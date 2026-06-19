# Changelog

All notable changes to this project will be documented in this file.

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

**Files changed:** `main.py` (new `on_import_clicked`, `_read_parameters_section`,
`_parse_imported_params`, `_phase_label_to_index`, `_import_set_slider`,
`_apply_imported_params` methods; updated button row). `physics.py` unchanged.

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