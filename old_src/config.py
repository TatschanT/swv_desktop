import numpy as np

class AppDefaults:
    """アプリケーションの初期状態やUIに関する設定"""
    # 部屋の寸法 (初期値)
    LX = 3.5
    LY = 2.6
    LZ = 2.4

    # 部屋の寸法のUIスライダー制限
    ROOM_MIN_L = 1.0
    ROOM_MAX_L_XY = 10.0
    ROOM_MAX_L_Z = 5.0

    # 機材の位置 (初期値)
    SPK_X = 0.5
    SPK_Y = 0.5
    SPK_Z = 0.5
    SPK2_X = 3.0
    SPK2_Y = 0.5
    SPK2_Z = 0.5
    MIC_X = 1.75
    MIC_Y = 1.3
    MIC_Z = 1.2

    # 反射係数 (初期値)
    R = 0.80

    # 描画サイズ
    CHART_HEIGHT_NORMAL = 500
    CHART_HEIGHT_LARGE = 800

class PhysicalConfig:
    """物理演算に関する定数"""
    SPEED_OF_SOUND = 343.0

    # 計算対象とするモードの周波数上限 (Hz)
    MAX_CALC_FREQ = 250.0

    # 減衰係数 (gamma) 計算用のマジックナンバー
    GAMMA_ZERO_SUM = 5.0
    GAMMA_BASE = 3.0
    GAMMA_SCALE = 40.0

    # 共振振幅のスケールファクター
    RESONANCE_SCALING = 50.0

    # デシベル変換時の下限クリッピング値
    DB_CLIP_MIN = 1e-10

class SimResolution:
    """シミュレーションの解像度やパフォーマンスに関する設定"""
    # 1D周波数特性の計算範囲 (Hz)
    FREQ_1D_START = 20
    FREQ_1D_END = 201
    FREQ_1D_STEP = 1

    # 3D空間テンソルの計算範囲 (通常モード)
    FREQ_3D_START_NORMAL = 20
    FREQ_3D_END_NORMAL = 205
    FREQ_3D_STEP_NORMAL = 5
    GRID_SIZE_NORMAL = 25

    # 3D空間テンソルの計算範囲 (高解像度モード)
    FREQ_3D_START_HIGH = 20
    FREQ_3D_END_HIGH = 201
    FREQ_3D_STEP_HIGH = 2
    GRID_SIZE_HIGH = 37

    # スムージング時のマイク位置の微小変位 (m)
    SMOOTHING_OFFSET = 0.1