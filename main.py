import os
import platform
if platform.system() == "Linux":
    os.environ["QT_QPA_PLATFORM"] = "xcb"

import csv
import sys
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
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

# View layer (3D + 2D)
import render
from graphs import Plot2DWidget
from settings_ui import SettingsDialog, load_settings

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

    Emits `valueChanged(float)` (the real, unscaled value) continuously while
    the slider is dragged or a number is committed in the line edit -- use this
    for lightweight live UI updates.

    Emits `committed(float)` only when the user *finishes* an interaction
    (releases the slider handle, or commits the line edit) -- use this to
    trigger heavy recomputation exactly once per gesture.
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

        # Keep slider <-> edit in sync
        self.slider.valueChanged.connect(self._on_slider)
        self.edit.editingFinished.connect(self._on_edit)
        # Heavy-update trigger: only when the drag gesture finishes.
        self.slider.sliderReleased.connect(
            lambda: self.committed.emit(self.value())
        )

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


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Standing Wave Viewer")
        self.setFixedSize(WIN_W, WIN_H)
        self.setFont(mono(10))

        # Apply any persisted settings BEFORE building the panels: the 3D grid
        # size and the 2D frequency axis are read from config at construction.
        load_settings()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_left())
        root.addWidget(self._build_center())
        root.addWidget(self._build_right())

        # Constrain position sliders to the default room, then populate the
        # room-modes table. Both must run after the panels exist.
        self._sync_position_limits()
        self.update_room_modes()

        # Wire up the 3D view signals and draw the initial field + 2D plots.
        self._wire_3d_signals()
        self._refresh(recompute_response=True)

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------
    def _build_left(self):
        panel = QWidget()
        panel.setFixedWidth(LEFT_W)
        # Scope the divider border to the panel itself; an unscoped rule would
        # cascade to every child widget (group boxes, labels, sliders) and add
        # stray borders that corrupt their rendering.
        panel.setObjectName("leftPanel")
        panel.setStyleSheet("#leftPanel { border-right: 2px solid #000; }")
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

        # Constrain speaker/mic positions to the room: each room axis caps the
        # matching axis on Speaker 1, Speaker 2 and Mic (and clamps if needed).
        self.room.x.valueChanged.connect(lambda v: self._limit_axis("x", v))
        self.room.y.valueChanged.connect(lambda v: self._limit_axis("y", v))
        self.room.z.valueChanged.connect(lambda v: self._limit_axis("z", v))

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

        # Logic: enable/disable speaker 2 + symmetry based on source count.
        self.source_combo.currentIndexChanged.connect(self._update_source_state)
        # Toggling the link re-locks/unlocks Speaker 2 and re-mirrors it.
        self.symmetry_chk.toggled.connect(self._update_source_state)
        # While linked, any Speaker 1 move (and a room-width change, since
        # spk2.x = Lx - spk1.x) re-mirrors Speaker 2.
        for axis in (self.spk1.x, self.spk1.y, self.spk1.z):
            axis.valueChanged.connect(self._sync_symmetry)
        self.room.x.valueChanged.connect(self._sync_symmetry)

        self._update_source_state()

        return panel

    def _update_source_state(self, *_):
        """Enable/disable Speaker 2 and the L/R link based on source count and
        the symmetry toggle. Speaker 2 is editable only with 2 sources AND the
        link OFF; when the link is ON it is locked (disabled) and mirrored."""
        two_sources = self.source_combo.currentText() == "2"
        linked = two_sources and self.symmetry_chk.isChecked()

        self.symmetry_chk.setEnabled(two_sources)
        self.spk2.setEnabled(two_sources and not linked)

        if linked:
            self._sync_symmetry()

    def _sync_symmetry(self, *_):
        """Mirror Speaker 2 from Speaker 1 when the L/R link is active.

        Verified against old_src/main.py: X is mirrored across the room width
        (spk2.x = Lx - spk1.x); Y and Z match Speaker 1 exactly.
        """
        if self.source_combo.currentText() != "2" or not self.symmetry_chk.isChecked():
            return
        Lx = self.room.x.value()
        self.spk2.x.setValue(Lx - self.spk1.x.value())
        self.spk2.y.setValue(self.spk1.y.value())
        self.spk2.z.setValue(self.spk1.z.value())

    def closeEvent(self, event):
        """Release the VTK render window before the app exits."""
        self.render3d.close()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # CONTROLLER: room <-> position constraints
    # ------------------------------------------------------------------
    def _limit_axis(self, axis, new_max):
        """Cap the given axis ('x'/'y'/'z') of every position group to the
        current room dimension, clamping any position now out of bounds."""
        for grp in (self.spk1, self.spk2, self.mic):
            getattr(grp, axis).setMaxValue(new_max)

    def _sync_position_limits(self):
        """Apply all three room dimensions as position-slider maxima (startup)."""
        self._limit_axis("x", self.room.x.value())
        self._limit_axis("y", self.room.y.value())
        self._limit_axis("z", self.room.z.value())

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

    # ------------------------------------------------------------------
    # CONTROLLER: 3D pressure field
    # ------------------------------------------------------------------
    def _wall_reflection(self):
        """Per-axis reflection coefficient = mean of the two opposing walls
        (matches the original Streamlit model)."""
        w = self.wall_sliders
        Rx = (w["Left (X=0)"].value() + w["Right (X=Lx)"].value()) / 2.0
        Ry = (w["Front (Y=0)"].value() + w["Back (Y=Ly)"].value()) / 2.0
        Rz = (w["Floor (Z=0)"].value() + w["Ceiling (Z=Lz)"].value()) / 2.0
        return Rx, Ry, Rz

    def _current_room(self):
        Rx, Ry, Rz = self._wall_reflection()
        return physics.RoomConfig(
            Lx=self.room.x.value(), Ly=self.room.y.value(), Lz=self.room.z.value(),
            Rx=Rx, Ry=Ry, Rz=Rz,
        )

    def _pos(self, grp):
        return physics.Position(grp.x.value(), grp.y.value(), grp.z.value())

    def _corr_mode(self):
        """Map the UI combo label to the substring physics.py expects."""
        label = self.phase_combo.currentText().lower()
        if "complex" in label:
            return "True Complex Field"
        if "cancel" in label:
            return "Global Cancel"
        return "Uncorrelated"

    def _refresh(self, recompute_response):
        """Refresh the 3D field and the 2D plots from the current UI state.

        The 3D volume always recomputes (it shows the field at the selected
        frequency). For the 2D plots, ``recompute_response`` controls whether the
        expensive 1D frequency-response curve is recomputed (geometry change) or
        only the marker line is moved (frequency change) -- the curve itself is
        frequency-independent.
        """
        room = self._current_room()
        spk1 = self._pos(self.spk1)
        spk2 = self._pos(self.spk2)
        mic = self._pos(self.mic)
        num_src = 2 if self.source_combo.currentText() == "2" else 1
        corr = self._corr_mode()
        freq = self.freq_slider.value()

        mode_freqs = None
        if self.show_modes_chk.isChecked():
            mode_freqs = [f for f, _, _ in physics.calc_room_modes(room)]

        self.render3d.update_mesh(room, spk1, spk2, mic, num_src, corr, freq)
        self.plot2d.update_all(
            room, spk1, spk2, mic, num_src, corr, freq,
            recompute_response=recompute_response,
            smoothing=self.smoothing_chk.isChecked(),
            mode_freqs=mode_freqs,
        )

    # ---- Frequency slider --------------------------------------------
    def _on_freq_changed(self, *_):
        """While the frequency slider moves: lightweight only -- slide the red
        marker line on the response graph. The 3D field recompute waits for the
        release (or runs live if Dynamic update is on)."""
        self.plot2d.update_freq_marker(self.freq_slider.value())
        if self.dynamic_chk.isChecked():
            self._refresh(recompute_response=False)

    def _on_freq_committed(self, *_):
        """Frequency slider released / value typed: recompute the 3D field once
        (the 2D response curve is frequency-independent, so only its marker
        moves)."""
        self._refresh(recompute_response=False)

    # ---- Geometry / source / walls -----------------------------------
    def _on_param_changed(self, *_):
        """Live recompute while dragging, but ONLY when Dynamic update is on."""
        if self.dynamic_chk.isChecked():
            self._refresh(recompute_response=True)

    def _on_param_committed(self, *_):
        """Slider released / value typed / combo changed: recompute the field
        and the 2D response curve exactly once, regardless of the toggle."""
        self._refresh(recompute_response=True)

    def _on_render_mode_changed(self, *_):
        """Switch the 3D view between volume and contour rendering.

        The pressure field and the 2D response are unchanged, so this is a
        lightweight 3D-only path: it regenerates the iso-surfaces from the
        EXISTING field and flips actor visibility (no physics recompute, no 2D
        redraw). Camera is preserved -- ``set_render_mode`` only does
        SetVisibility + in-place copy_from."""
        num_src = 2 if self.source_combo.currentText() == "2" else 1
        self.render3d.set_render_mode(self.contour_chk.isChecked(), num_src)

    def _on_reset_view(self):
        """Forcefully restore the default isometric view of the current room.

        Manual rotation/zoom/pan leaves the camera with a custom focal point and
        view-up that a bare ``reset_camera()`` will preserve, so the view appears
        not to reset. We therefore:
          1. snap the camera back to the canonical isometric orientation
             (this clears the user's manual focal point / view-up), then
          2. refit it to the current room bounds at the VTK renderer level, then
          3. force the embedded Qt widget to repaint.
        """
        plotter = self.render3d.plotter
        # 1. Force the camera out of its manual state to the default iso angle.
        plotter.camera_position = "iso"
        # 2. Refit to the current room bounds (vtkRenderer-level reset).
        plotter.renderer.ResetCamera(*self.render3d.grid.bounds)
        # 3. Repaint the Qt widget (processEvents flush, not just a VTK draw).
        plotter.update()

    # ------------------------------------------------------------------
    # CONTROLLER: data export
    # ------------------------------------------------------------------
    def on_export_clicked(self):
        """Export the current parameters, frequency-response curve and room
        modes to a CSV file chosen by the user.

        Does nothing if the user cancels the save dialog. The CSV is laid out as
        three labelled sections separated by blank lines so it stays readable in
        a spreadsheet while remaining a single file.
        """
        default_name = "swv_export_{}.csv".format(
            datetime.now().strftime("%Y%m%d_%H%M%S")
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Data", default_name, "CSV files (*.csv)"
        )
        if not path:
            # User cancelled the dialog -> nothing to do.
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        # Gather current state.
        room = self._current_room()
        spk1, spk2, mic = self._pos(self.spk1), self._pos(self.spk2), self._pos(self.mic)
        num_src = 2 if self.source_combo.currentText() == "2" else 1
        w = self.wall_sliders
        modes = physics.calc_room_modes(room)

        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)

                # --- Section 1: parameters -------------------------------
                writer.writerow(["[Parameters]"])
                writer.writerow(["Parameter", "Value"])
                writer.writerow(["Room Lx (m)", f"{room.Lx:.3f}"])
                writer.writerow(["Room Ly (m)", f"{room.Ly:.3f}"])
                writer.writerow(["Room Lz (m)", f"{room.Lz:.3f}"])
                writer.writerow(["Speaker 1 (x,y,z)", f"{spk1.x:.3f}, {spk1.y:.3f}, {spk1.z:.3f}"])
                if num_src == 2:
                    writer.writerow(["Speaker 2 (x,y,z)", f"{spk2.x:.3f}, {spk2.y:.3f}, {spk2.z:.3f}"])
                writer.writerow(["Mic (x,y,z)", f"{mic.x:.3f}, {mic.y:.3f}, {mic.z:.3f}"])
                writer.writerow(["Reflection Rx", f"{room.Rx:.3f}"])
                writer.writerow(["Reflection Ry", f"{room.Ry:.3f}"])
                writer.writerow(["Reflection Rz", f"{room.Rz:.3f}"])
                writer.writerow(["Wall Left (X=0)", f"{w['Left (X=0)'].value():.2f}"])
                writer.writerow(["Wall Right (X=Lx)", f"{w['Right (X=Lx)'].value():.2f}"])
                writer.writerow(["Wall Front (Y=0)", f"{w['Front (Y=0)'].value():.2f}"])
                writer.writerow(["Wall Back (Y=Ly)", f"{w['Back (Y=Ly)'].value():.2f}"])
                writer.writerow(["Wall Floor (Z=0)", f"{w['Floor (Z=0)'].value():.2f}"])
                writer.writerow(["Wall Ceiling (Z=Lz)", f"{w['Ceiling (Z=Lz)'].value():.2f}"])
                writer.writerow(["Frequency (Hz)", f"{self.freq_slider.value():.1f}"])
                writer.writerow(["Source count", num_src])
                writer.writerow(["Phase correction", self._corr_mode()])
                writer.writerow(["Spatial smoothing", self.smoothing_chk.isChecked()])

                # --- Section 2: frequency response -----------------------
                writer.writerow([])
                writer.writerow(["[Frequency Response]"])
                writer.writerow(["Frequency (Hz)", "Relative SPL (dB)"])
                freqs, db = self.plot2d._freqs, self.plot2d._db
                if db is not None:
                    for f, d in zip(freqs, db):
                        writer.writerow([f"{f:.1f}", f"{d:.3f}"])

                # --- Section 3: room modes -------------------------------
                writer.writerow([])
                writer.writerow(["[Room Modes]"])
                writer.writerow(["Frequency (Hz)", "Mode (nx, ny, nz)", "Length (m)"])
                for freq, (nx, ny, nz), length in modes:
                    writer.writerow([f"{freq:.1f}", f"({nx}, {ny}, {nz})", f"{length:.3f}"])
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write file:\n{exc}")
            return

        QMessageBox.information(self, "Export complete", f"Data exported to:\n{path}")

    # ------------------------------------------------------------------
    # CONTROLLER: settings dialog
    # ------------------------------------------------------------------
    def _open_settings(self):
        """Open the modal Settings dialog. It mutates config in place and emits
        ``settings_applied``, which we react to with a full rebuild + refresh."""
        dlg = SettingsDialog(self)
        dlg.settings_applied.connect(self._on_settings_applied)
        dlg.exec()

    def _on_settings_applied(self):
        """React to applied settings. Some config values are consumed only at
        construction (3D grid size) or cached (2D frequency axis), so rebuild
        those explicitly, refresh the room-modes table (depends on speed of
        sound / max frequency), then recompute the 3D + 2D views once."""
        room = self._current_room()
        self.render3d.set_grid_size(app_config.SimResolution.GRID_SIZE_NORMAL, room)
        self.plot2d.rebuild_freqs()
        self.update_room_modes()
        self._refresh(recompute_response=True)

    def _wire_3d_signals(self):
        # Frequency: live marker on drag (+ optional live recompute), and a
        # single heavy recompute when the gesture finishes.
        self.freq_slider.valueChanged.connect(self._on_freq_changed)
        self.freq_slider.committed.connect(self._on_freq_committed)

        # Room + speaker/mic + wall sliders: live recompute only when Dynamic is
        # on, but ALWAYS a single recompute when the gesture finishes.
        for grp in (self.room, self.spk1, self.spk2, self.mic):
            for axis in (grp.x, grp.y, grp.z):
                axis.valueChanged.connect(self._on_param_changed)
                axis.committed.connect(self._on_param_committed)
        for slider in self.wall_sliders.values():
            slider.valueChanged.connect(self._on_param_changed)
            slider.committed.connect(self._on_param_committed)

        # Combos are discrete commits -> recompute immediately.
        self.source_combo.currentIndexChanged.connect(self._on_param_committed)
        self.phase_combo.currentIndexChanged.connect(self._on_param_committed)

        self.reset_view_btn.clicked.connect(self._on_reset_view)

        # Both 2D-graph toggles are discrete commits -> full response recompute.
        self.show_modes_chk.toggled.connect(self._on_param_committed)
        self.smoothing_chk.toggled.connect(self._on_param_committed)

        # 3D render-mode toggle: lightweight 3D-only path (no physics / no 2D).
        self.contour_chk.toggled.connect(self._on_render_mode_changed)

        # Export current state to CSV.
        self.export_btn.clicked.connect(self.on_export_clicked)

        # Open the runtime settings dialog.
        self.settings_btn.clicked.connect(self._open_settings)

    # ------------------------------------------------------------------
    # CENTER PANEL
    # ------------------------------------------------------------------
    def _build_center(self):
        panel = QWidget()
        panel.setFixedWidth(CENTER_W)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # --- Top section (340 px): embedded Matplotlib 2D plots ------
        top_section = QWidget()
        top_section.setFixedHeight(TOP_H - 16)
        top_lay = QVBoxLayout(top_section)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(2)

        self.plot2d = Plot2DWidget(panel)
        top_lay.addWidget(self.plot2d, stretch=1)

        # Toggle row at the bottom-right of the 2D-graph panel.
        # Both toggles are discrete commits -> wired in _wire_3d_signals.
        smooth_row = QHBoxLayout()
        smooth_row.setContentsMargins(0, 0, 0, 0)
        smooth_row.addStretch()
        self.show_modes_chk = QCheckBox("Show room modes")
        self.show_modes_chk.setFont(mono(9, bold=True))
        smooth_row.addWidget(self.show_modes_chk)
        self.smoothing_chk = QCheckBox("Spatial Smoothing")
        self.smoothing_chk.setFont(mono(9, bold=True))
        smooth_row.addWidget(self.smoothing_chk)
        top_lay.addLayout(smooth_row)

        lay.addWidget(top_section)

        # --- Bottom section (660 px) ---------------------------------
        bottom = QWidget()
        bottom.setFixedHeight(BOTTOM_H - 16)
        blay = QVBoxLayout(bottom)
        blay.setContentsMargins(0, 0, 0, 0)
        blay.setSpacing(6)

        # Real PyVista 3D view (replaces the former placeholder frame).
        self.render3d = render.Render3D(panel)
        blay.addWidget(self.render3d.interactor, stretch=1)

        # Frequency slider (1 Hz steps), matched to the physics calc range.
        self.freq_slider = LabeledSlider(
            "Frequency (Hz)", 20.0, 250.0, 1.0, value=40.0
        )
        blay.addWidget(self.freq_slider)

        # Toggle and action controls bottom-right
        toggles = QHBoxLayout()
        toggles.addStretch()
        # 3D render-mode switch: volume (dense) vs. contour ("clear visibility").
        # Toggling it neither changes the physics nor the 2D response, so it is
        # routed to a lightweight 3D-only handler (see _wire_3d_signals).
        self.contour_chk = QCheckBox("Contour Mode")
        self.contour_chk.setFont(mono(9, bold=True))
        toggles.addWidget(self.contour_chk)
        self.dynamic_chk = QCheckBox("Dynamic update")
        self.dynamic_chk.setFont(mono(9, bold=True))
        toggles.addWidget(self.dynamic_chk)
        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.setFont(mono(9, bold=True))
        toggles.addWidget(self.reset_view_btn)
        blay.addLayout(toggles)

        lay.addWidget(bottom)

        return panel

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------
    def _build_right(self):
        panel = QWidget()
        panel.setFixedWidth(RIGHT_W)
        # Scope the divider border to the panel itself; an unscoped rule would
        # cascade to every child widget and corrupt the group-box titles.
        panel.setObjectName("rightPanel")
        panel.setStyleSheet("#rightPanel { border-left: 2px solid #000; }")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # --- Logo banner (72 px) ------------------------------------
        banner_label = QLabel()
        banner_label.setFixedHeight(BANNER_H)
        banner_label.setAlignment(Qt.AlignCenter)
        banner_label.setStyleSheet("background-color: #b1b2b5;")
        logo_path = app_config.get_resource_path(os.path.join("images", "SWVlogo_s.jpg"))
        pixmap = QPixmap(logo_path)
        if not pixmap.isNull():
            banner_label.setPixmap(
                pixmap.scaled(RIGHT_W - 16, BANNER_H, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        lay.addWidget(banner_label)

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
        R0 = app_config.AppDefaults.R
        for row, (a, b) in enumerate(wall_pairs):
            sa = LabeledSlider(a, 0.0, 1.0, 0.1, value=R0)
            sb = LabeledSlider(b, 0.0, 1.0, 0.1, value=R0)
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
        self.modes_table.setFont(mono(10))
        self.modes_table.setHorizontalHeaderLabels(
            ["Hz", "Modes (x, y, z)", "L (m)"]
        )
        self.modes_table.verticalHeader().setVisible(False)
        self.modes_table.horizontalHeader().setFont(mono(10, bold=True))
        self.modes_table.setEditTriggers(QTableWidget.NoEditTriggers)
        # Small breathing room between cell text and the cell borders.
        self.modes_table.setStyleSheet("QTableWidget::item { padding: 1px; }")
        # Distribute the three columns evenly across the full panel width
        # instead of sizing to content (which left them bunched on the left).
        self.modes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for r in range(16):
            for c in range(3):
                self.modes_table.setItem(r, c, QTableWidgetItem(""))
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
