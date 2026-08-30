# Changelog

All notable changes to this project will be documented in this file.

## [1.4.0] - 2026-08-29

### Added: Modal Collision Hazard Overlay (2D Frequency Response)

A new **Hazard overlay** selector — **Off / Original / v5** — sits next to the
"Show room modes" checkbox and draws a density backdrop behind the frequency-
response curve. It ports the Modal Collision Hazard Map (MCFD) metric from a
separate acoustics research project. Default is **Off**, so v1.3.1 behaviour is
unchanged until the feature is opted into.

#### What the metric measures

A rectangular room's eigenmodes are enumerated from the classic formula. When
two modes land at nearly the same frequency they "collide" — their energy piles
up at one spot in the spectrum instead of being spread across it. The hazard
density curve `D(f)` scores, for every frequency, how much pairwise collision is
happening there; each colliding pair contributes a Gaussian bump centred on the
pair's midpoint frequency.

#### What it is NOT

`D(f)` is a property of the **room geometry and wall absorption alone**. It does
not depend on speaker position, mic position, source count or phase-correction
mode. Its peaks therefore do **not** correspond to dips in the frequency-
response curve, and are not supposed to: the response curve describes one
specific listening position, while the hazard curve describes the room's
intrinsic disposition. The overlay earns its place precisely because the two
curves can be compared and **disagree**.

The overlay is styled as a wash sitting behind everything (fill α=0.22, z-order
below the mode guide lines, the response curve and the red marker) so it reads
as a backdrop rather than as a second foreground curve inviting a point-by-point
comparison. No UI text claims the peaks predict dips.

**Known blind spot** (verified against a real room, Aug 2026): two close modes
sharing the same *z*-dependence produce a position-dependent null that this
frequency-domain metric cannot see at all.

#### Two models, both kept

| Model | Mode set | Weighting | Score |
|---|---|---|---|
| **Original** | fixed 29 modes by index cap (9 axial, 12 tangential, 8 oblique) | class weight only (1.0 / 0.5 / 0.25); constant σ = 3.0 Hz | `S_orig`, **not** divided by N |
| **v5** | frequency-driven, enumerated to 3·f_s | direction-cosine axis weight × γ order penalty × Schroeder roll-off; σ(f) narrows as 1/f | `S_v5`, divided by N |

"Original" is deliberately naive and is **not** superseded — it tracks perceived
room quality better in small rooms. "v5" is the extension that handles large
rooms. **Their scalar scores are not comparable to each other** (different
weighting, and only v5 divides by the mode count), so the on-plot read-out
always prefixes the model name.

#### Parameter coupling — what tracks the UI, what is pinned

