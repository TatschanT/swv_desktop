"""Shared literal constants with a single source of truth.

Pure data, no imports of other project modules (so any module can import it
without risking a cycle). Centralised here because each of these values was
previously duplicated across files, where a typo in one copy would silently
diverge from the others:

  * ``CorrMode``   - phase-correction tokens produced by ``main`` and matched by
                     ``physics`` (by substring). A mismatch would change physics
                     branching, so they MUST agree.
  * equipment colors - shared by the 3D (``render``) and 2D (``graphs``) views.
  * ``WALL_NAMES`` - the six wall identifiers used by the UI sliders, the
                     physics absorption map and the CSV import/export.
  * ``HazardMode`` - Modal Collision Hazard model tokens, produced by the
                     ``main`` combo box, dispatched on by ``hazard`` and echoed
                     back in ``HazardResult.mode`` for the ``graphs`` annotation.
"""


class CorrMode:
    """Phase-correction tokens. ``main._corr_mode()`` returns one of these and
    ``physics`` matches them as substrings of ``corr_mode``."""
    UNCORRELATED = "Uncorrelated"
    GLOBAL_CANCEL = "Global Cancel"
    TRUE_COMPLEX = "True Complex Field"


class HazardMode:
    """Modal Collision Hazard model selection.

    ``OFF`` is the default: no overlay is computed and the 2D plot is drawn
    exactly as it was before the feature existed.

    ``ORIGINAL`` and ``V5`` are two DIFFERENT scoring models, not two
    resolutions of one. Their scalar scores are NOT comparable to each other
    (different weighting; only v5 divides by the mode count), so any display of
    a score MUST carry the model name -- see ``hazard.py`` and the annotation in
    ``graphs.update_freq_response``.
    """
    OFF = "off"
    ORIGINAL = "original"
    V5 = "v5"


# Equipment marker colors (shared by render.py and graphs.py).
SPK_COLOR = "#38bdf8"   # speaker: bright cyan-blue
MIC_COLOR = "#f4f4f4"   # mic: bright white


# Wall identifiers, in CSV export order. These exact strings are the keys of the
# UI wall-slider dict, physics' absorption-area map and the CSV "Wall <name>" rows.
WALL_LEFT = "Left (X=0)"
WALL_RIGHT = "Right (X=Lx)"
WALL_FRONT = "Front (Y=0)"
WALL_BACK = "Back (Y=Ly)"
WALL_FLOOR = "Floor (Z=0)"
WALL_CEILING = "Ceiling (Z=Lz)"

# Opposing wall pairs (X, Y, Z axes) -- the order the UI lays them out and the
# physics engine averages them into Rx/Ry/Rz.
WALL_PAIRS = (
    (WALL_LEFT, WALL_RIGHT),
    (WALL_FRONT, WALL_BACK),
    (WALL_FLOOR, WALL_CEILING),
)

# Flat tuple in export order.
WALL_NAMES = tuple(name for pair in WALL_PAIRS for name in pair)
