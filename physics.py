import numpy as np
from dataclasses import dataclass
import config as app_config

# ==========================================
# Data Models
# ==========================================

@dataclass
class Position:
    x: float
    y: float
    z: float

@dataclass
class RoomConfig:
    Lx: float
    Ly: float
    Lz: float
    Rx: float
    Ry: float
    Rz: float

# ==========================================
# Room Modes (analysis helper)
# ==========================================

def calc_room_modes(room: RoomConfig, max_order: int = 4, max_freq: float = None) -> list:
    """Enumerate room eigenmodes and return them sorted by frequency ascending.

    Each entry is a tuple: (freq_hz, (nx, ny, nz), ref_length_m).

    The modal frequency is the classic rectangular-room formula
        fn = (c / 2) * sqrt((nx/Lx)^2 + (ny/Ly)^2 + (nz/Lz)^2)
    and the reference (half-wavelength) length is L = c / (2 * fn).
    """
    c = app_config.PhysicalConfig.SPEED_OF_SOUND
    if max_freq is None:
        max_freq = app_config.PhysicalConfig.MAX_CALC_FREQ

    if room.Lx <= 0 or room.Ly <= 0 or room.Lz <= 0:
        return []

    modes = []
    for nx in range(max_order + 1):
        for ny in range(max_order + 1):
            for nz in range(max_order + 1):
                if nx == 0 and ny == 0 and nz == 0:
                    continue
                fn = (c / 2.0) * np.sqrt(
                    (nx / room.Lx) ** 2 + (ny / room.Ly) ** 2 + (nz / room.Lz) ** 2
                )
                if fn > max_freq:
                    continue
                length = c / (2.0 * fn)
                modes.append((float(fn), (nx, ny, nz), float(length)))

    modes.sort(key=lambda m: m[0])
    return modes
# Normalization constant (Modal Norm) for volume integration of the wave equation
MODAL_NORMS = (0.25, 0.5, 1.0, 0.0) 
def get_modal_norm(nx, ny, nz):
    zeros_count = (nx == 0) + (ny == 0) + (nz == 0)
    return MODAL_NORMS[zeros_count]
# ==========================================
# Core Physics Engine
# ==========================================

def get_max_modes(room: RoomConfig) -> tuple:
    return (
        int(2.0 * room.Lx * app_config.PhysicalConfig.MAX_CALC_FREQ / app_config.PhysicalConfig.SPEED_OF_SOUND) + 2,
        int(2.0 * room.Ly * app_config.PhysicalConfig.MAX_CALC_FREQ / app_config.PhysicalConfig.SPEED_OF_SOUND) + 2,
        int(2.0 * room.Lz * app_config.PhysicalConfig.MAX_CALC_FREQ / app_config.PhysicalConfig.SPEED_OF_SOUND) + 2
    )

def calc_shape(n: int, pos: float, L: float, R: float) -> float:
    if n == 0: return pos * 0.0 + 1.0
    return np.sqrt(1 + R**2 + 2 * R * np.cos(2 * n * np.pi * pos / L)) / (1 + R)

def get_psi(n: int, pos: float, L: float, R: float) -> complex:
    if n == 0: return 1.0 + 0j
    theta = n * np.pi * pos / L

    # Symmetric radiation model referenced to the room center (L/2). This avoids
    # the asymmetry artifact in the True Complex Field mode that a one-sided
    # phase reference produced.
    beta = (1.0 - R) / (1.0 + R)
    # Symmetric scaler: -1 at x=0, 0 at the center, +1 at x=L.
    center_offset = (pos - L / 2.0) / (L / 2.0)

    return np.cos(theta) - 1j * beta * center_offset * np.sin(theta)

