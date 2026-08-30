"""Modal Collision Hazard density (MCFD) -- the metric only, no view code.

Pure NumPy. Imports ``numpy``, ``config``, ``constants`` and ``physics``
(for ``schroeder_frequency`` only). No Qt, no Matplotlib, so this module stays
unit-testable headlessly and can be lifted back out to the research project.

WHAT THIS MEASURES
------------------
A rectangular room's eigenmodes are enumerated from the classic formula. When
two modes land at nearly the same frequency they "collide": their energy piles
up at one spot in the spectrum instead of being spread across it. The hazard
density curve ``D(f)`` scores, for every frequency, how much pairwise collision
is happening there -- each colliding pair contributes a Gaussian bump centred on
the pair's midpoint frequency.

WHAT THIS IS NOT
----------------
``D(f)`` is a property of the room GEOMETRY AND WALL ABSORPTION ALONE. It does
not depend on speaker position, mic position, source count or phase-correction
mode. Consequently its peaks do NOT correspond to dips in the 1D frequency
response, and are not supposed to: the response curve describes one specific
listening position, while the hazard curve describes the room's intrinsic
disposition. The overlay earns its place precisely because the two curves can
be compared and DISAGREE.

The scalar score is likewise NOT an absolute grade, and NOT comparable between
rooms of different SIZE. ``D(f)`` is scale-dependent by construction -- sigma
goes as 1/f while mode spacing goes as 1/L -- so enlarging a room while keeping
its proportions raises the score purely mechanically. Measured 2026-08-30, all
six walls at R = 0.80:

    4.42 x 3.34 x 2.40 m          S_v5 = 0.006904   S_orig = 1.4805
    the SAME SHAPE scaled 1.5x    S_v5 = 0.019385   S_orig = 3.1143
    the SAME SHAPE scaled 2.5x    S_v5 = 0.061392   S_orig = 7.0022

Nine times "worse" for an acoustically identical geometry. The score is for
comparing ONE room across wall treatments, where curve and number agree in
direction; it has no fixed zero and no absolute good/bad threshold. The curve is
peak-normalized per room in the view (see ``graphs.py._draw_hazard``), so the
overlay answers "WHERE is this room weak", never "how weak next to that other
room". A fixed normalization reference that would make cross-room comparison
meaningful is deferred -- see SESSION_HANDOFF 2.13.

Known blind spot (verified against a real room, Aug 2026): two close modes that
share the same z-dependence produce a position-dependent null which this
frequency-domain metric cannot see at all.

TWO MODELS
----------
``HazardMode.ORIGINAL`` is a deliberately naive score over a fixed 29-mode set
with a constant collision width. It is kept -- not superseded -- because it
tracks perceived room quality better in small rooms. ``HazardMode.V5`` is the
extension that handles large rooms, adding direction-cosine axis weighting, an
order penalty and a Schroeder roll-off.

Their scalar scores are NOT comparable to each other (different weighting, and
only v5 divides by the mode count). Never render them side by side without the
model name attached.

**The original model ignores wall reflections entirely.** Its mode set is fixed
by index caps, its collision width is constant, and it has no roll-off and no
order penalty -- so nothing in it reads ``Rx/Ry/Rz`` or ``f_s``. The six wall
sliders being inert while it is selected is CORRECT BEHAVIOUR, not a bug: the
model is a statement about room proportions alone. Do not "fix" it by feeding
absorption in; that would make it the v5 model with fewer modes. For the same
reason it renders normally in a fully reflective room, where v5 correctly
renders nothing.

CALIBRATED CONSTANTS
--------------------
Every constant in the "pinned" block below was calibrated against research data
and must not be re-tuned here. In particular ``SCATTER`` is pinned at 0.30 and
is deliberately NOT read from the UI's Room Scatter slider: that slider defaults
to 0.0, which would silently delete the order penalty in the default state and
make every score incomparable with the research set. Room dimensions, the six
wall reflection coefficients and the Schroeder frequency derived from them DO
track the UI live -- see SESSION_HANDOFF.md section 2.12.
"""

from typing import NamedTuple

import numpy as np

import config as app_config
import constants
import physics

