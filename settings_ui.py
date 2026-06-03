"""Settings dialog for the runtime-editable subset of ``config.py``.

Exposes a curated set of constants (physical constants, frequency-response /
3D-grid resolution and spatial-smoothing parameters) in a modal ``QDialog``.

State model
-----------
Applying the dialog mutates the live ``config`` class attributes in place.
Because the physics and view layers read those attributes at call time (never
caching them at import), the new values take effect on the next recompute. The
values are also persisted to ``settings.json`` (resolved via
``config.get_user_data_path`` so it sits next to the executable in a frozen
build) so they survive a restart; on startup ``load_settings`` re-applies them
before the UI is built.

Separation of concerns
-----------------------
The dialog deliberately knows nothing about recomputation. After mutating config
it emits ``settings_applied``; the controller (``main``) connects to that
signal and performs the appropriate grid/freq-axis rebuild and view refresh.
"""

import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
)

import config as app_config

# settings.json is user-writable: use get_user_data_path so it lands next to
# the .exe in a frozen build (sys._MEIPASS is deleted on exit, so it can't live
# there) and in the working directory in script mode.
SETTINGS_PATH = app_config.get_user_data_path("settings.json")

_INT = "int"
_FLOAT = "float"

# Field spec: (config_class_name, attribute, label, kind, vmin, vmax, *extra)
#   kind _INT   -> QSpinBox          (extra: none)
#   kind _FLOAT -> QDoubleSpinBox    (extra: decimals, single_step)
FIELDS = [
    ("PhysicalConfig", "SPEED_OF_SOUND",    "Speed of sound (m/s)",      _FLOAT, 100.0, 700.0, 1, 1.0),
    ("PhysicalConfig", "MAX_CALC_FREQ",     "Max calc frequency (Hz)",   _FLOAT, 50.0, 1000.0, 0, 5.0),
    ("SimResolution",  "FREQ_1D_START",     "Freq response start (Hz)",  _INT,   1, 500),
    ("SimResolution",  "FREQ_1D_END",       "Freq response end (Hz)",    _INT,   2, 1000),
    ("SimResolution",  "FREQ_1D_STEP",      "Freq response step (Hz)",   _INT,   1, 50),
    ("SimResolution",  "GRID_SIZE_NORMAL",  "3D grid size (per axis)",   _INT,   8, 60),
    ("SimResolution",  "SMOOTHING_RADIUS",  "Smoothing radius (m)",      _FLOAT, 0.0, 2.0, 2, 0.05),
    ("SimResolution",  "SMOOTHING_SAMPLES", "Smoothing samples / axis",  _INT,   1, 11),
]

# Visual grouping of the fields into labelled sections.
_GROUPS = [
    ("Physical", ["SPEED_OF_SOUND", "MAX_CALC_FREQ"]),
    ("Frequency response resolution", ["FREQ_1D_START", "FREQ_1D_END", "FREQ_1D_STEP"]),
    ("3D resolution", ["GRID_SIZE_NORMAL"]),
    ("Spatial smoothing", ["SMOOTHING_RADIUS", "SMOOTHING_SAMPLES"]),
]


def _spec(attr):
    """Return the FIELDS entry for ``attr`` (raises KeyError if unknown)."""
    for spec in FIELDS:
        if spec[1] == attr:
            return spec
    raise KeyError(attr)


# ---------------------------------------------------------------------------
# Config mutation + persistence (module-level so they can be reused on startup)
# ---------------------------------------------------------------------------
def current_settings_dict():
    """Snapshot the current values of all exposed fields as
    ``{class_name: {attr: value}}``."""
    out = {}
    for cls_name, attr, *_ in FIELDS:
        out.setdefault(cls_name, {})[attr] = getattr(
            getattr(app_config, cls_name), attr
        )
    return out


def apply_settings_dict(values):
    """Write a ``{class_name: {attr: value}}`` mapping onto the live config
    classes. Unknown classes/attributes are ignored so a stale JSON file can
    never raise."""
    for cls_name, attrs in values.items():
        cls = getattr(app_config, cls_name, None)
        if cls is None:
            continue
        for attr, val in attrs.items():
            if hasattr(cls, attr):
                setattr(cls, attr, val)


def load_settings(path=SETTINGS_PATH):
    """Apply persisted settings (if any) onto the config classes. Silent on a
    missing or corrupt file so a bad file never blocks startup."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return
    apply_settings_dict(data)


def save_settings(path=SETTINGS_PATH):
    """Persist the current config values to JSON. Silent on write errors."""
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(current_settings_dict(), fh, indent=2)
    except OSError:
        pass


class SettingsDialog(QDialog):
    """Modal editor for the runtime-configurable subset of ``config.py``.

    Emits ``settings_applied`` after the live config has been mutated (on Apply
    or OK) so the controller can trigger a recompute. Cancel closes without
    applying. Widgets are initialised from the *current* config values, so
    reopening the dialog always reflects the last applied state.
    """

    settings_applied = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(360)

        self._editors = {}  # attr -> spin box

        root = QVBoxLayout(self)
        for group_title, attrs in _GROUPS:
            box = QGroupBox(group_title)
            form = QFormLayout(box)
            for attr in attrs:
                cls_name, _, label, kind, *rng = _spec(attr)
                editor = self._make_editor(kind, rng)
                editor.setValue(getattr(getattr(app_config, cls_name), attr))
                self._editors[attr] = editor
                form.addRow(label, editor)
            root.addWidget(box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._on_ok)          # OK
        buttons.rejected.connect(self.reject)           # Cancel
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._apply)
        root.addWidget(buttons)

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _make_editor(kind, rng):
        if kind == _INT:
            box = QSpinBox()
            box.setRange(int(rng[0]), int(rng[1]))
        else:
            box = QDoubleSpinBox()
            box.setRange(float(rng[0]), float(rng[1]))
            box.setDecimals(int(rng[2]))
            box.setSingleStep(float(rng[3]))
        return box

    def _collect(self):
        """Read every editor back into a ``{class_name: {attr: value}}`` map.
        QSpinBox yields int and QDoubleSpinBox yields float, so types are
        preserved correctly."""
        values = {}
        for cls_name, attr, *_ in FIELDS:
            values.setdefault(cls_name, {})[attr] = self._editors[attr].value()
        return values

    def _apply(self):
        apply_settings_dict(self._collect())
        save_settings()
        self.settings_applied.emit()

    def _on_ok(self):
        self._apply()
        self.accept()