def calc_gamma(nx: int, ny: int, nz: int, room: RoomConfig) -> float:
    n_sum = nx + ny + nz
    if n_sum == 0: return app_config.PhysicalConfig.GAMMA_ZERO_SUM
    R_eff = (nx * room.Rx + ny * room.Ry + nz * room.Rz) / n_sum
    return app_config.PhysicalConfig.GAMMA_BASE + app_config.PhysicalConfig.GAMMA_SCALE * (1.0 - R_eff)

def compute_f_response_1d(room: RoomConfig, spk1: Position, spk2: Position, mic: Position, num_src: int, corr_mode: str, freqs_1d: np.ndarray, smoothing: bool = False) -> np.ndarray:
    Lx, Ly, Lz = room.Lx, room.Ly, room.Lz
    Rx, Ry, Rz = room.Rx, room.Ry, room.Rz
    sx, sy, sz = spk1.x, spk1.y, spk1.z
    sx2, sy2, sz2 = spk2.x, spk2.y, spk2.z

    if smoothing:
        # Sample a cube of mic positions of half-width SMOOTHING_RADIUS with
        # SMOOTHING_SAMPLES points per axis (so samples^3 points total), then
        # RMS-average the response over them. linspace includes the center when
        # the sample count is odd, so the un-smoothed point is still represented.
        radius = app_config.SimResolution.SMOOTHING_RADIUS
        samples = app_config.SimResolution.SMOOTHING_SAMPLES
        offsets = np.linspace(-radius, radius, samples)
        mic_positions = [(mic.x + dx, mic.y + dy, mic.z + dz) for dx in offsets for dy in offsets for dz in offsets]
    else:
        mic_positions = [(mic.x, mic.y, mic.z)]

    num_mics = len(mic_positions)
    mxs = np.clip([p[0] for p in mic_positions], 0, Lx)
    mys = np.clip([p[1] for p in mic_positions], 0, Ly)
    mzs = np.clip([p[2] for p in mic_positions], 0, Lz)

    max_nx, max_ny, max_nz = get_max_modes(room)

    if "True Complex Field" in corr_mode:
        P_complex_1_mics = np.zeros((num_mics, len(freqs_1d)), dtype=complex)
        P_complex_2_mics = np.zeros((num_mics, len(freqs_1d)), dtype=complex)

        for nx in range(max_nx):
            for ny in range(max_ny):
                for nz in range(max_nz):
                    if nx == 0 and ny == 0 and nz == 0: continue
                    fn = (app_config.PhysicalConfig.SPEED_OF_SOUND / 2.0) * np.sqrt((nx/Lx)**2 + (ny/Ly)**2 + (nz/Lz)**2)
                    if fn > app_config.PhysicalConfig.MAX_CALC_FREQ: continue
                    # modal energy weighting
                    mode_norm = get_modal_norm(nx, ny, nz)
                    gamma = calc_gamma(nx, ny, nz, room)
                    psi1 = get_psi(nx, sx, Lx, Rx) * get_psi(ny, sy, Ly, Ry) * get_psi(nz, sz, Lz, Rz)
                    if num_src == 2:
                        psi2 = get_psi(nx, sx2, Lx, Rx) * get_psi(ny, sy2, Ly, Ry) * get_psi(nz, sz2, Lz, Rz)

                    rec_psis = np.array([get_psi(nx, m_x, Lx, Rx) * get_psi(ny, m_y, Ly, Ry) * get_psi(nz, m_z, Lz, Rz) for m_x, m_y, m_z in zip(mxs, mys, mzs)])

                    for i, f_query in enumerate(freqs_1d):
                        res_complex = (app_config.PhysicalConfig.RESONANCE_SCALING / fn) / ((f_query - fn) + 1j * gamma)
                        P_complex_1_mics[:, i] += mode_norm * (psi1 * rec_psis * res_complex)
                        if num_src == 2:
                            P_complex_2_mics[:, i] += mode_norm * (psi2 * rec_psis * res_complex)

        tensor_1d_mics = np.abs(P_complex_1_mics + P_complex_2_mics)
        tensor_1d_avg = np.sqrt(np.mean(tensor_1d_mics ** 2, axis=0))

    else:
        tensor_1d_mics = np.zeros((num_mics, len(freqs_1d)))

        for nx in range(max_nx):
            for ny in range(max_ny):
                for nz in range(max_nz):
                    if nx == 0 and ny == 0 and nz == 0: continue
                    fn = (app_config.PhysicalConfig.SPEED_OF_SOUND / 2.0) * np.sqrt((nx/Lx)**2 + (ny/Ly)**2 + (nz/Lz)**2)
                    if fn > app_config.PhysicalConfig.MAX_CALC_FREQ: continue
                    # modal energy weighting
                    mode_norm = get_modal_norm(nx, ny, nz)
                    psi1 = get_psi(nx, sx, Lx, Rx) * get_psi(ny, sy, Ly, Ry) * get_psi(nz, sz, Lz, Rz)
                    if num_src == 2:
                        psi2 = get_psi(nx, sx2, Lx, Rx) * get_psi(ny, sy2, Ly, Ry) * get_psi(nz, sz2, Lz, Rz)
                        if "Global Cancel" in corr_mode:
                            exc = np.abs(psi1 + psi2) / 2.0
                        else:
                            exc = np.sqrt(np.abs(psi1)**2 + np.abs(psi2)**2) / 2.0
                    else:
                        exc = np.abs(psi1)

                    exc = exc * mode_norm
                    recs = np.array([calc_shape(nx, m_x, Lx, Rx) * calc_shape(ny, m_y, Ly, Ry) * calc_shape(nz, m_z, Lz, Rz) for m_x, m_y, m_z in zip(mxs, mys, mzs)])
                    gamma = calc_gamma(nx, ny, nz, room)

                    for i, f in enumerate(freqs_1d):
                        res_amp = (app_config.PhysicalConfig.RESONANCE_SCALING / fn) / np.sqrt((f - fn)**2 + gamma**2)
                        tensor_1d_mics[:, i] += (exc * recs * res_amp) ** 2

        tensor_1d_mics = np.sqrt(tensor_1d_mics)
        tensor_1d_avg = np.sqrt(np.mean(tensor_1d_mics ** 2, axis=0))

    f_response_db = 20 * np.log10(np.clip(tensor_1d_avg, app_config.PhysicalConfig.DB_CLIP_MIN, None))
    f_response_db = f_response_db - np.max(f_response_db)
    return f_response_db

