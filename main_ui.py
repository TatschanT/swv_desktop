import os
os.environ["QT_QPA_PLATFORM"] = "xcb"  # Wayland fix

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Model layer (streamlit-free desktop port)
import config as app_config
import physics

# ---------------------------------------------------------------------------
# Global dimensions (px)
# ---------------------------------------------------------------------------
WIN_W, WIN_H = 1600, 1000
LEFT_W = 340
CENTER_W = 920
RIGHT_W = 340
TOP_H = 340
BOTTOM_H = 660
BANNER_H = 72

# Monotone palette
DARK_BG = "#1e1e1e"
PLACEHOLDER_TEXT = "#888888"


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

    Emits `valueChanged(float)` (the real, unscaled value) whenever the slider
    is dragged or a valid number is committed in the line edit.
    """

    valueChanged = Signal(float)

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

        # Keep slider <-> edit in sync
        self.slider.valueChanged.connect(self._on_slider)
        self.edit.editingFinished.connect(self._on_edit)

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

    def _on_slider(self, tick):
        # Slider drag -> mirror into edit, then notify listeners with real value.
        self.edit.setText(self._fmt(self._to_value(tick)))
        self.valueChanged.emit(self._to_value(tick))

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Standing Wave Viewer")
        self.setFixedSize(WIN_W, WIN_H)
        self.setFont(mono(10))

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_left())
        root.addWidget(self._build_center())
        root.addWidget(self._build_right())

        # Populate the room-modes table with the startup defaults. Must run
        # after _build_right() has created self.modes_table.
        self.update_room_modes()

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------
    def _build_left(self):
        panel = QWidget()
        panel.setFixedWidth(LEFT_W)
        panel.setStyleSheet("border-right: 2px solid #000;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(6)

        title = QLabel("Control Panel")
        title.setFont(mono(13, bold=True))
        lay.addWidget(title)

        # --- Mode selection ------------------------------------------
        mode_box = QGroupBox("Mode select")
        mode_box.setFont(mono(10, bold=True))
        mode_lay = QGridLayout(mode_box)

        mode_lay.addWidget(QLabel("Source"), 0, 0)
        self.source_combo = QComboBox()
        self.source_combo.addItems(["1", "2"])
        self.source_combo.setFont(mono(10))
        mode_lay.addWidget(self.source_combo, 0, 1)

        mode_lay.addWidget(QLabel("Stereo phase corr."), 1, 0)
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(
            ["Uncorrected", "Global cancel", "True complex field"]
        )
        self.phase_combo.setFont(mono(10))
        mode_lay.addWidget(self.phase_combo, 1, 1)
        lay.addWidget(mode_box)

        # --- Room dimension ------------------------------------------
        D = app_config.AppDefaults
        room_ranges = {
            "X": (D.ROOM_MIN_L, D.ROOM_MAX_L_XY),
            "Y": (D.ROOM_MIN_L, D.ROOM_MAX_L_XY),
            "Z": (D.ROOM_MIN_L, D.ROOM_MAX_L_Z),
        }
        room_defaults = {"X": D.LX, "Y": D.LY, "Z": D.LZ}
        self.room = XYZSliders("Room dimension", room_ranges, 0.01, room_defaults)
        lay.addWidget(self.room)

        # Recompute the room-modes table whenever a room dimension changes.
        self.room.x.valueChanged.connect(self.update_room_modes)
        self.room.y.valueChanged.connect(self.update_room_modes)
        self.room.z.valueChanged.connect(self.update_room_modes)

        # --- Speaker 1 -----------------------------------------------
        spk_ranges = {"X": (0.0, D.ROOM_MAX_L_XY), "Y": (0.0, D.ROOM_MAX_L_XY), "Z": (0.0, D.ROOM_MAX_L_Z)}
        spk1_defaults = {"X": D.SPK_X, "Y": D.SPK_Y, "Z": D.SPK_Z}
        self.spk1 = XYZSliders("Speaker 1 position", spk_ranges, 0.01, spk1_defaults)
        lay.addWidget(self.spk1)

        # --- L/R symmetry link ---------------------------------------
        self.symmetry_chk = QCheckBox("L/R symmetry link")
        self.symmetry_chk.setFont(mono(10, bold=True))
        lay.addWidget(self.symmetry_chk)

        # --- Speaker 2 -----------------------------------------------
        spk2_defaults = {"X": D.SPK2_X, "Y": D.SPK2_Y, "Z": D.SPK2_Z}
        self.spk2 = XYZSliders("Speaker 2 position", spk_ranges, 0.01, spk2_defaults)
        lay.addWidget(self.spk2)

        # --- Mic -----------------------------------------------------
        mic_defaults = {"X": D.MIC_X, "Y": D.MIC_Y, "Z": D.MIC_Z}
        self.mic = XYZSliders("Mic position", spk_ranges, 0.01, mic_defaults)
        lay.addWidget(self.mic)

        lay.addStretch()

        # Logic: enable/disable speaker 2 + symmetry based on source count
        self.source_combo.currentIndexChanged.connect(self._update_source_state)
        self._update_source_state()

        return panel

    def _update_source_state(self):
        """Grey out Speaker 2 sliders and L/R link when only 1 source."""
        two_sources = self.source_combo.currentText() == "2"
        self.spk2.setEnabled(two_sources)
        self.symmetry_chk.setEnabled(two_sources)

    # ------------------------------------------------------------------
    # CONTROLLER: room modes
    # ------------------------------------------------------------------
    def update_room_modes(self, *_):
        """Recompute the room eigenmodes from the current Room Dimension
        sliders and repopulate the Room modes table (sorted by frequency).

        Accepts/ignores any positional arg so it can be wired directly to a
        slider's valueChanged(float) signal.
        """
        Lx = self.room.x.value()
        Ly = self.room.y.value()
        Lz = self.room.z.value()

        room = physics.RoomConfig(Lx=Lx, Ly=Ly, Lz=Lz, Rx=0.0, Ry=0.0, Rz=0.0)
        modes = physics.calc_room_modes(room)

        table = self.modes_table
        # Keep at least the original 16 rows so the panel layout is stable,
        # but grow if more modes fall under the frequency ceiling.
        table.setRowCount(max(16, len(modes)))

        for r in range(table.rowCount()):
            if r < len(modes):
                freq, (nx, ny, nz), length = modes[r]
                cells = [f"{freq:.1f}", f"({nx}, {ny}, {nz})", f"{length:.2f}"]
            else:
                cells = ["", "", ""]
            for c, text in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(text))

        table.resizeColumnsToContents()

    # ------------------------------------------------------------------
    # CENTER PANEL
    # ------------------------------------------------------------------
    def _build_center(self):
        panel = QWidget()
        panel.setFixedWidth(CENTER_W)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # --- Top section (340 px) ------------------------------------
        top = make_placeholder("Top-down view  |  Frequency response graph")
        top.setFixedHeight(TOP_H - 16)
        lay.addWidget(top)

        # --- Bottom section (660 px) ---------------------------------
        bottom = QWidget()
        bottom.setFixedHeight(BOTTOM_H - 16)
        blay = QVBoxLayout(bottom)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(6)

        view3d = make_placeholder("PyVista 3D View")
        blay.addWidget(view3d, stretch=1)

        # Frequency slider (1 Hz steps)
        self.freq_slider = LabeledSlider(
            "Frequency (Hz)", 1.0, 300.0, 1.0, value=20.0
        )
        blay.addWidget(self.freq_slider)

        # Toggle switches bottom-right
        toggles = QHBoxLayout()
        toggles.addStretch()
        self.dynamic_chk = QCheckBox("Dynamic update")
        self.camlock_chk = QCheckBox("Camera lock")
        for chk in (self.dynamic_chk, self.camlock_chk):
            chk.setFont(mono(9, bold=True))
            toggles.addWidget(chk)
        blay.addLayout(toggles)

        lay.addWidget(bottom)

        return panel

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------
    def _build_right(self):
        panel = QWidget()
        panel.setFixedWidth(RIGHT_W)
        panel.setStyleSheet("border-left: 2px solid #000;")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # --- Title banner (72 px) ------------------------------------
        banner = make_placeholder("Title Banner", bg="#b1b2b5")
        banner.setFixedHeight(BANNER_H)
        lay.addWidget(banner)

        # --- Wall reflection coefficients ----------------------------
        wall_box = QGroupBox("Wall reflection coefficients")
        wall_box.setFont(mono(10, bold=True))
        wall_lay = QGridLayout(wall_box)
        wall_lay.setSpacing(4)

        # 3 rows x 2 columns: Left/Right, Front/Back, Top/Bottom
        wall_pairs = [
            ("Left (X=0)", "Right (X=Lx)"),
            ("Front (Y=0)", "Back (Y=Ly)"),
            ("Floor (Z=0)", "Ceiling (Z=Lz)"),
        ]
        self.wall_sliders = {}
        for row, (a, b) in enumerate(wall_pairs):
            sa = LabeledSlider(a, 0.0, 1.0, 0.1, value=1.0)
            sb = LabeledSlider(b, 0.0, 1.0, 0.1, value=1.0)
            wall_lay.addWidget(sa, row, 0)
            wall_lay.addWidget(sb, row, 1)
            self.wall_sliders[a] = sa
            self.wall_sliders[b] = sb
        lay.addWidget(wall_box)

        # --- Room modes table ----------------------------------------
        modes_box = QGroupBox("Room modes")
        modes_box.setFont(mono(10, bold=True))
        modes_lay = QVBoxLayout(modes_box)
        self.modes_table = QTableWidget(16, 3)
        self.modes_table.setFont(mono(9))
        self.modes_table.setHorizontalHeaderLabels(
            ["Hz", "Modes (x, y, z)", "L (m)"]
        )
        self.modes_table.verticalHeader().setVisible(False)
        self.modes_table.horizontalHeader().setFont(mono(9, bold=True))
        self.modes_table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r in range(16):
            for c in range(3):
                self.modes_table.setItem(r, c, QTableWidgetItem(""))
        self.modes_table.resizeColumnsToContents()
        modes_lay.addWidget(self.modes_table)
        lay.addWidget(modes_box, stretch=1)

        # --- Buttons -------------------------------------------------
        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export data")
        self.settings_btn = QPushButton("Settings")
        for btn in (self.export_btn, self.settings_btn):
            btn.setFont(mono(10, bold=True))
            btn.setFixedHeight(40)
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        return panel


def main():
    app = QApplication(sys.argv)
    app.setFont(mono(10))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