# -- Pinned, calibrated constants. Do NOT re-tune, do NOT expose in Settings. --
AXIS_POWER = 1.5          # p -- exponent on the room-flatness ratio (H / L_a)
SIGMA_POWER = 1.0         # q -- how fast the collision width narrows with f
ROLLOFF_POWER = 1.0       # k -- Schroeder roll-off order; r(f_s) == 0.5 exactly
SIGMA_REF = 3.0           # collision width [Hz] at F_REF
F_REF = 100.0             # reference frequency [Hz] for the width law
SIGMA_MIN = 0.3           # floor on the collision width [Hz]
SCATTER = 0.30            # s -- order penalty in gamma; NOT the UI slider value
# VERSIONING-RELEVANT, NOT A TUNING KNOB. GAMMA_REF_R defines the reference
# point of the entire v5 score: w_order = GAMMA_MIN / gamma(n) is dimensionless
# and referenced to it, so 1.0 reads "as damped as the least-damped mode of the
# reference room" and 2.13 reads "half as damped". Changing this value silently
# invalidates every S_v5 recorded before the change -- the numbers stay
# plausible and stop meaning the same thing. Treat any move as a breaking change
# to the metric and re-baseline the research set alongside it.
#
# READ THIS AS: a pinned reference DAMPING LEVEL, not a reference GEOMETRY. The
# two are easy to conflate and the distinction is the whole scope of the score.
# Pinning is what makes the score move in the RIGHT DIRECTION as absorption is
# changed within ONE room. It does NOT make scores from rooms of different size
# comparable -- they are not, by construction. See "WHAT THIS IS NOT" in the
# module docstring for the measured scale dependence.
GAMMA_REF_R = 0.80        # reflection coefficient GAMMA_MIN is evaluated at

# The order penalty's reference damping, evaluated ONCE at GAMMA_REF_R for the
# fundamental. This is a pinned constant (== 11.3), NOT a per-room quantity.
#
# Recomputing it from the live reflections would renormalize every room so that
# its own least-damped mode scores exactly w_order = 1.0, which throws away the
# absolute damping level: as absorption rises the constant GAMMA_SCALE term
# comes to dominate gamma, the relative spread across mode orders collapses,
# high-order modes stop being penalized, more modes carry weight, and the score
# gets WORSE while the roll-off tail (correctly) retracts. The overlay would
# contradict itself -- curve says "better", number says "worse".
#
# Ranking is unaffected either way: GAMMA_MIN depends only on R and never on
# geometry, so at any fixed wall setting the two variants differ by a global
# scalar and order rooms identically. Only the cross-absorption behaviour
# changes -- which is precisely the behaviour the overlay is read for.
GAMMA_MIN = (app_config.PhysicalConfig.GAMMA_BASE
             + app_config.PhysicalConfig.GAMMA_SCALE * (1.0 - GAMMA_REF_R)
             + SCATTER * 1.0)

# Mode A ("original") per-class weights. Recomputed here rather than taken from
# physics.get_modal_norm because that helper is scalar-only and this module is
# vectorised throughout.
#
# Their coincidence with physics.MODAL_NORMS is NOT numerology. The modal
# normalization constant of the wave equation is
#
#     Lambda = (1/2) ** (number of non-zero indices)
#
# i.e. 1/2 axial, 1/4 tangential, 1/8 oblique -- ratios 1 : 0.5 : 0.25, exactly
# the weights below. The naive model was implicitly weighting each mode by the
# ENERGY IT HOLDS. That is a real physical justification for weights that
# otherwise look arbitrary, and it explains why the naive model holds up in
# small rooms: there neither the roll-off nor the order penalty bites, so energy
# weighting is the whole story.
W_AXIAL = 1.0
W_TANGENTIAL = 0.5
W_OBLIQUE = 0.25
SIGMA_ORIGINAL = 3.0      # constant collision width -- no frequency dependence

# -- Presentation-independent implementation knobs ---------------------------
GRID_STEP = 0.5           # hazard-curve resolution [Hz]; see _f_grid()
PAIR_MIN_CONTRIB = 1e-4   # pairs at or below this never reach the accumulator
PAIR_CHUNK = 2000         # pairs per accumulation block, to bound peak memory
SCORE_CEILING_FACTOR = 3.0  # score enumerates to 3 * f_s (matches research)


