import os
import sys


def get_resource_path(relative_path: str) -> str:
    """Absolute path to a bundled read-only asset (image, etc.).

    When running as a PyInstaller .exe, assets are extracted to sys._MEIPASS.
    In normal script mode, falls back to the current working directory.
    """
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, relative_path)


def get_user_data_path(filename: str) -> str:
    """Absolute path for a read/write user-data file (e.g., settings.json).

    In a frozen .exe, writes land next to the executable (not in _MEIPASS,
    which is deleted on exit). In script mode, uses the current directory.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.abspath(".")
    return os.path.join(base, filename)

class AppDefaults:
    """Application initial state and UI-related defaults."""
    # Room dimensions (initial values)
    LX = 3.5
    LY = 2.6
    LZ = 2.4

    # Room-dimension UI slider limits
    ROOM_MIN_L = 1.0
    ROOM_MAX_L_XY = 10.0
    ROOM_MAX_L_Z = 5.0

    # Equipment positions (initial values)
    SPK_X = 0.5
    SPK_Y = 0.5
    SPK_Z = 0.5
    SPK2_X = 3.0
    SPK2_Y = 0.5
    SPK2_Z = 0.5
    MIC_X = 1.75
    MIC_Y = 1.3
    MIC_Z = 1.2

    # Reflection coefficient (initial value)
    R = 0.80

    # Chart render sizes
    CHART_HEIGHT_NORMAL = 500
    CHART_HEIGHT_LARGE = 800

    # Contour ("Clear Visibility") 3D render mode -- statistical iso-surface
    # thresholds (ported from old_src/render.py "Statistical Scaling").
    # The robust value band is mean +/- CONTOUR_STD_DEV_LIMIT * std (clamped at
    # 0 below). Iso-surfaces are drawn ONLY in the bottom CONTOUR_VALLEY_FRAC of
    # that band (valleys) and the top (1 - CONTOUR_PEAK_FRAC) of it (peaks); the
    # middle band is deliberately skipped so the field is "see-through".
    # CONTOUR_LEVELS_PER_BAND iso-values are spread across each of the two bands.
    CONTOUR_STD_DEV_LIMIT = 1.5
    CONTOUR_VALLEY_FRAC = 0.30
    CONTOUR_PEAK_FRAC = 0.70
    CONTOUR_LEVELS_PER_BAND = 7

class PhysicalConfig:
    """Constants for the physics computation."""
    SPEED_OF_SOUND = 343.0

    # Unified frequency bounds (Hz) -- the SINGLE source of truth for both the
    # simulation (mode generation / cutoff) and the display (frequency slider
    # range + 2D plot X-axis). Editing these in the Settings dialog propagates
    # to the physics engine, the freq slider and the 2D plot without a restart.
    MIN_FREQ = 20.0
    MAX_FREQ = 250.0

    # Tuning constants for the damping coefficient (gamma) calculation
    GAMMA_ZERO_SUM = 5.0
    GAMMA_BASE = 3.0
    GAMMA_SCALE = 40.0

    # Resonance amplitude scale factor
    RESONANCE_SCALING = 50.0

    # Lower clipping bound applied before the decibel conversion
    DB_CLIP_MIN = 1e-10

class SimResolution:
    """Simulation resolution and performance settings."""
    # 1D frequency-response sample resolution (Hz). The START/END bounds now
    # live in PhysicalConfig.MIN_FREQ / MAX_FREQ (single source of truth); only
    # the sample step belongs here.
    FREQ_1D_STEP = 1

    # 3D spatial-tensor calculation range (normal mode)
    FREQ_3D_START_NORMAL = 20
    FREQ_3D_END_NORMAL = 205
    FREQ_3D_STEP_NORMAL = 5
    GRID_SIZE_NORMAL = 25

    # 3D spatial-tensor calculation range (high-resolution mode)
    FREQ_3D_START_HIGH = 20
    FREQ_3D_END_HIGH = 201
    FREQ_3D_STEP_HIGH = 2
    GRID_SIZE_HIGH = 37

    # Listening Area sampling resolution: mic-sample points per axis used by
    # compute_f_response_1d when the Listening Area slider is > 0. The mic is
    # sampled over a cube (half-width = the slider value in metres) with this
    # many points per axis, then RMS-averaged (5 -> 5^3 = 125 sample points).
    # The half-width is now driven live by the UI slider, so only the sample
    # count remains here as a fixed resolution/performance constant.
    SMOOTHING_SAMPLES = 5