def calc_tensor_space(room: RoomConfig, spk1: Position, spk2: Position, num_src: int, corr_mode: str, freq: float, grid_size: int = None) -> np.ndarray:
    """Convenience wrapper around ``compute_tensor_3d`` for a SINGLE frequency.

    Returns the magnitude pressure field as a 3D array of shape
    ``(grid_size, grid_size, grid_size)`` indexed as ``[ix, iy, iz]`` (the same
    'ij' meshgrid layout used internally), suitable for feeding straight into a
    structured/uniform grid in the 3D view.
    """
    if grid_size is None:
        grid_size = app_config.SimResolution.GRID_SIZE_NORMAL
    freqs = np.array([float(freq)], dtype=float)
    _, _, _, tensor = compute_tensor_3d(room, spk1, spk2, num_src, corr_mode, freqs, grid_size)
    return tensor[0]


def compute_tensor_3d(room: RoomConfig, spk1: Position, spk2: Position, num_src: int, corr_mode: str, freqs_3d: np.ndarray, grid_size: int = 32) -> tuple:
    Lx, Ly, Lz = room.Lx, room.Ly, room.Lz
    Rx, Ry, Rz = room.Rx, room.Ry, room.Rz
    sx, sy, sz = spk1.x, spk1.y, spk1.z
    sx2, sy2, sz2 = spk2.x, spk2.y, spk2.z
    x = np.linspace(0, Lx, grid_size)
    y = np.linspace(0, Ly, grid_size)
    z = np.linspace(0, Lz, grid_size)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    tensor = np.zeros((len(freqs_3d), len(x), len(y), len(z)))
    max_nx, max_ny, max_nz = get_max_modes(room)

    if "True Complex Field" in corr_mode:
        for i, f_query in enumerate(freqs_3d):
            P_complex_1 = np.zeros_like(X, dtype=np.complex128)
            P_complex_2 = np.zeros_like(X, dtype=np.complex128)

            for nx in range(max_nx):
                for ny in range(max_ny):
                    for nz in range(max_nz):
                        if nx == 0 and ny == 0 and nz == 0: continue
                        fn = (app_config.PhysicalConfig.SPEED_OF_SOUND / 2.0) * np.sqrt((nx/Lx)**2 + (ny/Ly)**2 + (nz/Lz)**2)
                        if fn > app_config.PhysicalConfig.MAX_CALC_FREQ: continue
                        # modal energy weighting
                        mode_norm = get_modal_norm(nx, ny, nz)
                        gamma = calc_gamma(nx, ny, nz, room)
                        res_complex = (app_config.PhysicalConfig.RESONANCE_SCALING / fn) / ((f_query - fn) + 1j * gamma)

                        mode_complex = get_psi(nx, X, Lx, Rx) * get_psi(ny, Y, Ly, Ry) * get_psi(nz, Z, Lz, Rz)
                        psi1 = get_psi(nx, sx, Lx, Rx) * get_psi(ny, sy, Ly, Ry) * get_psi(nz, sz, Lz, Rz)

                        P_complex_1 += mode_norm * (psi1 * mode_complex * res_complex)
                    
                        if num_src == 2:
                            psi2 = get_psi(nx, sx2, Lx, Rx) * get_psi(ny, sy2, Ly, Ry) * get_psi(nz, sz2, Lz, Rz)
                            P_complex_2 += mode_norm * (psi2 * mode_complex * res_complex)

            if num_src == 2:
                tensor[i] = np.abs(P_complex_1 + P_complex_2)
            else:
                tensor[i] = np.abs(P_complex_1)
    else:
        for nx in range(max_nx):
            for ny in range(max_ny):
                for nz in range(max_nz):
                    if nx == 0 and ny == 0 and nz == 0: continue
                    fn = (app_config.PhysicalConfig.SPEED_OF_SOUND / 2.0) * np.sqrt((nx/Lx)**2 + (ny/Ly)**2 + (nz/Lz)**2)
                    if fn > app_config.PhysicalConfig.MAX_CALC_FREQ: continue
                    # modal energy weighting
                    mode_norm = get_modal_norm(nx, ny, nz)
                    psi1 = get_psi(nx, sx, Lx, Rx) * get_psi(ny, sy, Ly, Ry) * get_psi(nz, sz, Lz, Rz)
                    if num_src == 2:
                        psi2 = get_psi(nx, sx2, Lx, Rx) * get_psi(ny, sy2, Ly, Ry) * get_psi(nz, sz2, Lz, Rz)
                        if "Global Cancel" in corr_mode:
                            exc = np.abs(psi1 + psi2) / 2.0
                        else:
                            exc = np.sqrt(np.abs(psi1)**2 + np.abs(psi2)**2) / 2.0
                    else:
                        exc = np.abs(psi1)

                    exc = exc * mode_norm
                    mode_shape = calc_shape(nx, X, Lx, Rx) * calc_shape(ny, Y, Ly, Ry) * calc_shape(nz, Z, Lz, Rz)
                    gamma = calc_gamma(nx, ny, nz, room)

                    for i, f in enumerate(freqs_3d):
                        res_amp = (app_config.PhysicalConfig.RESONANCE_SCALING / fn) / np.sqrt((f - fn)**2 + gamma**2)
                        tensor[i] += (exc * mode_shape * res_amp) ** 2

        tensor = np.sqrt(tensor)

    return X.flatten(), Y.flatten(), Z.flatten(), tensor
