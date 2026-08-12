"""Reusable Qt view widgets for the Standing Wave Viewer UI.

These are self-contained presentation widgets with no dependency on the
controller (``MainWindow``):

  * ``mono``            - the shared Courier font factory.
  * ``LabeledSlider``   - a float slider with min/max labels and a numeric entry,
                          emitting ``valueChanged`` (live) and ``committed``
                          (gesture-finished) signals.
  * ``XYZSliders``      - a titled group of three ``LabeledSlider``s (X/Y/Z).
  * ``make_placeholder``- a simple labelled placeholder frame.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QVBoxLayout,
    QWidget,
)

# Monotone palette
DARK_BG = "#1e1e1e"
PLACEHOLDER_TEXT = "#888888"

# Debounce window (ms) used ONLY to detect "gesture finished" for inputs that
# have no natural press/release pair -- keyboard nudges (arrow/Page/Home/End)
# and mouse-wheel notches on a focused QSlider. A real mouse drag never uses
# this: QAbstractSlider.sliderReleased already fires instantly on release, so
# dragging performance and latency are completely unchanged by this constant.
COMMIT_DEBOUNCE_MS = 150


def mono(size=10, bold=False):
    """Return a Courier font."""
    f = QFont("Courier", size)
    f.setBold(bold)
    return f


class LabeledSlider(QWidget):
    """A horizontal slider with min/max labels above and a QLineEdit for
    direct numeric entry on the right.

    Slider works on integer ticks internally; `step` maps ticks to real
    values (e.g. 0.01 m or 0.1 reflection coefficient).

    Emits `valueChanged(float)` (the real, unscaled value) continuously while
    the slider is dragged or a number is committed in the line edit -- use this
    for lightweight live UI updates.

    Emits `committed(float)` only when the user *finishes* an interaction
    (releases the slider handle, or commits the line edit) -- use this to
    trigger heavy recomputation exactly once per gesture.

    A real mouse drag commits INSTANTLY on release (unchanged, zero added
    cost). Keyboard nudges (arrow/Page/Home/End) and mouse-wheel notches on a
    focused slider have no press/release pair at all -- Qt's
    `sliderReleased` never fires for them -- so without help `committed`
    would never fire for those either. Those two input paths debounce
    instead: `committed` fires once, `COMMIT_DEBOUNCE_MS` after the last such
    change, coalescing a burst (key-repeat, a fast wheel scroll) into a
    single recomputation. Dragging performance is untouched either way.
    """

    valueChanged = Signal(float)
    committed = Signal(float)

    def __init__(self, label, vmin, vmax, step, value=None, parent=None):
        super().__init__(parent)
        self._vmin = vmin
        self._vmax = vmax
        self._step = step
        self._ticks = int(round((vmax - vmin) / step))

        if value is None:
            value = vmin

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)

        # Row 1: caption
        cap = QLabel(label)
        cap.setFont(mono(9, bold=True))
        root.addWidget(cap)

        # Row 2: min / max range labels
        range_row = QHBoxLayout()
        range_row.setContentsMargins(0, 0, 0, 0)
        self._min_lbl = QLabel(self._fmt(vmin))
        self._max_lbl = QLabel(self._fmt(vmax))
        for lbl in (self._min_lbl, self._max_lbl):
            lbl.setFont(mono(7))
        range_row.addWidget(self._min_lbl, alignment=Qt.AlignLeft)
        range_row.addStretch()
        range_row.addWidget(self._max_lbl, alignment=Qt.AlignRight)
        root.addLayout(range_row)

        # Row 3: slider + line edit
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 0, 0, 0)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(self._ticks)
        self.slider.setValue(self._to_tick(value))

        self.edit = QLineEdit(self._fmt(value))
        self.edit.setFont(mono(9))
        self.edit.setFixedWidth(60)
        self.edit.setAlignment(Qt.AlignRight)

        ctrl_row.addWidget(self.slider, stretch=1)
        ctrl_row.addWidget(self.edit)
        root.addLayout(ctrl_row)

        # Fires `committed` for keyboard/wheel changes only -- see class
        # docstring. Single-shot + restarted on every qualifying change, so a
        # burst collapses into exactly one emission after it settles.
        self._commit_timer = QTimer(self)
        self._commit_timer.setSingleShot(True)
        self._commit_timer.timeout.connect(self._emit_committed)

        # Keep slider <-> edit in sync
        self.slider.valueChanged.connect(self._on_slider)
        self.edit.editingFinished.connect(self._on_edit)
        # Heavy-update trigger: only when the drag gesture finishes.
        self.slider.sliderReleased.connect(
            lambda: self.committed.emit(self.value())
        )
        # A fresh mouse press supersedes any pending debounce -- the release
        # handler above commits instantly instead, so this avoids a stray
        # leftover timer firing mid-drag.
        self.slider.sliderPressed.connect(self._commit_timer.stop)

    # -- helpers ---------------------------------------------------------
    def _fmt(self, v):
        if float(self._step).is_integer():
            return f"{v:.0f}"
        # decimals based on step
        decimals = max(0, len(str(self._step).split(".")[-1]))
        return f"{v:.{decimals}f}"

    def _to_tick(self, v):
        return int(round((v - self._vmin) / self._step))

    def _to_value(self, tick):
        return self._vmin + tick * self._step

    def value(self):
        return self._to_value(self.slider.value())

    def setValue(self, v):
        """Programmatically set the value (clamped, slider + edit kept in sync)."""
        v = max(self._vmin, min(self._vmax, v))
        self.slider.setValue(self._to_tick(v))
        self.edit.setText(self._fmt(v))

    def setMaxValue(self, new_vmax):
        """Update the upper bound at runtime.

        Recomputes the tick count for the new range, refreshes the max range
        label, and clamps the current value down if it now sits outside the
        boundary. The fixed `step` (and therefore the scaling logic) is
        preserved, so existing tick<->value conversions stay valid.
        """
        current = self.value()
        self._vmax = new_vmax
        self._ticks = int(round((new_vmax - self._vmin) / self._step))

        # Resizing the range can auto-clamp the slider; suppress the resulting
        # signal churn while we reconcile state, then restore the position.
        self.slider.blockSignals(True)
        self.slider.setMaximum(self._ticks)
        self.slider.setValue(self._to_tick(min(current, new_vmax)))
        self.slider.blockSignals(False)

        self._max_lbl.setText(self._fmt(new_vmax))

        if current > new_vmax:
            # Position fell outside the shrunken room -> clamp + notify listeners.
            self.edit.setText(self._fmt(new_vmax))
            self.valueChanged.emit(new_vmax)
        else:
            self.edit.setText(self._fmt(current))

    def setMinValue(self, new_vmin):
        """Update the lower bound at runtime (mirror of ``setMaxValue``).

        Because tick 0 maps to ``_vmin``, moving the lower bound re-bases the
        whole tick<->value mapping. We recompute the tick count for the new
        range, refresh the min range label, and clamp the current value up if it
        now sits below the boundary. The fixed ``step`` is preserved.
        """
        current = self.value()
        self._vmin = new_vmin
        self._ticks = int(round((self._vmax - new_vmin) / self._step))

        self.slider.blockSignals(True)
        self.slider.setMaximum(self._ticks)
        self.slider.setValue(self._to_tick(max(current, new_vmin)))
        self.slider.blockSignals(False)

        self._min_lbl.setText(self._fmt(new_vmin))

        if current < new_vmin:
            # Value fell below the new floor -> clamp + notify listeners.
            self.edit.setText(self._fmt(new_vmin))
            self.valueChanged.emit(new_vmin)
        else:
            self.edit.setText(self._fmt(current))

    def _on_slider(self, tick):
        # Slider drag -> mirror into edit, then notify listeners with real value.
        self.edit.setText(self._fmt(self._to_value(tick)))
        self.valueChanged.emit(self._to_value(tick))
        # isSliderDown() is True only while an actual mouse press/drag is in
        # progress -- that case already commits instantly on release (see
        # __init__), so skip the timer for it: dragging stays exactly as
        # lightweight as before. Everything else reaching here (keyboard,
        # wheel, or a programmatic setValue()/setMaxValue() from elsewhere in
        # the app) has no release event of its own, so schedule one.
        if not self.slider.isSliderDown():
            self._commit_timer.start(COMMIT_DEBOUNCE_MS)

    def _emit_committed(self):
        self.committed.emit(self.value())

    def _on_edit(self):
        try:
            v = float(self.edit.text())
        except ValueError:
            self.edit.setText(self._fmt(self.value()))
            return
        v = max(self._vmin, min(self._vmax, v))
        new_tick = self._to_tick(v)
        # If the tick is unchanged the slider won't re-emit, so notify explicitly.
        if new_tick == self.slider.value():
            self.edit.setText(self._fmt(v))
            self.valueChanged.emit(v)
        else:
            self.slider.setValue(new_tick)  # triggers _on_slider -> emits
            self.edit.setText(self._fmt(v))
        # Committing the line edit is a finished gesture -> heavy update.
        self.committed.emit(v)


class XYZSliders(QGroupBox):
    """A titled group containing three LabeledSliders for X, Y and Z."""

    def __init__(self, title, ranges, step, defaults=None, parent=None):
        super().__init__(title, parent)
        self.setFont(mono(10, bold=True))
        defaults = defaults or {}
        lay = QVBoxLayout(self)
        lay.setSpacing(4)
        self.x = LabeledSlider("X", *ranges["X"], step, value=defaults.get("X"))
        self.y = LabeledSlider("Y", *ranges["Y"], step, value=defaults.get("Y"))
        self.z = LabeledSlider("Z", *ranges["Z"], step, value=defaults.get("Z"))
        for s in (self.x, self.y, self.z):
            lay.addWidget(s)


def make_placeholder(text, bg=DARK_BG):
    frame = QFrame()
    frame.setStyleSheet(
        f"background-color: {bg}; border: 1px solid #000;"
    )
    lay = QVBoxLayout(frame)
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFont(mono(14, bold=True))
    lbl.setStyleSheet(f"color: {PLACEHOLDER_TEXT}; border: none;")
    lay.addWidget(lbl)
    return frame
