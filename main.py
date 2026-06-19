import os
import platform

if platform.system() == "Linux":
    os.environ["QT_QPA_PLATFORM"] = "xcb"
# Hotfix to prevent window scaling
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

import sys
from collections import namedtuple
from datetime import datetime

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Model layer (streamlit-free desktop port)
import config as app_config
import constants
import csv_io
import physics

# View layer (3D + 2D)
import render
from graphs import Plot2DWidget
from settings_ui import SettingsDialog, load_settings
from widgets import LabeledSlider, XYZSliders, mono

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

# The physics parameters shared by the 3D field, 1D response and calibration
# sweep. Built by MainWindow._physics_snapshot() so every consumer reads the
# same derived state.
PhysicsSnapshot = namedtuple(
    "PhysicsSnapshot", "room spk1 spk2 mic num_src corr room_scatter"
)


class CalibWorker(QThread):
    """Background full-band calibration sweep.

    Sweeps every frequency the 1D response curve uses (MIN_FREQ..MAX_FREQ in
    FREQ_1D_STEP) at the current grid size, computes the 3D pressure field at
    each, collects a 2-sigma-clipped spatial maximum per frequency, and reports
    a median-centred dB reference: the linear pressure at the median of the
    per-frequency maxima (in dB) plus the +/- dB half-window the renderer maps
    onto the colour range. The median makes the scale robust against the extreme
    outlier peaks that a raw global max would be dominated by.

    All physics parameters are passed in as a SNAPSHOT at construction time so
    mid-computation UI changes cannot corrupt the result.
    """

    progress = Signal(int)           # 0-100
    finished = Signal(float, float)  # (median_pressure, db_range)

    def __init__(self, room, spk1, spk2, num_src, corr_mode,
                 room_scatter, grid_size):
        super().__init__()
        self.room = room
        self.spk1 = spk1
        self.spk2 = spk2
        self.num_src = num_src
        self.corr_mode = corr_mode
        self.room_scatter = room_scatter
        self.grid_size = grid_size

    def run(self):
        freqs = np.arange(
            app_config.PhysicalConfig.MIN_FREQ,
            app_config.PhysicalConfig.MAX_FREQ + app_config.SimResolution.FREQ_1D_STEP,
            app_config.SimResolution.FREQ_1D_STEP,
        )
        spatial_maxes = []
        n = len(freqs)
        for i, f in enumerate(freqs):
            p = physics.calc_tensor_space(
                self.room, self.spk1, self.spk2, self.num_src,
                self.corr_mode, float(f),
                grid_size=self.grid_size,
                room_scatter=self.room_scatter,
            )
            # 2-sigma clip per frequency so a single extreme cell cannot dominate.
            mean, std = float(p.mean()), float(p.std())
            spatial_maxes.append(min(float(p.max()), mean + 2.0 * std))
            self.progress.emit(int((i + 1) / n * 100))

        if spatial_maxes:
            # Median-centred dB reference: take the median of the per-frequency
            # maxima in dB and convert it back to a linear pressure. The renderer
            # builds a +/- db_range window around this median.
            maxes_db = 20.0 * np.log10(np.clip(spatial_maxes, 1e-9, None))
            median_pressure = float(10.0 ** (np.median(maxes_db) / 20.0))
        else:
            median_pressure = 1.0
        self.finished.emit(median_pressure, 20.0)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Standing Wave Viewer")
        self.setFixedSize(WIN_W, WIN_H)
        self.setFont(mono(10))

        # Apply any persisted settings BEFORE building the panels: the 3D grid
        # size and the 2D frequency axis are read from config at construction.
        load_settings()

        # Full-band scaling state.
        #   _global_max    -- approximate-mode linear reference (None = off/none)
        #   _calib_median  -- accurate-mode linear median reference (Calibrate)
        #   _calib_db_range-- accurate-mode +/- dB half-window (fixed at 20.0)
        #   _calib_accurate-- True once a Calibrate sweep has populated the median
        #   _calib_worker  -- the running CalibWorker (if any)
        self._global_max = None
        self._calib_median = None
        self._calib_db_range = 20.0
        self._calib_accurate = False
        self._calib_worker = None

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

        # Populate the Schroeder-frequency label from the startup state.
        self._update_schroeder_display()

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
        self.source_combo.setFont(mono(9))
        mode_lay.addWidget(self.source_combo, 0, 1)

        mode_lay.addWidget(QLabel("Phase correction"), 1, 0)
        self.phase_combo = QComboBox()
        self.phase_combo.addItems(
            ["Uncorrected", "Global cancel", "True complex field"]
        )
        self.phase_combo.setFont(mono(9))
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
        # Let any in-flight calibration sweep finish so the QThread is not
        # destroyed while still running.
        if self._calib_worker is not None:
            self._calib_worker.wait()
            self._calib_worker = None
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
    # CONTROLLER: Schroeder frequency estimate
    # ------------------------------------------------------------------
    def _update_schroeder_display(self, *_):
        """Recompute the Schroeder-frequency estimate from the current room
        dimensions and per-wall reflection coefficients, then update the label.

        Cheap pure arithmetic (no physics field computation), so this is wired to
        ``valueChanged`` and runs live while sliders are dragged. Accepts/ignores
        any positional arg so it can connect straight to a slider signal."""
        fs = physics.schroeder_frequency(
            self.room.x.value(), self.room.y.value(), self.room.z.value(),
            {name: s.value() for name, s in self.wall_sliders.items()},
        )
        if fs <= 0.0:
            self.schroeder_lbl.setText("Est. Schroeder: —")
        else:
            self.schroeder_lbl.setText(f"Est. Schroeder: ~{fs:.0f} Hz")

    # ------------------------------------------------------------------
    # CONTROLLER: 3D pressure field
    # ------------------------------------------------------------------
    def _wall_reflection(self):
        """Per-axis reflection coefficient = mean of the two opposing walls
        (matches the original Streamlit model)."""
        w = self.wall_sliders
        Rx = (w[constants.WALL_LEFT].value() + w[constants.WALL_RIGHT].value()) / 2.0
        Ry = (w[constants.WALL_FRONT].value() + w[constants.WALL_BACK].value()) / 2.0
        Rz = (w[constants.WALL_FLOOR].value() + w[constants.WALL_CEILING].value()) / 2.0
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
        """Map the UI combo label to the token physics.py matches."""
        label = self.phase_combo.currentText().lower()
        if "complex" in label:
            return constants.CorrMode.TRUE_COMPLEX
        if "cancel" in label:
            return constants.CorrMode.GLOBAL_CANCEL
        return constants.CorrMode.UNCORRELATED

    def _num_src(self):
        """Active source count (1 or 2) from the Source combo."""
        return 2 if self.source_combo.currentText() == "2" else 1

    def _physics_snapshot(self):
        """Bundle the current UI state into the parameter set shared by the 3D
        field, the 1D response, and the full-band calibration sweep. Centralises
        the room/position/source/phase/scatter reads so call sites can't drift."""
        return PhysicsSnapshot(
            room=self._current_room(),
            spk1=self._pos(self.spk1),
            spk2=self._pos(self.spk2),
            mic=self._pos(self.mic),
            num_src=self._num_src(),
            corr=self._corr_mode(),
            room_scatter=self.room_scatter.value(),
        )

    def _refresh(self, recompute_response):
        """Refresh the 3D field and the 2D plots from the current UI state.

        The 3D volume always recomputes (it shows the field at the selected
        frequency). For the 2D plots, ``recompute_response`` controls whether the
        expensive 1D frequency-response curve is recomputed (geometry change) or
        only the marker line is moved (frequency change) -- the curve itself is
        frequency-independent.
        """
        s = self._physics_snapshot()
        room, spk1, spk2, mic = s.room, s.spk1, s.spk2, s.mic
        num_src, corr, room_scatter = s.num_src, s.corr, s.room_scatter
        freq = self.freq_slider.value()
        listening_area = self.listening_area.value()

        mode_freqs = None
        if self.show_modes_chk.isChecked():
            mode_freqs = [f for f, _, _ in physics.calc_room_modes(room)]

        # Full-band scaling normalization reference (only when the mode is ON):
        #   accurate    -> median-centred +/- dB window (calib_median/db_range)
        #   approximate -> single linear global_max
        #   otherwise   -> all None -> default per-frequency normalization.
        global_max = None
        calib_median = None
        calib_db_range = self._calib_db_range
        if self.fullband_chk.isChecked():
            if self._calib_accurate and self._calib_median is not None:
                calib_median = self._calib_median
            elif self._global_max is not None:
                global_max = self._global_max

        self.render3d.update_mesh(
            room, spk1, spk2, mic, num_src, corr, freq,
            room_scatter=room_scatter, global_max=global_max,
            calib_median=calib_median, calib_db_range=calib_db_range,
        )
        self.plot2d.update_all(
            room, spk1, spk2, mic, num_src, corr, freq,
            recompute_response=recompute_response,
            listening_area=listening_area,
            room_scatter=room_scatter,
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
        and the 2D response curve exactly once, regardless of the toggle.

        A committed change is a geometry change, so any Full-band calibration is
        now stale. Recompute the response FIRST (so the 1D curve is fresh), then
        invalidate -- the approximate reference is read from that fresh curve."""
        self._refresh(recompute_response=True)
        self._invalidate_calibration()

    def _on_display_param_committed(self, *_):
        """Committed change that affects only the 2D display or mode overlay,
        not the 3D pressure field (calc_tensor_space ignores these parameters).

        Refreshes and recomputes the 2D response, but does NOT touch the
        Full-band scaling cache -- it remains valid across these changes."""
        self._refresh(recompute_response=True)

    # ------------------------------------------------------------------
    # CONTROLLER: Full-band scaling
    # ------------------------------------------------------------------
    def _invalidate_calibration(self):
        """Discard the cached full-band reference because geometry changed.

        Any in-flight Calibrate sweep is abandoned (its snapshot is now stale).
        When Full-band is OFF the cache is cleared silently; when ON we
        immediately recompute the lightweight approximate reference and redraw.
        """
        # Abandon a running sweep: dropping the reference makes its finished
        # handler ignore the (now stale) result.
        if self._calib_worker is not None:
            self._calib_worker = None
            self.calib_progress_lbl.setText("")

        self._global_max = None
        self._calib_median = None
        self._calib_db_range = 20.0
        self._calib_accurate = False
        self.calibrate_btn.setText("Calibrate")
        # Re-enable Calibrate only if Full-band scaling is ON.
        self.calibrate_btn.setEnabled(self.fullband_chk.isChecked())
        self.fullband_chk.setEnabled(True)
        # If Full-band is ON, immediately recompute approximate mode.
        if self.fullband_chk.isChecked():
            self._compute_approx_global_max()
            self._refresh(recompute_response=False)

    def _compute_approx_global_max(self):
        """Lightweight approximate full-band reference (no background sweep).

        Read the peak of the already-computed 1D response curve, compute ONE 3D
        field at that frequency, and use its spatial max as the normalization
        reference. Marks the cache as approximate (not Calibrated)."""
        db = self.plot2d._db
        freqs = self.plot2d._freqs
        if db is None or freqs is None or len(freqs) == 0:
            self._global_max = None
            self._calib_median = None
            self._calib_accurate = False
            return
        # _db is in dB -> convert back to linear amplitude to find the true peak.
        linear = 10 ** (np.asarray(db) / 20.0)
        peak_freq = float(freqs[int(np.argmax(linear))])

        s = self._physics_snapshot()
        field = physics.calc_tensor_space(
            s.room, s.spk1, s.spk2, s.num_src, s.corr, peak_freq,
            grid_size=self.render3d.grid_size, room_scatter=s.room_scatter,
        )
        self._global_max = float(field.max())
        self._calib_median = None
        self._calib_accurate = False

    def _on_fullband_toggled(self, checked):
        """Enter/leave Full-band scaling immediately.

        ON: reuse a cached reference if geometry is unchanged (accurate ->
        "Calibrated ✓" disabled; approximate -> Calibrate enabled), otherwise
        compute the approximate reference. OFF: revert to per-frequency
        normalization while keeping the cache for a later re-enable."""
        if checked:
            if self._calib_accurate and self._calib_median is not None:
                self.calibrate_btn.setText("Calibrated ✓")
                self.calibrate_btn.setEnabled(False)
            elif self._global_max is not None:
                self.calibrate_btn.setText("Calibrate")
                self.calibrate_btn.setEnabled(True)
            else:
                self._compute_approx_global_max()
                self.calibrate_btn.setText("Calibrate")
                self.calibrate_btn.setEnabled(True)
        else:
            # Keep the cached values (geometry unchanged) so re-enabling reuses
            # them; just disable Calibrate while off.
            self.calibrate_btn.setEnabled(False)
        self._refresh(recompute_response=False)

    def _on_calibrate_clicked(self):
        """Launch the accurate full-band sweep in a background QThread.

        Snapshots all physics parameters NOW so mid-computation UI changes can't
        corrupt the cache. Disables the checkbox + button to block re-entrancy."""
        if self._calib_worker is not None:
            return  # already running

        s = self._physics_snapshot()
        worker = CalibWorker(
            s.room, s.spk1, s.spk2, s.num_src, s.corr, s.room_scatter,
            self.render3d.grid_size,
        )
        self._calib_worker = worker
        worker.progress.connect(self._on_calib_progress)
        worker.finished.connect(
            lambda med, dbr, w=worker: self._on_calib_finished(med, dbr, w)
        )

        self.calibrate_btn.setText("Calculating...")
        self.calibrate_btn.setEnabled(False)
        self.fullband_chk.setEnabled(False)
        self.calib_progress_lbl.setText("Calibrating... 0%")
        worker.start()

    def _on_calib_progress(self, pct):
        self.calib_progress_lbl.setText(f"Calibrating... {pct}%")

    def _on_calib_finished(self, median, db_range, worker):
        """Apply the swept median-centred dB reference, unless this worker was
        abandoned (geometry changed mid-sweep -> a newer invalidation dropped our
        reference)."""
        if worker is not self._calib_worker:
            return
        self._calib_worker = None
        self._calib_median = median
        self._calib_db_range = db_range
        self._calib_accurate = True

        self.calib_progress_lbl.setText("")
        self.fullband_chk.setEnabled(True)
        self.calibrate_btn.setText("Calibrated ✓")
        self.calibrate_btn.setEnabled(False)
        self._refresh(recompute_response=False)

    def _on_render_mode_changed(self, *_):
        """Switch the 3D view between volume and contour rendering.

        The pressure field and the 2D response are unchanged, so this is a
        lightweight 3D-only path: it regenerates the iso-surfaces from the
        EXISTING field and flips actor visibility (no physics recompute, no 2D
        redraw). Camera is preserved -- ``set_render_mode`` only does
        SetVisibility + in-place copy_from."""
        self.render3d.set_render_mode(self.contour_chk.isChecked(), self._num_src())

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

        # Gather current state. The CSV layout lives in csv_io.write_export.
        s = self._physics_snapshot()
        walls = {name: self.wall_sliders[name].value() for name in csv_io.WALL_NAMES}
        try:
            csv_io.write_export(
                path,
                room=s.room, spk1=s.spk1, spk2=s.spk2, mic=s.mic,
                num_src=s.num_src, walls=walls,
                freq=self.freq_slider.value(), corr_mode=s.corr,
                room_scatter=s.room_scatter,
                listening_area=self.listening_area.value(),
                response_freqs=self.plot2d._freqs, response_db=self.plot2d._db,
                modes=physics.calc_room_modes(s.room),
            )
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write file:\n{exc}")
            return

        QMessageBox.information(self, "Export complete", f"Data exported to:\n{path}")

    # ------------------------------------------------------------------
    # CONTROLLER: data import
    # ------------------------------------------------------------------
    def on_import_clicked(self):
        """Restore all room/simulation parameters from a previously exported CSV.

        Reads the ``[Parameters]`` section (ignoring ``[Frequency Response]`` and
        ``[Room Modes]``), validates that every required value is present and
        well-formed, then applies them to the UI in one batch with a single
        recompute. If anything is missing or malformed the import is aborted
        before any state is touched and an error dialog is shown -- no partial
        state is ever applied.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Data", "", "CSV files (*.csv)"
        )
        if not path:
            # User cancelled the dialog -> nothing to do.
            return

        try:
            values = csv_io.load_parameters(path)
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.critical(
                self, "Import failed",
                f"Could not import parameters from:\n{path}\n\n{exc}",
            )
            return

        # Parsing succeeded and every required value is valid -> safe to apply.
        self._apply_imported_params(values)
        QMessageBox.information(
            self, "Import complete", f"Parameters imported from:\n{path}"
        )

    def _import_set_slider(self, slider, value):
        """Set a LabeledSlider value, clamping to its current ``[_vmin, _vmax]``
        range first. A value that was valid when exported may fall outside the
        current config limits -- that is a warning, not a failure."""
        clamped = max(slider._vmin, min(slider._vmax, value))
        if clamped != value:
            print(
                f"[import] value {value} out of range "
                f"[{slider._vmin}, {slider._vmax}] -> clamped to {clamped}"
            )
        slider.setValue(clamped)

    def _apply_imported_params(self, v):
        """Apply validated parameters to the UI in one batch, then recompute once.

        All affected widget signals are blocked while values are set so no
        per-parameter recompute / symmetry / clamp cascade fires. Room dimensions
        are applied first (and position-slider maxima re-synced) so speaker/mic
        values are clamped against the imported room, not the previous one. After
        the batch, derived state is rebuilt and a single refresh + calibration
        invalidation is triggered."""
        sliders = [
            self.room.x, self.room.y, self.room.z,
            self.spk1.x, self.spk1.y, self.spk1.z,
            self.spk2.x, self.spk2.y, self.spk2.z,
            self.mic.x, self.mic.y, self.mic.z,
            self.freq_slider, self.room_scatter, self.listening_area,
        ] + list(self.wall_sliders.values())
        combos = [self.source_combo, self.phase_combo]

        for w in sliders + combos:
            w.blockSignals(True)
        try:
            # Room dimensions FIRST, then re-cap position sliders so the
            # speaker/mic values below clamp against the imported room.
            self._import_set_slider(self.room.x, v["Lx"])
            self._import_set_slider(self.room.y, v["Ly"])
            self._import_set_slider(self.room.z, v["Lz"])
            self._sync_position_limits()

            self._import_set_slider(self.spk1.x, v["spk1"][0])
            self._import_set_slider(self.spk1.y, v["spk1"][1])
            self._import_set_slider(self.spk1.z, v["spk1"][2])

            self._import_set_slider(self.mic.x, v["mic"][0])
            self._import_set_slider(self.mic.y, v["mic"][1])
            self._import_set_slider(self.mic.z, v["mic"][2])

            for name, slider in self.wall_sliders.items():
                self._import_set_slider(slider, v["walls"][name])

            self._import_set_slider(self.freq_slider, v["freq"])
            self._import_set_slider(self.room_scatter, v["room_scatter"])
            self._import_set_slider(self.listening_area, v["listening_area"])

            self.source_combo.setCurrentIndex(0 if v["num_src"] == 1 else 1)
            self.phase_combo.setCurrentIndex(v["phase_index"])

            if v["num_src"] == 2 and "spk2" in v:
                self._import_set_slider(self.spk2.x, v["spk2"][0])
                self._import_set_slider(self.spk2.y, v["spk2"][1])
                self._import_set_slider(self.spk2.z, v["spk2"][2])
        finally:
            for w in sliders + combos:
                w.blockSignals(False)

        # Rebuild derived state the blocked signals would normally maintain,
        # then recompute the 3D field + 2D plots exactly once.
        self._update_source_state()
        self._sync_position_limits()
        self._sync_symmetry()
        self.update_room_modes()
        self._update_schroeder_display()
        self._refresh(recompute_response=True)
        self._invalidate_calibration()

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
        those explicitly, retune the frequency slider bounds to the unified
        MIN_FREQ/MAX_FREQ, refresh the room-modes table (depends on speed of
        sound / max frequency), then recompute the 3D + 2D views once."""
        P = app_config.PhysicalConfig
        room = self._current_room()
        self.render3d.set_grid_size(app_config.SimResolution.GRID_SIZE_NORMAL, room)

        # Retune the frequency slider to the new bounds without restart. Raise
        # the ceiling before the floor so the tick range never collapses through
        # an intermediate state where a rising floor passes the old ceiling.
        self.freq_slider.setMaxValue(P.MAX_FREQ)
        self.freq_slider.setMinValue(P.MIN_FREQ)

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

        # Schroeder-frequency estimate: cheap arithmetic, so update live on any
        # room-dimension or wall-reflection change (valueChanged, not committed).
        for axis in (self.room.x, self.room.y, self.room.z):
            axis.valueChanged.connect(self._update_schroeder_display)
        for slider in self.wall_sliders.values():
            slider.valueChanged.connect(self._update_schroeder_display)

        # Advanced-acoustics: room_scatter feeds calc_tensor_space (geometry
        # change -> invalidates calibration); listening_area only affects the
        # 1D response curve and never reaches the 3D field (display-only).
        self.room_scatter.valueChanged.connect(self._on_param_changed)
        self.room_scatter.committed.connect(self._on_param_committed)
        self.listening_area.valueChanged.connect(self._on_param_changed)
        self.listening_area.committed.connect(self._on_display_param_committed)

        # Combos are discrete commits -> recompute immediately.
        self.source_combo.currentIndexChanged.connect(self._on_param_committed)
        self.phase_combo.currentIndexChanged.connect(self._on_param_committed)

        self.reset_view_btn.clicked.connect(self._on_reset_view)

        # The 2D-graph toggle only controls the mode-frequency overlay on the 2D
        # plot; it does not affect the 3D field -> display-only handler.
        self.show_modes_chk.toggled.connect(self._on_display_param_committed)

        # Full-band scaling: toggle switches normalization mode immediately;
        # Calibrate launches the accurate background sweep.
        self.fullband_chk.toggled.connect(self._on_fullband_toggled)
        self.calibrate_btn.clicked.connect(self._on_calibrate_clicked)

        # 3D render-mode toggle: lightweight 3D-only path (no physics / no 2D).
        self.contour_chk.toggled.connect(self._on_render_mode_changed)

        # Export current state to CSV.
        self.export_btn.clicked.connect(self.on_export_clicked)

        # Import room parameters from a previously exported CSV.
        self.import_btn.clicked.connect(self.on_import_clicked)

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
        # Discrete commit -> wired in _wire_3d_signals.
        # (Spatial Smoothing moved to the right-panel "Listening Area" slider.)
        smooth_row = QHBoxLayout()
        smooth_row.setContentsMargins(0, 0, 0, 0)
        # Read-only Schroeder-frequency estimate, sitting just below the
        # frequency-response curve. Updated live from room dims + wall sliders.
        self.schroeder_lbl = QLabel("Est. Schroeder: —")
        self.schroeder_lbl.setFont(mono(9))
        self.schroeder_lbl.setStyleSheet("color: #aaaaaa;")
        smooth_row.addWidget(self.schroeder_lbl)
        smooth_row.addStretch()
        self.show_modes_chk = QCheckBox("Show room modes")
        self.show_modes_chk.setFont(mono(9, bold=True))
        smooth_row.addWidget(self.show_modes_chk)
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

        # Frequency slider (1 Hz steps). Bounds come from the unified config
        # (single source of truth) so they track Settings changes; the default
        # value is clamped into range in case MIN_FREQ was raised above it.
        P = app_config.PhysicalConfig
        freq_default = min(max(40.0, P.MIN_FREQ), P.MAX_FREQ)
        self.freq_slider = LabeledSlider(
            "Frequency (Hz)", P.MIN_FREQ, P.MAX_FREQ, 1.0, value=freq_default
        )
        blay.addWidget(self.freq_slider)

        # Controls row: Full-band scaling (left) + render toggles (right)
        controls_row = QHBoxLayout()
        controls_row.setContentsMargins(0, 0, 0, 0)

        self.fullband_chk = QCheckBox("Full-band scaling")
        self.fullband_chk.setFont(mono(9, bold=True))
        controls_row.addWidget(self.fullband_chk)

        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setFont(mono(9, bold=True))
        self.calibrate_btn.setEnabled(False)
        controls_row.addWidget(self.calibrate_btn)

        self.calib_progress_lbl = QLabel("")
        self.calib_progress_lbl.setFont(mono(9))
        controls_row.addWidget(self.calib_progress_lbl)

        controls_row.addStretch()

        self.contour_chk = QCheckBox("Contour Mode")
        self.contour_chk.setFont(mono(9, bold=True))
        controls_row.addWidget(self.contour_chk)

        self.dynamic_chk = QCheckBox("Dynamic update")
        self.dynamic_chk.setFont(mono(9, bold=True))
        controls_row.addWidget(self.dynamic_chk)

        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.setFont(mono(9, bold=True))
        controls_row.addWidget(self.reset_view_btn)

        blay.addLayout(controls_row)

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

        # 3 rows x 2 columns: Left/Right, Front/Back, Floor/Ceiling
        wall_pairs = constants.WALL_PAIRS
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

        # --- Advanced acoustics --------------------------------------
        # Two continuous sliders feeding the physics engine:
        #   Room Scatter    -> order-dependent modal damping (calc_gamma)
        #   Listening Area  -> mic-cube RMS averaging of the 1D response
        adv_box = QGroupBox("Advanced Acoustics")
        adv_box.setFont(mono(10, bold=True))
        adv_lay = QHBoxLayout(adv_box)
        adv_lay.setSpacing(8)
        self.room_scatter = LabeledSlider("Room Scatter", 0.0, 1.0, 0.05, value=0.0)
        self.listening_area = LabeledSlider("Listening Area (m)", 0.0, 0.5, 0.05, value=0.0)
        adv_lay.addWidget(self.room_scatter)
        adv_lay.addWidget(self.listening_area)
        lay.addWidget(adv_box)

        # --- Room modes table ----------------------------------------
        modes_box = QGroupBox("Room modes")
        modes_box.setFont(mono(9, bold=True))
        modes_lay = QVBoxLayout(modes_box)
        self.modes_table = QTableWidget(16, 3)
        self.modes_table.setFont(mono(9))
        self.modes_table.setHorizontalHeaderLabels(
            ["Hz", "Modes (x, y, z)", "L (m)"]
        )
        self.modes_table.verticalHeader().setVisible(False)
        self.modes_table.horizontalHeader().setFont(mono(9, bold=True))
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
        # Three buttons in one row: [Export data] [Import data] [Settings].
        # Export and Settings are slightly smaller than before to leave room
        # for the new Import button while keeping all three the same size.
        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export data")
        self.import_btn = QPushButton("Import data")
        self.settings_btn = QPushButton("Settings")
        for btn in (self.export_btn, self.import_btn, self.settings_btn):
            btn.setFont(mono(9, bold=True))
            btn.setFixedHeight(34)
            btn_row.addWidget(btn)
        lay.addLayout(btn_row)

        return panel


def main():
    app = QApplication(sys.argv)
    app.setFont(mono(10))
    win = MainWindow()
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass
    win.show()
    win.raise_()
    win.activateWindow()
    win.setWindowState(win.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
 