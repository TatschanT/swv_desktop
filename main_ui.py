import os
os.environ["QT_QPA_PLATFORM"] = "xcb"  # Wayland fix

import sys

from PySide6.QtCore import Qt
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
    """

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

    def _on_slider(self, tick):
        self.edit.setText(self._fmt(self._to_value(tick)))

    def _on_edit(self):
        try:
            v = float(self.edit.text())
        except ValueError:
            self.edit.setText(self._fmt(self.value()))
            return
        v = max(self._vmin, min(self._vmax, v))
        self.slider.setValue(self._to_tick(v))
        self.edit.setText(self._fmt(v))


class XYZSliders(QGroupBox):
    """A titled group containing three LabeledSliders for X, Y and Z."""

    def __init__(self, title, ranges, step, parent=None):
        super().__init__(title, parent)
        self.setFont(mono(10, bold=True))
        lay = QVBoxLayout(self)
        lay.setSpacing(4)
        self.x = LabeledSlider("X", *ranges["X"], step)
        self.y = LabeledSlider("Y", *ranges["Y"], step)
        self.z = LabeledSlider("Z", *ranges["Z"], step)
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
        room_ranges = {"X": (0.0, 20.0), "Y": (0.0, 20.0), "Z": (0.0, 20.0)}
        self.room = XYZSliders("Room dimension", room_ranges, 0.01)
        lay.addWidget(self.room)

        # --- Speaker 1 -----------------------------------------------
        spk_ranges = {"X": (0.0, 20.0), "Y": (0.0, 20.0), "Z": (0.0, 20.0)}
        self.spk1 = XYZSliders("Speaker 1 position", spk_ranges, 0.01)
        lay.addWidget(self.spk1)

        # --- L/R symmetry link ---------------------------------------
        self.symmetry_chk = QCheckBox("L/R symmetry link")
        self.symmetry_chk.setFont(mono(10, bold=True))
        lay.addWidget(self.symmetry_chk)

        # --- Speaker 2 -----------------------------------------------
        self.spk2 = XYZSliders("Speaker 2 position", spk_ranges, 0.01)
        lay.addWidget(self.spk2)

        # --- Mic -----------------------------------------------------
        self.mic = XYZSliders("Mic position", spk_ranges, 0.01)
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
