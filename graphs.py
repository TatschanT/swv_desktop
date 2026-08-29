"""View layer for the embedded 2D Matplotlib plots.

``Plot2DWidget`` is a Qt-embeddable canvas holding two subplots:
  * left  - top-down (XY plane) room layout with speaker / mic markers
  * right - 1D frequency response (dB) with a marker line at the current freq

The expensive part is the 1D response (``physics.compute_f_response_1d``); it is
recomputed only when the geometry/sources change. When just the frequency slider
moves, only the vertical marker line is repositioned (no physics recompute).
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.patches import Rectangle

import config as app_config
import constants
import physics

# Dark palette to match the rest of the UI.
BG = "#15191e"
FG = "#cfd6df"
GRID = "#333b46"
SPK_COLOR = constants.SPK_COLOR   # blue square (shared with the 3D view)
MIC_COLOR = constants.MIC_COLOR   # bright white
RESP_COLOR = "#4ade80"    # green response curve
MARK_COLOR = "#f43f5e"    # red current-frequency line

# Fixed dB window for the response plot (normalized to 0 dB max, with headroom)
# so the Y-axis never rescales/jumps as the curve changes.
DB_MIN = -25.0
DB_MAX = 5.0
ANNOT_Y = 3.5            # vertical placement of the dB readout near the top


class Plot2DWidget(FigureCanvasQTAgg):
    """Two side-by-side Matplotlib plots embedded in the PySide6 layout."""

    def __init__(self, parent=None):
        self.fig = Figure(figsize=(9, 3.4), facecolor=BG)
        super().__init__(self.fig)
        if parent is not None:
            self.setParent(parent)

        # One gridspec carrying BOTH the width split and the margins, so there
        # is no second place holding the same numbers (this replaced a pair of
        # add_subplot(1, 2, n) calls plus a separate subplots_adjust).
        #
        # 4:6 rather than 1:1 -- the frequency response is the panel that
        # actually rewards width (it gained ~20 %), while the top-down view is
        # letterboxed by set_aspect("equal") anyway, so a squarer slot wastes
        # less. The room outline keeps its true proportions either way.
        gs = self.fig.add_gridspec(
            1, 2, width_ratios=[4, 6],
            left=0.07, right=0.97, top=0.88, bottom=0.16, wspace=0.28,
        )
        self.ax_top = self.fig.add_subplot(gs[0, 0])
        self.ax_freq = self.fig.add_subplot(gs[0, 1])

        # Frequency sample axis, derived from config so the Settings dialog can
        # change it. Precomputed and reused on every recompute until rebuilt.
        self._freqs = None
        self.rebuild_freqs()
        self._marker = None   # the vertical "current frequency" line
        self._annot = None    # the "-x.x dB" text next to the marker
        self._db = None       # last computed response curve (for marker lookup)

    def rebuild_freqs(self):
        """(Re)build the frequency sample axis from the unified config bounds.

        Bounds come from ``PhysicalConfig.MIN_FREQ`` / ``MAX_FREQ`` (the single
        source of truth) and the step from ``SimResolution.FREQ_1D_STEP``. The
        ``+ step`` makes the range inclusive of MAX_FREQ, and ``max(...)``
        guarantees at least two points so a degenerate MIN>=MAX never yields an
        empty curve. Call this after the Settings dialog changes any of them.
        """
        p = app_config.PhysicalConfig
        step = app_config.SimResolution.FREQ_1D_STEP
        start = p.MIN_FREQ
        end = max(p.MAX_FREQ, start + step)
        self._freqs = np.arange(start, end + step, step)

    # -- styling helper --------------------------------------------------
    @staticmethod
    def _style(ax, title, xlabel, ylabel):
        ax.set_facecolor(BG)
        ax.set_title(title, color=FG, fontsize=10, fontweight="bold")
        ax.set_xlabel(xlabel, color=FG, fontsize=8)
        ax.set_ylabel(ylabel, color=FG, fontsize=8)
        ax.tick_params(colors=FG, labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(GRID)

    # -- left subplot: top-down room layout ------------------------------
    def update_top_down(self, room, spk1, spk2, mic, num_src):
        ax = self.ax_top
        ax.clear()
        self._style(ax, "Top-Down View (XY)", "Width  X [m]", "Depth  Y [m]")

        Lx, Ly = room.Lx, room.Ly

        # Room boundary.
        ax.add_patch(Rectangle((0, 0), Lx, Ly, fill=False, edgecolor=FG, lw=1.6))

        # 1/4, 1/2, 3/4 subdivision guide lines.
        for frac in (0.25, 0.5, 0.75):
            ax.axvline(frac * Lx, color=GRID, ls="--", lw=0.8)
            ax.axhline(frac * Ly, color=GRID, ls="--", lw=0.8)

        # Equipment markers + Z-height labels.
        def marker(p, color, shape, label):
            ax.scatter([p.x], [p.y], c=color, marker=shape, s=70,
                       edgecolors="white", linewidths=0.8, zorder=5)
            ax.annotate(f"{label}\nZ={p.z:.2f}", (p.x, p.y),
                        textcoords="offset points", xytext=(6, 6),
                        color=FG, fontsize=7, zorder=6)

        marker(spk1, SPK_COLOR, "s", "Spk1" if num_src == 2 else "Spk")
        if num_src == 2:
            marker(spk2, SPK_COLOR, "s", "Spk2")
        marker(mic, MIC_COLOR, "o", "Mic")

        ax.set_xlim(0, Lx)
        ax.set_ylim(0, Ly)
        ax.set_aspect("equal", adjustable="box")

    # -- right subplot: 1D frequency response ----------------------------
    def update_freq_response(self, room, spk1, spk2, mic, num_src, corr_mode, current_freq,
                             listening_area=0.0, room_scatter=0.0, mode_freqs=None):
        ax = self.ax_freq
        ax.clear()
        self._style(ax, "Frequency Response", "Frequency [Hz]", "Relative SPL [dB]")

        db = physics.compute_f_response_1d(
            room, spk1, spk2, mic, num_src, corr_mode, self._freqs,
            listening_area=listening_area, room_scatter=room_scatter,
        )
        self._db = db

        # Room-mode guide lines - subtle vertical references drawn behind
        # the response curve (zorder=1) and the red marker (zorder=2).
        if mode_freqs:
            fmin, fmax = self._freqs[0], self._freqs[-1]
            for mf in mode_freqs:
                if fmin <= mf <= fmax:
                    ax.axvline(mf, color="#777", lw=0.6, alpha=0.4, zorder=1)

        ax.plot(self._freqs, db, color=RESP_COLOR, lw=1.5)
        ax.grid(True, color=GRID, lw=0.5, alpha=0.5)

        # Current-frequency marker line (kept as a handle for cheap updates).
        self._marker = ax.axvline(current_freq, color=MARK_COLOR, lw=1.4)

        # Live dB readout next to the marker line.
        db_val = float(np.interp(current_freq, self._freqs, db))
        self._annot = ax.text(
            current_freq, ANNOT_Y, f"{db_val:.1f} dB",
            color=MARK_COLOR, fontsize=8, fontweight="bold",
            ha=self._annot_ha(current_freq), va="top", zorder=6,
        )

        # X-axis spans the unified config bounds directly (single source of
        # truth), so it stays in sync with the freq slider after a Settings
        # change. Fixed Y-axis so the plot never rescales/jumps.
        ax.set_xlim(app_config.PhysicalConfig.MIN_FREQ, app_config.PhysicalConfig.MAX_FREQ)
        ax.set_ylim(DB_MIN, DB_MAX)

    def _annot_ha(self, freq):
        # Flip text alignment near the right edge so the label never clips off.
        mid = 0.5 * (self._freqs[0] + self._freqs[-1])
        return "right" if freq > mid else "left"

    def update_freq_marker(self, current_freq):
        """Cheap update: move ONLY the vertical line and refresh the dB readout
        (interpolated from the cached curve) -- no physics recompute."""
        if self._marker is not None:
            self._marker.set_xdata([current_freq, current_freq])
        if self._annot is not None and self._db is not None:
            db_val = float(np.interp(current_freq, self._freqs, self._db))
            self._annot.set_text(f"{db_val:.1f} dB")
            self._annot.set_position((current_freq, ANNOT_Y))
            self._annot.set_ha(self._annot_ha(current_freq))
        self.draw_idle()

    # -- combined entry point --------------------------------------------
    def update_all(self, room, spk1, spk2, mic, num_src, corr_mode, current_freq,
                   recompute_response=True, listening_area=0.0, room_scatter=0.0, mode_freqs=None):
        """Update the 2D plots.

        recompute_response=True  -> redraw layout + recompute the response curve
                                    (use when geometry / sources / walls change).
        recompute_response=False -> only move the frequency marker line
                                    (use when ONLY the frequency slider moves).
        ``listening_area``, ``room_scatter`` and ``mode_freqs`` are forwarded to
        the response recompute (ignored when only the marker moves).
        """
        if recompute_response:
            self.update_top_down(room, spk1, spk2, mic, num_src)
            self.update_freq_response(room, spk1, spk2, mic, num_src, corr_mode, current_freq,
                                      listening_area=listening_area, room_scatter=room_scatter,
                                      mode_freqs=mode_freqs)
            self.draw()
        else:
            self.update_freq_marker(current_freq)