class HazardResult(NamedTuple):
    """Everything the view needs, in one object.

    ``curve`` is the RAW, un-normalized ``D(f)``. Normalizing it is a
    presentation decision (the absolute magnitude is scale-dependent, so the
    view peak-normalizes) and therefore belongs in ``graphs.py`` -- keeping the
    raw curve here preserves ``peak_value`` for the annotation, which is where
    the information lost to normalization is recovered.

    A degenerate room (see ``compute()``) yields empty arrays and zeros; the
    view must render nothing in that case rather than propagate NaN/inf.
    """
    f_grid: np.ndarray      # 0.5 Hz grid over [MIN_FREQ, MAX_FREQ]
    curve: np.ndarray       # raw D(f), same length as f_grid
    peak_value: float       # max(curve), absolute (pre-normalization)
    peak_freq: float        # location of that peak [Hz]
    score: float            # S_orig or S_v5 -- see the module docstring
    f_s: float              # the Schroeder frequency actually used [Hz]
    mode: str               # HazardMode.ORIGINAL | HazardMode.V5


# ==========================================
# Mode enumeration
# ==========================================

def _enumerate_modes(lx: float, ly: float, lz: float, f_max: float) -> tuple:
    """Return ``(freqs, nx, ny, nz)`` as 1-D arrays, unsorted, ``(0,0,0)``
    excluded, all with ``f <= f_max``.

    Deliberately NOT ``physics.calc_room_modes()``: that one returns a sorted
    Python list of ``(freq, (nx, ny, nz), length)`` tuples shaped for the UI's
    mode table and guide lines, and enumerates a different index range. This
    metric needs vectorised NumPy arrays over a frequency-driven index cap.
    """
    c = app_config.PhysicalConfig.SPEED_OF_SOUND
    if lx <= 0.0 or ly <= 0.0 or lz <= 0.0 or f_max <= 0.0:
        empty_f = np.zeros(0, dtype=float)
        empty_n = np.zeros(0, dtype=int)
        return empty_f, empty_n, empty_n.copy(), empty_n.copy()

    nx_max = int(np.ceil(2.0 * lx * f_max / c))
    ny_max = int(np.ceil(2.0 * ly * f_max / c))
    nz_max = int(np.ceil(2.0 * lz * f_max / c))

    nx, ny, nz = np.meshgrid(
        np.arange(nx_max + 1), np.arange(ny_max + 1), np.arange(nz_max + 1),
        indexing="ij",
    )
    nx, ny, nz = nx.ravel(), ny.ravel(), nz.ravel()

    # Drop the trivial (0,0,0) "mode" -- it has no frequency.
    nonzero = (nx > 0) | (ny > 0) | (nz > 0)
    nx, ny, nz = nx[nonzero], ny[nonzero], nz[nonzero]

    freqs = (c / 2.0) * np.sqrt((nx / lx) ** 2 + (ny / ly) ** 2 + (nz / lz) ** 2)

    keep = freqs <= f_max
    return freqs[keep], nx[keep], ny[keep], nz[keep]


def _enumerate_original(lx: float, ly: float, lz: float) -> tuple:
    """The fixed 29-mode set of Mode A, with its per-class weights.

    The set is bounded by INDEX CAPS, not by a frequency ceiling -- that is the
    whole point of the naive model, and why its mode count never varies with
    room size:

        axial       each axis, n = 1..3            ->  9 modes, w = 1.00
        tangential  3 axis pairs, n1, n2 = 1..2    -> 12 modes, w = 0.50
        oblique     nx, ny, nz = 1..2              ->  8 modes, w = 0.25
    """
    idx = []
    weights = []

    for n in range(1, 4):                                   # axial
        idx += [(n, 0, 0), (0, n, 0), (0, 0, n)]
        weights += [W_AXIAL] * 3
    for n1 in range(1, 3):                                  # tangential
        for n2 in range(1, 3):
            idx += [(n1, n2, 0), (n1, 0, n2), (0, n1, n2)]
            weights += [W_TANGENTIAL] * 3
    for nx in range(1, 3):                                  # oblique
        for ny in range(1, 3):
            for nz in range(1, 3):
                idx.append((nx, ny, nz))
                weights.append(W_OBLIQUE)

    n_arr = np.array(idx, dtype=int)
    nx, ny, nz = n_arr[:, 0], n_arr[:, 1], n_arr[:, 2]
    c = app_config.PhysicalConfig.SPEED_OF_SOUND
    freqs = (c / 2.0) * np.sqrt((nx / lx) ** 2 + (ny / ly) ** 2 + (nz / lz) ** 2)
    return freqs, np.array(weights, dtype=float)