| Parameter | Source | Why |
|---|---|---|
| `Lx, Ly, Lz` | **UI (live)** | — |
| `f_s`, feeding the roll-off `r(f)` | **UI (live)** — `physics.schroeder_frequency()` with the six per-wall slider values | SWV's Schroeder formula is algebraically identical to the research one (V cancels). All six walls at R=0.80 reproduces the research's α=0.36 exactly. Live coupling makes the core v5 insight visible: **more absorption raises total absorption A, shortens RT60 and widens each mode's bandwidth, so modal overlap `M(f) = 3(f/f_s)²` reaches 3 at a lower frequency — `f_s` falls and the modal region NARROWS.** The v5 roll-off inherits this correctly: the hazard tail retracts as absorption is added |
| `R_eff` in γ (`Rx, Ry, Rz`) | **UI (live)** — per-axis mean of the opposing wall pair (`_wall_reflection()`) | Same damping model as `calc_gamma` |
| `GAMMA_MIN` (γ's numerator) | **PINNED at 11.3**, evaluated once at `GAMMA_REF_R = 0.80` | Recomputing it from live reflections renormalizes every room so its own least-damped mode scores exactly 1.0, discarding the absolute damping level — and **inverts** how the score responds to absorption (see below) |
| scatter `s` in γ | **PINNED at 0.30** — the Room Scatter slider is ignored | The slider defaults to 0.0. Reading it would silently delete the order penalty in the default state and make every score incomparable with the research data |
| `p=1.5`, `q=1.0`, `k=1.0`, `σ_ref=3.0`, `f_ref=100` | **PINNED** | Calibrated; deliberately not exposed in Settings |

`GAMMA_MIN` is the subtle one. Derived live, it makes `w_order = 1.0` for each
room's own least-damped mode; as absorption rises the constant
`GAMMA_SCALE·(1 − R_eff)` term comes to dominate γ, the relative spread across
mode orders collapses, high-order modes stop being penalized, more modes carry
weight — and the score gets *worse* while the roll-off tail correctly retracts.
The overlay would contradict itself: the curve says "better", the number says
"worse". Pinned, both agree. Note this does **not** change how rooms rank
against each other — `GAMMA_MIN` depends only on `R`, never on geometry, so at
any fixed wall setting the two variants differ by a global scalar and produce
identical orderings. Only the cross-absorption behaviour changes.

Measured `S_v5` for 4.42 × 3.34 × 2.40 m as absorption is swept:

| all six walls at R | 0.95 | 0.90 | 0.80 | 0.70 | 0.60 | 0.40 |
|---|---|---|---|---|---|---|
| `f_s` (Hz) | 314.5 | 225.3 | 163.7 | 137.5 | 122.8 | 107.2 |
| `S_v5` | 0.010601 | 0.010484 | 0.006904 | 0.004414 | 0.002957 | 0.001465 |

`w_order` exceeds 1.0 for rooms more reflective than the reference (2.13 for the
fundamental at R=0.95). That is expected and correct — it means "less damped
than the reference room" — and is deliberately **not** clamped; the curve is
peak-normalized downstream, so nothing overflows.

Degenerate rooms are guarded, but **only where the guard is justified**. A fully
reflective room (all six walls at R=1.0) makes `schroeder_frequency()` return
0.0, and v5's roll-off would divide by zero — so **v5** returns an empty result
and renders nothing, a plot byte-identical to the Off state. **Original** has no
such dependency and renders normally there, showing `f_s —` in its read-out
(matching the existing `Est. Schroeder: —` convention). Non-positive room
dimensions guard both models. No NaN, no inf, no exception in any case.

Relatedly: **the six wall sliders are inert while Original is selected, and that
is correct behaviour, not a bug.** Original's mode set is fixed by index caps,
its collision width is constant, and it has no roll-off and no order penalty, so
nothing in it reads `Rx/Ry/Rz` or `f_s` — it is a statement about room
proportions alone. Feeding absorption into it would just make it v5 with fewer
modes.

The Original weights (1.0 / 0.5 / 0.25) coinciding with `physics.MODAL_NORMS` is
not numerology. The wave equation's modal normalization constant is
`Λ = (1/2)^(number of non-zero indices)` — 1/2 axial, 1/4 tangential, 1/8
oblique, i.e. ratios 1 : 0.5 : 0.25 exactly. The naive model was implicitly
weighting each mode by the energy it holds, which is a real physical
justification for weights that otherwise look arbitrary, and explains why it
holds up in small rooms: there neither the roll-off nor the order penalty bites,
so energy weighting is the whole story.

#### Recompute behaviour

The hazard is a **third** recompute category, strictly narrower than the two the
app already had. It depends only on the room dimensions, the six wall
reflection coefficients and the selected model, and is memoized on exactly that
set — moving the mic costs zero hazard computation, and the cheap
frequency-marker path never touches the overlay artists. Nothing is added to the
CSV: dimensions and wall coefficients already round-trip, and the hazard is
derived, never stored.

Measured cost of a full v5 recompute (curve + score) for a 6.0 × 5.0 × 2.4 m
room — 518 modes, ~134 000 pairs — is **4.7 ms**.

---

### Changed: `GAMMA_MIN` Pinned — the v5 Score Changed Meaning

Shipped as a follow-up fix within v1.4.0. **This is not merely a bug fix: it
changed what `S_v5` means, and scores recorded before it are not comparable to
scores recorded after it.**

`GAMMA_MIN`, the numerator of the order penalty `w_order = GAMMA_MIN / γ(n)`,
was being recomputed per room from the live wall reflections. That normalised
every room against *itself*: its own least-damped mode scored exactly
`w_order = 1.0` regardless of how absorptive the room actually was, discarding
the absolute damping level entirely.

It is now a pinned constant — `GAMMA_REF_R = 0.80`, value **11.3** — so the
score is expressed **relative to a fixed reference room**. `w_order = 1.0` now
means "as damped as the least-damped mode of the reference room"; `2.13` means
"half as damped". Values above 1.0 are expected for rooms more reflective than
the reference and are deliberately not clamped.

**Room-to-room ranking is unaffected.** `GAMMA_MIN` depends only on `R`, never
on geometry, so at any fixed wall setting the two variants differ by a global
scalar and order rooms identically (verified: four geometries, identical
ordering at R=0.80 and R=0.60). Note this pins a reference **damping level**,
not a reference **geometry**: `S_v5` is scale-dependent by construction, so
scores from rooms of different size remain **not comparable** — the same room
shape scaled 2.5× scores ~8.9× worse despite being acoustically identical
(measured 2026-08-30; see SESSION_HANDOFF 2.13). What changed is the
**cross-absorption** behaviour — and it changed from wrong to right. Previously, adding absorption
made the score *worse* while the roll-off tail correctly retracted, so the
overlay contradicted itself: the curve said "better", the number said "worse".

Because `GAMMA_REF_R` defines the reference point of the whole score, it is
**versioning-relevant, not a tuning knob**. Changing it silently invalidates
every score recorded before the change.

---

### Fixed: `f_s` Guard Narrowed to the v5 Model Only

The `f_s <= 0.0` degenerate-room guard applied to both models. Only v5 divides
by `f_s` (in the Schroeder roll-off); the Original model reads no wall
reflections at all, so blanking it in a fully reflective room had no
justification.

Original now renders normally there, showing `f_s —` in its read-out (matching
the existing `Est. Schroeder: —` convention). v5 still renders nothing. The
non-positive-dimension guard still covers both models. Verified: Original's
R=1.0 curve is bit-identical to its R=0.80 curve, which demonstrates
independence from wall reflections rather than merely the absence of a crash.

---

### Changed: 2D Panel Width Rebalance (1:1 → 4:6)

The frequency response is the panel that rewards width; the top-down view is
letterboxed by `set_aspect("equal")` regardless, so half the figure was being
spent on margin. The response gains ~20 % width and the top-down slot becomes
near-square. Two `add_subplot(1, 2, n)` calls plus a separate
`subplots_adjust()` are replaced by a single `add_gridspec()` carrying both the
split and the margins, so the margin numbers live in exactly one place.
`figsize` goes 3.2 → 3.4 in for annotation headroom; the room outline keeps its
true proportions throughout.

The right margin also moved 0.97 → 0.93 to make room for the hazard axis's tick
labels and rotated ylabel, which at 0.97 were drawn off the canvas. It is held
constant across both overlay states so the response curve never shifts sideways
when the overlay is toggled.

**Files changed:** `hazard.py` (new — the metric, pure NumPy, no Qt/Matplotlib).
`constants.py` (new `HazardMode` tokens). `graphs.py` (gridspec rebalance,
`ax_hazard` twin created once in `__init__`, `_restack()` / `_draw_hazard()` /
`_hide_hazard()`, `hazard=` threaded through `update_all` →
`update_freq_response`). `main.py` (`hazard_combo`, `_hazard_mode()`,
`_hazard_result()` with memoization, `_on_hazard_mode_changed()`, signal
wiring). `physics.py`, `render.py` and the 3D pipeline unchanged.

## [1.3.1] - 2026-08-12

### Added: Flat-Field Warning (Wall Reflection Coefficients)

When every axis's reflection coefficient collapses to zero (`Rx == Ry == Rz
== 0`, i.e. both walls of every pair are set fully absorptive), `calc_shape()`
degenerates to a spatial constant on every mode (see `physics.py`), so the 3D
pressure field carries no spatial structure and the default per-frequency
normalization renders it fully transparent — the view went silently blank
with no indication why.

A new label under the "Wall reflection coefficients" panel now reads
**"⚠ All walls fully absorptive (R=0) — field has no spatial structure"**
whenever this exact condition is met, and clears otherwise. Deliberately
setting a SINGLE wall to R=0 — a legitimate way to inspect that wall's
first-order reflection in isolation — does NOT trigger it, since the other
two axes still carry real modal structure.

The check is cheap arithmetic (reuses `_wall_reflection()`, no physics
recompute) wired to the six wall sliders' `valueChanged`, so it updates live
while dragging.

**Files changed:** `main.py` (new `_update_flat_field_warning()` method,
`flat_field_lbl` widget, signal wiring, startup call). `physics.py` and
`render.py` unchanged.

---

### Fixed: Position Sliders — Keyboard/Wheel Changes Never Reached the 2D/3D Views

With **Dynamic update** OFF (the default), a room/speaker/mic/wall slider
only refreshed the 2D plots and the 3D field on `committed`, which was wired
solely to `QSlider.sliderReleased` — a signal Qt emits **only for a mouse
press-drag-release gesture**. Adjusting a slider via the keyboard (arrow /
Page / Home / End) or the mouse wheel changes its value (`valueChanged` still
fires, so the numeric read-out was correct) but never emits
`sliderReleased`, so `committed` never fired: the 2D marker and 3D field
silently kept showing the pre-change state until some unrelated slider was
next dragged-and-released, at which point they would jump to the
already-changed values all at once — read by the user as "the marker didn't
move" or "jumped to the wrong place."

`LabeledSlider` now detects this case via `QSlider.isSliderDown()` (`True`
only during an actual mouse drag) and, when a value change arrives without
an active drag, starts a 150 ms single-shot debounce timer that fires
`committed` once input settles — coalescing key-repeat or a fast wheel
scroll into a single recomputation. A genuine mouse drag is completely
unaffected: it still commits instantly on release, with zero added overhead.

**Files changed:** `widgets.py` (`LabeledSlider`: new `COMMIT_DEBOUNCE_MS`
constant, `_commit_timer`, `_emit_committed()`, updated `_on_slider()`).
`main.py`, `physics.py`, `render.py` unchanged.

## [1.3.0] - 2026-06-19

### Added: Room Data Import

A new **Import data** button now sits between the Export data and Settings
buttons in the right-panel toolbar. Clicking it opens a file dialog filtered to
`*.csv` and restores the full application state from a previously exported file.

The import reads the `[Parameters]` section only (`[Frequency Response]` and
`[Room Modes]` are ignored). All room and simulation parameters are restored:
room dimensions, speaker positions (one or two sources), mic position, per-wall
reflection coefficients, frequency, source count, phase correction mode, room
scatter, and listening area.

All UI sliders and combo boxes are updated in a single batch with signals
blocked, so no per-parameter recompute or signal-storm fires during the import.
Room dimensions are applied first so speaker/mic positions clamp against the
imported room, not the previous one. A single recompute is triggered after all
values are set.

If any required parameter is missing or malformed the import is aborted before
any state is applied; the user is shown an informative error dialog.

**Files changed:** `main.py` (new `on_import_clicked`, `_import_set_slider`,
`_apply_imported_params` methods; updated button row). `csv_io.py` (new
`load_parameters`, `read_parameters_section`, `parse_parameters`,
`phase_label_to_index` — Qt-free; extracted during structural cleanup below).
`physics.py` unchanged.

---

### Added: Schroeder Frequency Display

A read-only label **Est. Schroeder: ~142 Hz** now appears below the frequency-
response curve, left of the "Show room modes" checkbox. It gives a quick
acoustic context for the simulation's valid frequency range.

The Schroeder frequency marks the transition from the modal region (isolated,
well-separated resonances — where this app's simulation is physically meaningful)
to the diffuse statistical region above it. It is estimated from Sabine's
reverberation formula:

```
RT60 = 0.161 × V / A          (Sabine, V = volume, A = total absorption)
f_s  = 2000 × sqrt(RT60 / V)
```

Each wall's absorption coefficient is derived from its reflection coefficient as
`α = 1 − r²`; the total absorption is the area-weighted sum over all six walls.
When all walls are fully reflective (R=1, A→0) the label shows a dash.

The display updates live while the user drags any room-dimension or wall-
reflection slider (cheap arithmetic, runs on the main thread with no physics
call).

**Files changed:** `physics.py` (new `schroeder_frequency()` function + helper
`_WALL_AREA_DIMS` table; `import math` added). `main.py` (new `schroeder_lbl`
widget, `_update_schroeder_display()` method, live signal wiring, startup
population, and post-import refresh).

---

### Refactored: Structural Cleanup

Five focused commits on branch `refactor/structural-cleanup` reorganise the
codebase without changing any observable behaviour. All five were verified by
a smoke-test harness (construction → recompute → full-band → contour →
export/import round-trip → stable Schroeder readout).

| Commit | Scope | What moved / was removed |
|--------|-------|--------------------------|
| **§3.1** | `main.py` → `widgets.py` | `LabeledSlider`, `XYZSliders`, `mono`, `make_placeholder`, `DARK_BG`, `PLACEHOLDER_TEXT` — pure Qt presentation, no controller coupling |
| **§1.1** | `render.py` | Deleted unreachable `_setup_overlay` method (~27 lines) + dropped unused `import vtk`; fixed misleading module docstring (X-ray/overlay paragraphs removed) |
| **§4.1+§4.2** | `main.py` | New `_num_src()` helper (eliminates 5 inline ternaries); new `_physics_snapshot()` helper returns `PhysicsSnapshot` namedtuple (eliminates 3 duplicate parameter-gather blocks) |
| **§3.2** | `main.py` → `csv_io.py` | `_read_parameters_section`, `_parse_imported_params`, `_phase_label_to_index`, CSV export formatter → Qt-free `csv_io.py`; `main.py` delegates via `csv_io.load_parameters()` / `csv_io.write_export()` |
| **§2.3+§2.1+§2.4** | all modules → `constants.py` | Phase-correction tokens (`CorrMode`), equipment colors (`SPK_COLOR`, `MIC_COLOR`), wall name strings and pairs (`WALL_*`, `WALL_PAIRS`, `WALL_NAMES`) — previously duplicated independently in `main.py`, `physics.py`, `render.py`, `graphs.py` |

**Net change:** `main.py` reduced by ~240 lines. Three new source files added:
`widgets.py`, `csv_io.py`, `constants.py`. No physics, no signal wiring, and no
UI layout was changed.

---

## [1.2.2] - 2026-06-18

### Fixed: Full-band Scaling — Accurate Mode Normalization

The Calibrated mode was rendering almost entirely blue due to two issues:

1. The original 2-sigma clipping (`mean + 2σ`) as the per-frequency spatial
   reference overestimates the typical pressure level, pushing the calibrated
   median too high. The median of spatial-peak values across all frequencies
   is used instead, giving a reference that better reflects the room's typical
   pressure distribution.
2. A symmetric ±20 dB window was too wide — measured data showed the actual
   range above the median reaches only +12 to +18 dB, while nulls at modal
   nodes can extend to −50 dB or below.

**Fix:** switched the calibration reference to the cross-frequency median and
replaced the symmetric window with an asymmetric fixed window `[−24 dB, +15 dB]`
relative to that median. Some clipping at the extremes is intentional — it
improves mid-range contrast at the cost of saturating deep nulls and sharp
antinodes.

| dB re. median | Colour |
|---|---|
| −24 dB and below | Blue |
| 0 dB (median) | Green |
| +15 dB and above | Red |

**Files changed:** `render.py` (`_normalize()` accurate-mode branch), `main.py`
(removed diagnostic prints). `physics.py` and `graphs.py` unchanged.

## [1.2.1] - 2026-06-18

### Added: Full-band Scaling Mode

Previously, the 3D pressure field was normalized per-frequency, making it
impossible to compare relative loudness across frequencies. This release adds
an optional **Full-band scaling** mode with a single normalization reference
derived from the global maximum pressure across the entire frequency band.

#### New Controls (below the frequency slider)

- **Full-band scaling** checkbox — toggles cross-frequency normalization on/off
- **Calibrate** button — launches an accurate full-band background sweep
- Progress label — shows live sweep progress ("Calibrating... 34%")

#### Two-tier Operation

- **Approximate mode** (instant): uses the peak of the already-computed 1D
  response curve to compute one reference 3D field. Activates immediately on toggle.
- **Accurate mode** (after Calibrate): `CalibWorker` (QThread) sweeps all
  frequencies in `FREQ_1D_STEP` steps, collecting the spatial maximum at each.
  Runs in the background; UI remains interactive. Cache persists until geometry changes.

#### Cache Invalidation

Triggered by any parameter that affects the 3D field (room dimensions, speaker/mic
positions, wall reflections, source count, phase mode, room scatter).
**Not** triggered by display-only parameters: **Show room modes** and
**Listening Area** (neither affects `calc_tensor_space()`).

#### Files Changed

| File | Change |
|---|---|
| `render.py` | `_normalize()` and `update_mesh()` accept optional `global_max` param |
| `main.py` | Added `CalibWorker`, full-band state management, and UI controls |
| `physics.py` | Unchanged |
| `graphs.py` | Unchanged |

## [1.2.0] - 2026-06-10
### Added
- **Room Scatter Slider**: Added a dynamic UI slider ("Advanced Acoustics" section) to simulate room order damping. The physics engine applies an $n^2$ (square of the mode order) penalty to high-order modes, accurately simulating wave scattering by furniture and irregular walls.
- **Listening Area Slider**: Added a continuous slider (0.0m to 0.3m) to replace the static spatial smoothing toggle. It dynamically averages sound pressure within a specified radius around the microphone, more accurately simulating human hearing characteristics.

### Changed
- **Dynamic UI & Unified Frequency Architecture**: Refactored `config.py` to establish a Single Source of Truth for frequency bounds (`MIN_FREQ` and `MAX_FREQ`). Changes in the Settings dialog now instantly update the main UI slider limits and 2D graph X-axis bounds without requiring an application restart.
- **Physics Engine Terminology**: Refactored internal variable names and comments. "Energy Weighting" variables (e.g., `mode_weight`) were renamed to `mode_norm` to accurately reflect their mathematical definition as Modal Normalization constants in the wave equation.
- **Settings UI Cleanup**: Removed obsolete technical debt, including `SMOOTHING_RADIUS` and redundant plot boundaries, streamlining the Settings dialog.

### Fixed
- **Statistical Color Clipping (2-Sigma Rule)**: Fixed an issue where extreme high-pressure hotspots (e.g., in room corners) would compress the global color scale, rendering the rest of the room as a giant blue cancellation zone. The 3D volume rendering now applies a robust 2-sigma statistical clipping method to preserve rich color gradients and interference patterns across the entire space.
- **Volume Rendering Opacity Tuning**: Adjusted the transparency mapping (`OPACITY_TF`) to counter the visual density introduced by the 2-sigma clipping. Mid-band sound pressure is now fully transparent, creating a clear, "velvet glass" effect that beautifully isolates acoustic peaks and cancellations without obscuring the equipment markers.

## [1.1.2] - Minor Visual & VTK Rendering Fixes
### Fixed
* **3D Grid Rendering Bug**: Fixed an upstream VTK bug where the 3D bounding box (CubeAxesActor) would incorrectly stretch or fail to draw grid lines for room dimensions under 2.5 meters.
* **UI Clean-up**: Replaced the distracting axis tick numbers with clean, evenly spaced 4-division grid lines that perfectly scale with any room dimension, dramatically improving the visual clarity of the 3D space.

### Changed / Improved
* **Mode Energy Weighting**: Overhauled the core physics engine to apply realistic amplitude decay based on mode types. Oblique and Tangential modes now carry less energy than Axial modes, mirroring real-world wall reflections.
* **Complex Field Accuracy**: Fixed the issue where the "True Complex Field" mode would generate excessive cancellation zones (blue) at high frequencies and unnatural extreme peaks (red) in room corners at low frequencies. The simulation is now substantially more accurate and true to physical acoustics.
  
## [V1.1.1] - 2026-06-05
### Added
- Added a splash screen (`pyi_splash`) during startup to provide visual feedback while heavy libraries (PyVista, PySide6) are loading.

### Fixed
- **Hotfix:** Added `os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"` to prevent the application window from exceeding the screen size on Windows systems with Display Scaling >100%. The UI is now strictly rendered at the intended 1600x1000 physical pixels regardless of OS scaling settings.

## [V1.1.0] - 2026-06-03
### Added
- **First Official Release (Windows Standalone).**
- Migrated the application from Streamlit to a native PySide6 desktop app.
- Implemented robust 3D visualization using PyVista with strict camera-preservation architecture.
- **Feature 1:** Added "Show room modes" toggle to overlay calculated room mode frequencies on the 2D frequency response plot.
- **Feature 2:** Added "Contour Mode" toggle. Implemented Statistical Scaling via Standard Deviation to render transparent iso-surface shells, providing a clearer view of the sound field compared to the dense Volume mode.
- Added CSV Export functionality for all parameters, frequency response, and room modes.
- Added settings dialog with JSON persistence.