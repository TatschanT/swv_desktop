import numpy as np

class AppDefaults:
    # Room dimensions
    LX = 3.5
    LY = 2.6
    LZ = 2.4

    # Room size limit
    ROOM_MIN_L = 1.0
    ROOM_MAX_L_XY = 10.0
    ROOM_MAX_L_Z = 5.0

    # speaker and mic position
    SPK_X = 0.5
    SPK_Y = 0.5
    SPK_Z = 0.5
    SPK2_X = 3.0
    SPK2_Y = 0.5
    SPK2_Z = 0.5
    MIC_X = 1.75
    MIC_Y = 1.3
    MIC_Z = 1.2

    # refrection coefficients
    R = 0.80

    # 3D view hight
    CHART_HEIGHT_NORMAL = 500
    CHART_HEIGHT_LARGE = 800

class PhysicalConfig:
    SPEED_OF_SOUND = 343.0

    # Upper limit of the calculation frequency
    MAX_CALC_FREQ = 250.0

    # Magic numbers for calculating the decay coefficient (gamma)
    GAMMA_ZERO_SUM = 5.0
    GAMMA_BASE = 3.0
    GAMMA_SCALE = 40.0

    # Scale factor for resonance amplitude
    RESONANCE_SCALING = 50.0

    # Lower clipping threshold for decibel conversion
    DB_CLIP_MIN = 1e-10

class SimResolution:
    # Calculation range for 1D frequency response (Hz)
    FREQ_1D_START = 20
    FREQ_1D_END = 201
    FREQ_1D_STEP = 1

    # Calculation range of 3D spatial tensors (Normal mode)
    FREQ_3D_START_NORMAL = 20
    FREQ_3D_END_NORMAL = 205
    FREQ_3D_STEP_NORMAL = 5
    GRID_SIZE_NORMAL = 25

    # Computation range of the 3D spatial tensor (High-resolution mode)
    FREQ_3D_START_HIGH = 20
    FREQ_3D_END_HIGH = 201
    FREQ_3D_STEP_HIGH = 2
    GRID_SIZE_HIGH = 37

    # Minor displacement of the microphone position during smoothing (m)
    SMOOTHING_OFFSET = 0.1