# ==========================================
# v5 weighting terms
# ==========================================

def _axis_weight(nx, ny, nz, lx: float, ly: float, lz: float) -> np.ndarray:
    """Direction-cosine axis weight.

    With ``k_a = n_a / L_a`` and ``H = L_z``:

        cos^2(theta_a) = k_a^2 / (k_x^2 + k_y^2 + k_z^2)
        w_axis         = sum_a cos^2(theta_a) * (H / L_a)^p

    Setting ``H = L_z`` is intentional: a pure z-axial mode then always scores
    exactly 1.0 regardless of room size, and x/y-leaning modes are discounted
    continuously by how flat the room is.
    """
    kx, ky, kz = nx / lx, ny / ly, nz / lz
    k_sq = kx ** 2 + ky ** 2 + kz ** 2
    # k_sq is strictly positive: (0,0,0) is never in the mode set.
    cos2_x, cos2_y, cos2_z = kx ** 2 / k_sq, ky ** 2 / k_sq, kz ** 2 / k_sq

    h = lz
    return (
        cos2_x * (h / lx) ** AXIS_POWER
        + cos2_y * (h / ly) ** AXIS_POWER
        + cos2_z * (h / lz) ** AXIS_POWER
    )


def _order_weight(nx, ny, nz, rx: float, ry: float, rz: float) -> np.ndarray:
    """Order penalty ``GAMMA_MIN / gamma(n)``, using the project's own damping
    model.

    ``gamma(n)`` is identical IN FORM to ``physics.calc_gamma`` -- keep it that
    way. It is re-derived here rather than called because ``calc_gamma`` is
    scalar-only and takes a ``RoomConfig``; only ``GAMMA_BASE`` /
    ``GAMMA_SCALE`` are borrowed.

        R_eff = (nx*Rx + ny*Ry + nz*Rz) / (nx + ny + nz)
        gamma = GAMMA_BASE + GAMMA_SCALE * (1 - R_eff) + s * (nx^2+ny^2+nz^2)

    ``s`` is SCATTER, pinned at 0.30 -- NOT the UI's Room Scatter slider.

    The numerator is the PINNED ``GAMMA_MIN``, evaluated once at
    ``GAMMA_REF_R``; ``rx, ry, rz`` are live and feed only ``R_eff`` inside
    ``gamma(n)``. See GAMMA_MIN's own comment for why re-deriving the numerator
    per room inverts how the score responds to absorption.

    A room more reflective than the reference therefore yields ``w_order > 1``
    (2.13 for the fundamental at R = 0.95). That is correct and means exactly
    "less damped than the reference room" -- do NOT clamp it. The curve is
    peak-normalized downstream, so nothing overflows.
    """
    p = app_config.PhysicalConfig
    n_sum = nx + ny + nz          # >= 1: (0,0,0) is never in the mode set
    r_eff = (nx * rx + ny * ry + nz * rz) / n_sum

    gamma = (p.GAMMA_BASE + p.GAMMA_SCALE * (1.0 - r_eff)
             + SCATTER * (nx ** 2 + ny ** 2 + nz ** 2))
    return GAMMA_MIN / gamma


def _rolloff(freqs: np.ndarray, f_s: float) -> np.ndarray:
    """Schroeder roll-off ``r(f) = 1 / (1 + (f/f_s)^(2k))``.

    Derived from the modal-overlap relation ``M(f) = 3 (f/f_s)^2``, so
    ``r(f_s) == 0.5`` exactly, by construction. There is deliberately no hard
    cutoff: the roll-off alone suppresses the high-frequency tail.
    """
    return 1.0 / (1.0 + (freqs / f_s) ** (2.0 * ROLLOFF_POWER))


