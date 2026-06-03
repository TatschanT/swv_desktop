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
    CONTOUR_STD_DEV_LIMIT = 2.0
    CONTOUR_VALLEY_FRAC = 0.3
    CONTOUR_PEAK_FRAC = 0.7
    CONTOUR_LEVELS_PER_BAND = 7

class PhysicalConfig:
    """Constants for the physics computation."""
    SPEED_OF_SOUND = 343.0

    # Upper frequency limit for modes included in the calculation (Hz)
    MAX_CALC_FREQ = 250.0

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
    # 1D frequency-response calculation range (Hz)
    FREQ_1D_START = 20
    FREQ_1D_END = 201
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

    # Spatial smoothing (spatial averaging) settings.
    # The mic position is sampled over a cube of +/- SMOOTHING_RADIUS [m] with
    # SMOOTHING_SAMPLES points per axis, then RMS-averaged across all samples.
    # A larger radius averages over a wider region, smoothing sharp dips/peaks
    # more strongly so the effect is more visible; more samples make the
    # averaging smoother. (radius=0.3, samples=5 -> 5^3 = 125 sample points.)
    SMOOTHING_RADIUS = 0.3
    SMOOTHING_SAMPLES = 5