def _sigma(freqs: np.ndarray) -> np.ndarray:
    """Frequency-dependent collision width
    ``sigma(f) = max(SIGMA_REF * (F_REF/f)^q, SIGMA_MIN)``.

    Modes crowd together as frequency rises, so the window that counts two of
    them as "colliding" narrows in step."""
    return np.maximum(SIGMA_REF * (F_REF / freqs) ** SIGMA_POWER, SIGMA_MIN)


# ==========================================
# Pair reductions
# ==========================================

def _f_grid() -> np.ndarray:
    """The hazard curve's OWN frequency grid, at GRID_STEP (0.5 Hz).

    Deliberately not the response curve's grid: ``SimResolution.FREQ_1D_STEP``
    is 1 Hz, too coarse for the ~2-3 Hz sigma features here, and the curve would
    render visibly jagged. Matplotlib is happy to plot a second line against a
    different x array.
    """
    p = app_config.PhysicalConfig
    start = p.MIN_FREQ
    end = max(p.MAX_FREQ, start + GRID_STEP)
    return np.arange(start, end + GRID_STEP, GRID_STEP)


def _pair_score(freqs: np.ndarray, weights: np.ndarray,
                sigma_pair: np.ndarray, divide_by_n: bool) -> float:
    """Scalar collision score ``sum_{i<j} w_i w_j exp(-((f_i-f_j)/sigma_ij)^2)``,
    optionally divided by the mode count (v5 does, the original does not)."""
    n = freqs.size
    if n < 2:
        return 0.0
    i, j = np.triu_indices(n, k=1)
    d = (freqs[i] - freqs[j]) / sigma_pair
    total = float(np.sum(weights[i] * weights[j] * np.exp(-d * d)))
    return total / n if divide_by_n else total


def _pair_curve(f_grid: np.ndarray, freqs: np.ndarray, weights: np.ndarray,
                sigma_pair: np.ndarray) -> np.ndarray:
    """Accumulate ``D(f) = sum_{i<j} c_ij * exp(-((f - f_ij)/sigma_ij)^2)``.

    Each surviving pair contributes one Gaussian bump centred on its midpoint
    ``f_ij``, with height ``c_ij = w_i w_j exp(-((f_i-f_j)/sigma_ij)^2)`` -- the
    same collision term the scalar score sums.

    Vectorised over a ``(pairs, grid)`` matrix reduced with ``.sum(0)``, chunked
    at PAIR_CHUNK pairs so peak memory stays bounded no matter how large the
    room is. (The research script loops in Python over kept pairs, which is fine
    for a one-shot PNG render but not for an interactive redraw.)
    """
    curve = np.zeros_like(f_grid)
    n = freqs.size
    if n < 2:
        return curve

    i, j = np.triu_indices(n, k=1)
    mids = 0.5 * (freqs[i] + freqs[j])
    d = (freqs[i] - freqs[j]) / sigma_pair
    contrib = weights[i] * weights[j] * np.exp(-d * d)

    # Pairs too far apart to collide contribute nothing visible; dropping them
    # here is what keeps the accumulation cheap for large rooms.
    keep = contrib > PAIR_MIN_CONTRIB
    mids, sig, contrib = mids[keep], sigma_pair[keep], contrib[keep]

    for lo in range(0, mids.size, PAIR_CHUNK):
        hi = min(lo + PAIR_CHUNK, mids.size)
        dg = (f_grid[None, :] - mids[lo:hi, None]) / sig[lo:hi, None]
        curve += (contrib[lo:hi, None] * np.exp(-dg * dg)).sum(0)

    return curve


# ==========================================
# Public API
# ==========================================

def _empty(mode: str, f_s: float) -> HazardResult:
    """A degenerate result: the view renders nothing for it."""
    return HazardResult(
        f_grid=np.zeros(0, dtype=float), curve=np.zeros(0, dtype=float),
        peak_value=0.0, peak_freq=0.0, score=0.0, f_s=f_s, mode=mode,
    )


def compute(mode: str, lx: float, ly: float, lz: float,
            wall_reflections: dict, rx: float, ry: float, rz: float) -> HazardResult:
    """Compute the hazard curve and scalar score for one room.

    Args:
        mode: ``HazardMode.ORIGINAL`` or ``HazardMode.V5``.
        lx, ly, lz: room dimensions [m], live from the UI.
        wall_reflections: the six per-wall reflection coefficients, keyed by
            ``constants.WALL_NAMES``. Feeds ``physics.schroeder_frequency``.
            Passed WHOLE rather than as the three axis means because f_s depends
            on each wall's own ``1 - r^2``, which the pair means do not
            determine (``(1.0, 0.6)`` and ``(0.8, 0.8)`` share a mean but not an
            absorption).
        rx, ry, rz: per-axis reflection = mean of the opposing wall pair, as
            produced by ``MainWindow._wall_reflection()``. Feeds the gamma
            order penalty, matching ``physics.calc_gamma``.

    Returns:
        A ``HazardResult``. When the room is degenerate -- non-positive
        dimensions, or fully reflective so that ``schroeder_frequency()``
        returns 0.0 and the roll-off would divide by zero -- the result is empty
        and the view renders nothing. No NaN or inf ever leaves this function.
    """
    f_s = physics.schroeder_frequency(lx, ly, lz, wall_reflections)

    # Non-positive dimensions are degenerate for BOTH models -- there are no
    # modes to enumerate. The f_s guard is v5-ONLY and lives in its branch
    # below: the original model never divides by f_s.
    if lx <= 0.0 or ly <= 0.0 or lz <= 0.0:
        return _empty(mode, f_s)

    f_grid = _f_grid()

    if mode == constants.HazardMode.ORIGINAL:
        freqs, weights = _enumerate_original(lx, ly, lz)
        # Constant collision width -- no frequency dependence, no roll-off, no
        # order penalty, no direction-cosine weighting. The mode set is fixed at
        # 29, so score and curve share it (the dual-ceiling split below is moot).
        sigma_pair = np.full(freqs.size * (freqs.size - 1) // 2, SIGMA_ORIGINAL)
        score = _pair_score(freqs, weights, sigma_pair, divide_by_n=False)
        curve = _pair_curve(f_grid, freqs, weights, sigma_pair)

    elif mode == constants.HazardMode.V5:
        # v5 ONLY: the Schroeder roll-off divides by f_s, and a fully
        # reflective room (absorption -> 0) has no modal region for the model
        # to describe. Render nothing rather than propagate NaN/inf.
        if f_s <= 0.0:
            return _empty(mode, f_s)

        def prepare(f_max):
            f, nx, ny, nz = _enumerate_modes(lx, ly, lz, f_max)
            w = (_axis_weight(nx, ny, nz, lx, ly, lz)
                 * _order_weight(nx, ny, nz, rx, ry, rz)
                 * _rolloff(f, f_s))
            i, j = np.triu_indices(f.size, k=1)
            return f, w, _sigma(0.5 * (f[i] + f[j]))

        # Two enumeration ceilings, deliberately different (see SESSION_HANDOFF
        # 2.12). The score matches the research value exactly by sweeping to
        # 3*f_s; the curve only ever displays MIN_FREQ..MAX_FREQ, so enumerating
        # that far would explode the pair count for no visible gain.
        p = app_config.PhysicalConfig
        f_score, w_score, sig_score = prepare(SCORE_CEILING_FACTOR * f_s)
        score = _pair_score(f_score, w_score, sig_score, divide_by_n=True)

        curve_ceiling = min(
            SCORE_CEILING_FACTOR * f_s,
            p.MAX_FREQ + 5.0 * float(_sigma(np.array([p.MAX_FREQ]))[0]),
        )
        f_c, w_c, sig_c = prepare(curve_ceiling)
        curve = _pair_curve(f_grid, f_c, w_c, sig_c)

    else:
        return _empty(mode, f_s)

    if curve.size == 0 or not np.all(np.isfinite(curve)):
        return _empty(mode, f_s)

    peak_idx = int(np.argmax(curve))
    return HazardResult(
        f_grid=f_grid, curve=curve,
        peak_value=float(curve[peak_idx]), peak_freq=float(f_grid[peak_idx]),
        score=float(score), f_s=float(f_s), mode=mode,
    )
