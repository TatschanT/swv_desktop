# Standing Wave Viewer — Session Handoff Document
**Date:** 2026-08-29  
**Status:** **V1.4.0** ✅ — Modal Collision Hazard overlay (2D frequency response) + 4:6 panel rebalance complete. Metric and 2D plot verified headlessly; **3D view not exercised (needs a real display)**.  
**Project:** `swv_desktop` (`/home/ttatsuta/Projects/swv_desktop`)  
**Venv:** `.venv/` (Python 3.14, PySide6 6.11, PyVista 0.48, pyvistaqt 0.11, Matplotlib 3.10, NumPy 2.4)

---

## 1. Session Summary

### V1.0 (Streamlit → Desktop migration, all 5 polish TODOs)

| Phase | Deliverable |
|-------|-------------|
| 1 | UI skeleton — fixed 1600×1000 window with left/center/right panels, `LabeledSlider` + `XYZSliders` widgets, room-modes `QTableWidget`, wall-reflection sliders, placeholder frames |
| 2 | Controller — room-modes physics wired to sliders; room dimension→position slider clamping (`setMaxValue`); default values from `config.AppDefaults` |
| 3 | PyVista 3D view — `pyvistaqt.QtInteractor` volume rendering; in-place scalar + geometry updates; X-ray overlay markers; checkerboard floor; cube-axes framing |
| 3.5 | Visual polish — X-ray overlay on correct layer; floor z=-0.01 z-fight fix; scalar bar (later removed); `reset_camera(bounds=...)` on room resize only |
| 3.9 | L/R symmetry link — verified against `old_src`: X mirrored (`spk2.x = Lx - spk1.x`), Y/Z match; Speaker 2 locked while linked |
| 4 | Matplotlib 2D graphs — `Plot2DWidget` with top-down room layout (left) + frequency response (right); smart recompute gating |
| 4.1 | `committed` signal + release-gating; camera refit on room resize only; fixed freq-graph Y-axis `[-25, 5]`; live dB annotation |

### V1.1 (Feature additions — all complete)

| Feature | Deliverable |
|---------|-------------|
| 1 | Room-mode frequency guide lines on the 2D response plot |
| 2 | 3D rendering mode toggle: Volume vs. Contour ("Clear Visibility") |
| 3 | PyInstaller path-resolution helpers for Windows `.exe` packaging |

### V1.1.1 (Post-release hotfixes)

| Fix | Deliverable |
|-----|-------------|
| HiDPI scaling | `QT_ENABLE_HIGHDPI_SCALING=0` prevents window overflow on Windows with Display Scaling >100% |
| Startup splash | `pyi_splash` screen shown while heavy libraries (PyVista, PySide6) load in frozen build |

### V1.1.2 (Physics accuracy & VTK rendering fixes)

| Fix / Change | Deliverable |
|--------------|-------------|
| VTK grid rendering | Fixed CubeAxesActor bug where rooms <2.5 m caused stretched/missing grid lines; replaced axis tick numbers with clean 4-division grid lines that scale with any room dimension |
| Mode Energy Weighting (mode_norm) | Overhauled physics engine — Oblique and Tangential modes now carry less energy than Axial modes (realistic amplitude decay based on mode type, mirroring real-world wall reflections) |
| Complex Field Accuracy | Fixed excessive cancellation zones (blue) at high frequencies and unnatural extreme peaks (red) in corners at low frequencies in "True Complex Field" mode |

### V1.2.0 (Advanced acoustics — all complete)

| Feature | Deliverable |
|---------|-------------|
| Room Scatter slider | Order-dependent modal damping in Advanced Acoustics group |
| Listening Area slider | Continuous mic-cube RMS averaging; replaced boolean smoothing checkbox |
| Unified frequency bounds | `MIN_FREQ`/`MAX_FREQ` single source of truth across physics + UI |
| 2-sigma clipping | Robust normalisation in `render._normalize` to suppress hotspot wash-out |

### V1.2.1 (Full-band scaling — initial implementation)

| Feature | Deliverable |
|---------|-------------|
| Full-band scaling UI | Checkbox + Calibrate button + progress label below the frequency slider |
| Approximate mode | Instant: one 3D field at the 1D-response peak; `_global_max` used as normalisation reference |
| Accurate mode | `CalibWorker` (QThread) sweeps all frequencies; UI stays interactive during sweep |
| Cache invalidation | Cleared on any geometry change; display-only params (Show modes, Listening Area) do NOT invalidate |

### V1.3.0 (Room Data Import + Schroeder Frequency Display + Structural Cleanup)

| Feature / Change | Deliverable |
|------------------|-------------|
| Room Data Import | "Import data" button between Export/Settings; reads `[Parameters]` section of exported CSV; validates all values before applying any; signals blocked during batch-set; single recompute after import; clean error dialog on any failure |
| Schroeder Frequency Display | `schroeder_frequency()` in `physics.py`; live-updating `Est. Schroeder: ~NNN Hz` label beneath the frequency-response curve; `valueChanged` wired to all room-dim + wall-reflection sliders |
| **Structural Cleanup (5 commits)** | `widgets.py` (view widgets extracted from `main.py`); `csv_io.py` (Qt-free CSV parse/format); `constants.py` (phase tokens, colors, wall names); `_num_src()` + `_physics_snapshot()` helpers; dead overlay code removed from `render.py`. `main.py` −240 lines. No physics or UI layout changes. |

### V1.3.1 (Flat-field warning + keyboard/wheel commit debounce)

| Fix / Change | Deliverable |
|--------------|-------------|
| Flat-field warning | New label under "Wall reflection coefficients" reads "⚠ All walls fully absorptive (R=0) — field has no spatial structure" only when `Rx == Ry == Rz == 0` simultaneously; a single wall at R=0 (inspecting that wall's first-order reflection) does NOT trigger it |
| Keyboard/wheel commit debounce | `LabeledSlider` now fires `committed` for keyboard (arrow/Page/Home/End) and mouse-wheel changes too, via a 150 ms single-shot debounce gated on `QSlider.isSliderDown()`; mouse-drag commit-on-release is untouched (zero added cost) |

### V1.4.0 (Modal Collision Hazard overlay + 2D panel rebalance)

| Feature / Change | Deliverable |
|------------------|-------------|
| `hazard.py` (new) | Pure-NumPy MCFD metric, no Qt/Matplotlib. Two models: "Original" (fixed 29-mode set, constant σ=3 Hz, score NOT divided by N, independent of wall absorption entirely) and "v5" (direction-cosine axis weight, γ order penalty with PINNED `GAMMA_MIN`, Schroeder roll-off, σ(f)∝1/f, score divided by N). Scores are NOT comparable between models. **Verified numerically exact against the research code** |
| Hazard overlay UI | 3-way `QComboBox` (Off / Original / v5) beside "Show room modes"; default Off, so V1.3.1 behaviour is unchanged until opted into |
| Overlay drawing | Amber density backdrop on a `twinx()` sibling of `ax_freq`, created ONCE in `__init__` (see 2.12); peak-normalised in the view, raw in the metric; z-order below the mode lines, response curve and marker |
| Third recompute category | Hazard depends ONLY on room dims + the six wall sliders + the model; memoized on exactly that key, so moving the mic costs zero hazard computation (see 2.5) |
| 2D panel rebalance | Width ratio 1:1 → 4:6 and `figsize` 3.2 → 3.4 in, via a single `add_gridspec()` carrying both the split and the margins; right margin 0.97 → 0.93 to fit the hazard axis label |

### V1.2.2 (Full-band scaling — accurate mode normalization overhaul)

| Feature | Deliverable |
|---------|-------------|
| Median-centred dB scale | `CalibWorker` now emits `(median_pressure, db_range)` instead of a single `global_max` |
| Asymmetric dB window | `[−24 dB, +15 dB]` relative to the swept median (replaces symmetric ±20 dB) |
| Two-tier cache | `_calib_median` / `_calib_db_range` for accurate mode; `_global_max` retained for approximate mode |
| render._normalize | Three branches: accurate dB-window, approximate linear scale, per-frequency 2σ (default) |

---

## 2. Architectural Decisions & Critical Gotchas

**These rules held across every version without exception. Future agents MUST follow them strictly — any deviation risks invisible renders, camera resets, or signal storms.**

### 2.1 VTK / PyVista Volume Rendering — In-Place Update Rule

**Problem:** `add_volume()` binds the mapper to a **shallow copy** of the `ImageData`. The copy shares scalar arrays by reference but copies geometry (`spacing`, `origin`, `extent`) by value.

**Consequences:**
- Replacing `grid.point_data["Pressure"] = new_array` silently creates a new array; the mapper still points at the old (all-zeros) buffer → volume is invisible.
- Changing `grid.spacing` alone never reaches the mapper → volume stays clipped to the original bounding box.

**Correct update pattern (both must be present):**

```python
# Scalar update (in update_mesh):
arr = self.grid.point_data["Pressure"]
arr[:] = new_scalars                              # write INTO the existing buffer
self.grid.point_data.active_scalars_name = "Pressure"
self.grid.GetPointData().GetScalars().Modified()  # tell VTK the buffer changed
self.grid.Modified()

# Geometry update (rebind done ONCE in __init__ after add_volume):
self._vol_mapper = self.vol_actor.GetMapper()
self._vol_mapper.SetInputData(self.grid)          # now mapper IS self.grid, not a copy
# Then in update_mesh:
self.grid.spacing = self._spacing(room)
self.grid.Modified()
self._vol_mapper.Modified()
```

### 2.2 Camera Preservation — Never Call `plotter.clear()`

**Rule:** All actors (volume, contour, floor, outline, markers, cube-axes) are created **exactly once** in `Render3D.__init__`. `update_mesh` only mutates existing actor/mesh data, then calls `plotter.render()`. No `clear()`, no `remove_actor()`, no `add_*` calls during updates.

**Why:** `plotter.clear()` destroys and recreates the render window state, resetting the camera position, zoom, and rotation — breaking the "camera preserved" feature.

**Geometry-change helpers used instead of rebuilding:**
- `mesh.copy_from(new_mesh)` — updates an existing PolyData in place (floor, outline, markers, contour shells)
- `actor.SetVisibility(bool)` — hides/shows without removing (spk2 in mono mode, volume↔contour toggle)
- `actor.SetBounds(...)` — repositions the CubeAxesActor

**Camera refit exception:** On **room resize only**, call `self.plotter.reset_camera(bounds=self.grid.bounds)`. This recenters and steps back while preserving view direction (the user's rotation is kept). Detected via `room_resized = new_spacing != self._last_spacing`.

### 2.3 X-Ray Marker Overlay — Layer Collision

**Problem:** `pyvistaqt.QtInteractor` adds its orientation-axes widget on **layer 1**. Placing the marker overlay on layer 1 causes the axes widget to overdraw the markers.

**Fix:** In `_setup_overlay`, scan all existing renderers and pick `top_layer = max_existing_layer + 1` (lands on layer 2 in practice). Markers are moved from the main renderer into this overlay renderer; the overlay shares the main camera so everything stays synchronized.

### 2.4 Signal Gating — `valueChanged` vs `committed`

`LabeledSlider` emits two signals:

| Signal | When | Use for |
|--------|------|---------|
| `valueChanged(float)` | Every tick while dragging | Lightweight live UI (QLineEdit text, moving the 2D graph marker line) |
| `committed(float)` | `sliderReleased` + `editingFinished` | Heavy physics recompute (3D field, 1D freq response) |

**Wiring matrix (current state):**

```
Frequency slider:
  valueChanged → _on_freq_changed:
      plot2d.update_freq_marker(freq)          # always: just moves the red line
      if Dynamic ON: _refresh(recompute=False) # optional live 3D
  committed    → _on_freq_committed:
      _refresh(recompute_response=False)       # 3D update; freq-response curve is freq-independent

Room / Speaker / Mic / Wall sliders / room_scatter:
  valueChanged → _on_param_changed:
      if Dynamic ON: _refresh(recompute=True)  # live preview
  committed    → _on_param_committed:
      _refresh(recompute_response=True)        # recompute, THEN _invalidate_calibration()

listening_area / Show room modes:
  valueChanged → _on_param_changed (live preview)
  committed / toggled → _on_display_param_committed:
      _refresh(recompute_response=True)        # NO invalidation — 3D field unchanged

Source / Phase combos:
  currentIndexChanged → _on_param_committed   # discrete commit, always invalidates

Full-band checkbox / Calibrate button:
  toggled   → _on_fullband_toggled            # manages cache reuse, approx compute
  clicked   → _on_calibrate_clicked           # launches CalibWorker
```

**Critical ordering in `_on_param_committed`:** calls `_refresh(recompute_response=True)` FIRST (so the 1D curve is fresh), THEN `_invalidate_calibration()` (which reads the fresh curve to compute the approximate reference).

### 2.5 Frequency Response — Recompute Trigger Logic

The 1D frequency response curve is **independent of the current frequency** (it shows dB at *all* frequencies). Therefore:
- Moving the frequency **slider** must NOT recompute the curve — only the vertical marker line moves.
- Room / speaker / mic / wall / source / phase / room_scatter changes DO require a recompute.
- `listening_area` and `show_modes_chk` ALSO trigger `recompute_response=True` (the 1D curve changes), but they do NOT invalidate the Full-band calibration cache.

**Third category (V1.4.0) — the Modal Collision Hazard overlay.** Strictly
narrower than both of the above:

| | Depends on | Does NOT depend on |
|---|---|---|
| `hazard.compute()` | `Lx`, `Ly`, `Lz`, the six wall reflection sliders, the selected model | speaker/mic position, `num_src`, `corr_mode`, `listening_area`, Room Scatter (pinned at 0.30 inside `hazard.py`), the current frequency |

Memoized in `MainWindow._hazard_result()` on exactly that dependency set, so
moving the mic — which still fires a full `_refresh(recompute_response=True)` —
costs **zero** hazard computation. The cache is dropped in
`_on_hazard_mode_changed()` because the model is part of the key.

**The key holds the six wall values individually, NOT `Rx`/`Ry`/`Rz`.** The
axis means do not determine `f_s`: absorption is per-wall `1 - r²`, so walls of
`(1.0, 0.6)` and `(0.8, 0.8)` share a mean of `0.8` but have different total
absorption and therefore different Schroeder frequencies (verified: `f_s` moves
184.6 → 187.1 Hz across that edit while `Rx` stays at 0.80). A mean-keyed cache
would serve a stale curve for it.

The cheap `update_freq_marker()` path must never touch the hazard artists.

### 2.6 Reflection Coefficients

`RoomConfig.Rx/Ry/Rz` must not be zero — when `R=0`, `calc_shape(n, pos, L, 0)` collapses to a spatial constant, rendering the volume pressure field flat (invisible). Correct derivation:

```python
Rx = (wall_sliders["Left (X=0)"].value() + wall_sliders["Right (X=Lx)"].value()) / 2.0
Ry = (wall_sliders["Front (Y=0)"].value() + wall_sliders["Back (Y=Ly)"].value()) / 2.0
Rz = (wall_sliders["Floor (Z=0)"].value() + wall_sliders["Ceiling (Z=Lz)"].value()) / 2.0
```

**V1.3.1 update:** a single wall at `R=0` is a legitimate, supported way to
inspect that wall's first-order reflection in isolation — only ALL THREE axes
simultaneously at `R=0` collapses the whole field, and `main.py`'s new
`_update_flat_field_warning()` now surfaces that exact case to the user
instead of leaving the view silently blank. The underlying rule above (no
runtime clamp exists on the wall sliders) is unchanged.

### 2.7 L/R Symmetry — Verified Mirror Axes

From `old_src/main.py` (verified, not assumed):
- `spk2.x = Lx - spk1.x` — **X is mirrored** across room width
- `spk2.y = spk1.y` — Y is **identical**
- `spk2.z = spk1.z` — Z is **identical**

Additionally, `_sync_symmetry` is also triggered by `room.x.valueChanged` because `spk2.x` depends on `Lx`.

### 2.8 PyInstaller Path Resolution

Two helpers live at the top of `config.py`:

| Helper | When to use | How it works |
|--------|------------|--------------|
| `get_resource_path(relative)` | Read-only bundled assets (logo image, etc.) | `sys._MEIPASS` in frozen build, `os.path.abspath(".")` in script mode |
| `get_user_data_path(filename)` | Read/write user data (`settings.json`) | `os.path.dirname(sys.executable)` in frozen build, `os.path.abspath(".")` in script mode |

**Why the split matters:** `sys._MEIPASS` is a temporary extraction directory deleted when the `.exe` exits — any file written there is lost. Writable files MUST go to the directory containing the executable.

### 2.9 HiDPI Scaling Lock

`os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"` is set at the very top of `main.py`, before any Qt imports. This hard-locks the window to its intended 1600×1000 physical pixels regardless of Windows Display Scaling. Without it, a 150% OS scaling setting would render the window at 2400×1500 — too large for a 1080p screen.

**Rule:** This env-var must remain at the module top-level so it takes effect before `QApplication` initialises.

### 2.10 Mode Energy Weighting — `mode_norm`

In `physics.py`, mode amplitude is weighted by mode type (Axial / Tangential / Oblique) to reflect real-world energy decay from wall reflections:

- **Axial** (one non-zero index): full amplitude — reflects off only 2 walls.
- **Tangential** (two non-zero indices): reduced amplitude — reflects off 4 walls, more loss.
- **Oblique** (all three indices non-zero): lowest amplitude — reflects off all 6 walls.

### 2.11 Full-band Scaling Architecture (V1.2.1–V1.2.2)

**State variables on `MainWindow`:**

| Variable | Type | Meaning |
|----------|------|---------|
| `_global_max` | `float \| None` | Approximate-mode linear reference (one 3D field at peak freq) |
| `_calib_median` | `float \| None` | Accurate-mode swept median pressure (linear) |
| `_calib_db_range` | `float` | Accurate-mode +/- dB half-window (currently 20.0 matching the signal; applied asymmetrically in `render.py`) |
| `_calib_accurate` | `bool` | True only after a full Calibrate sweep completes |
| `_calib_worker` | `CalibWorker \| None` | Running worker (identity-check used to detect stale results) |

**`_normalize` dispatch order in `render.py`:**
1. `calib_median` supplied → accurate dB-window: `db_vals = 20·log10(clip(values/calib_median, 1e-9, 1.0))`, then `(db_vals + db_range) / (2·db_range)` clipped to [0,1].
2. `global_max` supplied → approximate: `clip(values/global_max, 0, 1)`.
3. Neither → per-frequency 2σ (unchanged default).

**Worker identity check:** `_on_calib_finished(median, db_range, worker)` guards `if worker is not self._calib_worker: return`. This silently discards results from a worker whose reference was dropped by `_invalidate_calibration` (geometry changed mid-sweep).

**Thread safety:** `fullband_chk` and `calibrate_btn` are both disabled during a running sweep. `closeEvent` calls `worker.wait()` to prevent "QThread destroyed while running" on app exit.

**Calibrate button state machine:**

| Condition | Button text | Enabled |
|-----------|-------------|---------|
| Full-band OFF | "Calibrate" | No |
| Full-band ON, no cache | "Calibrate" | Yes |
| Full-band ON, approximate cache | "Calibrate" | Yes |
| Full-band ON, accurate cache | "Calibrated ✓" | No |
| Sweep running | "Calculating..." | No |

### 2.12 Matplotlib `twinx()` — Create-Once Rule (V1.4.0)

**Rule:** `self.ax_hazard = self.ax_freq.twinx()` is called **exactly once**, in
`Plot2DWidget.__init__`. Never inside an update method.

**Why:** each `twinx()` call constructs a **new** `Axes` and registers it on the
figure. In a long-lived Qt app, calling it per redraw accumulates sibling axes
for the lifetime of the process — the 2D analogue of §2.2's "never call
`plotter.clear()`".

**The trap:** `update_freq_response()` starts with `ax.clear()`, which does
**not** remove a twin sibling. The twin survives, so it must be cleared
explicitly (`_hide_hazard()` / the `clear()` at the top of `_draw_hazard()`).
Deleting and recreating it instead would reintroduce the leak.

**Three things `Axes.clear()` resets that must be re-applied on every redraw**
(all three were found by rendering the figure headlessly, not by reading docs):

| Reset by `clear()` | Symptom if not re-applied | Re-applied in |
|---|---|---|
| `ax_freq`'s background patch → visible | The opaque patch hides the hazard fill beneath it — overlay looks like it never drew | `_restack()` |
| A twin's y-axis → back to the **left** side | The hazard label and ticks land across the middle of the response plot | `_draw_hazard()` |
| All artist styling on the twin | Default light-theme ticks on the dark palette | `_draw_hazard()` |

**Cross-axes stacking:** Matplotlib draws whole `Axes` in z-order, so artist
z-order cannot mix across the two. The backdrop has to *be* the axes that draws
first: `ax_hazard.set_zorder(0)`, `ax_freq.set_zorder(1)`, and `ax_freq`'s patch
made invisible so the fill shows through. Losing that patch is invisible in
practice — the figure behind it is already `BG`.

**Layout margins:** the gridspec's `right` is `0.93`, not `0.97`. The hazard
axis needs ~0.3 in for its tick labels and rotated ylabel; at `0.97` the label
was drawn off the canvas entirely. It is held constant across both overlay
states so the response curve never shifts sideways when the overlay is toggled.

### 2.13 Hazard Metric — Pinned vs. Live Parameters (V1.4.0)

`hazard.py` is a **pure-NumPy sibling** of `physics.py`: it imports `physics`
(for `schroeder_frequency` only) but never writes to it, and imports no Qt or
Matplotlib. Every constant in its "pinned" block was calibrated against research
data and **must not be re-tuned** — see the CHANGELOG `[1.4.0]` coupling table
for the full list and the reasoning.

**The Schroeder frequency falls as absorption rises — this is correct and both
projects agree on it.** More absorption raises total absorption `A`, shortens
`RT60`, and widens each mode's bandwidth, so modal overlap `M(f) = 3(f/f_s)²`
reaches 3 at a *lower* frequency: `f_s` falls and the modal region **narrows**.
The v5 roll-off inherits this correctly — the hazard tail retracts as absorption
is added. (The V1.4.0 brief stated the opposite direction; that was an error in
the brief, confirmed and withdrawn by the author. `physics.schroeder_frequency`
is right and was never modified. Do not "fix" it.)

**`GAMMA_MIN` is pinned at 11.3, evaluated once at `GAMMA_REF_R = 0.80`.** It
must NOT be recomputed from the live reflections. Doing so renormalizes every
room so its own least-damped mode scores exactly `w_order = 1.0`, discarding the
absolute damping level: as absorption rises the constant `GAMMA_SCALE·(1−R_eff)`
term dominates γ, the spread across mode orders collapses, high-order modes stop
being penalized, more modes carry weight, and the score gets *worse* while the
tail correctly retracts — the curve says "better", the number says "worse".
Only `R_eff` inside `γ(n)` is live. This does not change how rooms **rank**:
`GAMMA_MIN` depends only on `R`, never on geometry, so at fixed walls the two
variants differ by a global scalar. `w_order > 1` for rooms more reflective than
the reference (2.13 for the fundamental at R=0.95) is expected — **do not
clamp it.**

#### What the score actually is (V1.4.0)

`w_order = GAMMA_MIN / γ(n)` is a **dimensionless quantity referenced to the
reference room**, not a self-normalised one:

| `w_order` | Reading |
|---|---|
| 1.0 | as damped as the least-damped mode of the reference room (R = 0.80) |
| 2.13 | half as damped as that (the fundamental at R = 0.95) |

The consequence is that **`GAMMA_REF_R` is versioning-relevant, not a tuning
knob.** Changing it silently invalidates every `S_v5` recorded before the
change — the numbers stay plausible and stop meaning the same thing. If it ever
must move, treat it as a breaking change to the metric and re-baseline the
research set alongside it.

#### What the score is NOT — cross-room comparison (verified 2026-08-30)

**"Reference room" above means a reference DAMPING LEVEL (R = 0.80), not a
reference GEOMETRY.** These are trivially easy to conflate, and the distinction
is the entire scope of the score. Pinning `GAMMA_MIN` bought exactly one thing:
within **one** room, changing absorption now moves curve and number in the same
direction. It bought **nothing** about comparing two different rooms.

`S_v5` and `S_orig` are **not comparable between rooms of different size.**
`D(f)` is scale-dependent by construction — `σ ∝ 1/f` while mode spacing
`∝ 1/L` — so enlarging a room at constant proportions raises the score purely
mechanically. Measured, all six walls at R = 0.80:

| room | `S_v5` | `S_orig` |
|---|---|---|
| 4.42 × 3.34 × 2.40 m | 0.006904 | 1.4805 |
| the SAME SHAPE × 1.5 | 0.019385 | 3.1143 |
| the SAME SHAPE × 2.5 | 0.061392 | 7.0022 |

**~8.9× "worse" for an acoustically identical geometry.** `graphs.py
._draw_hazard` already states the mechanism in its docstring (~10× at 2.5×); the
measurement above confirms it end-to-end through `compute()`.

Two consequences that must not be lost:

1. The CHANGELOG's *"four geometries, identical ordering at R = 0.80 and
   R = 0.60"* verifies that **the pinned and live `GAMMA_MIN` variants rank
   rooms identically** — it does NOT license comparing absolute scores across
   sizes. Do not cite it as if it did.
2. The displayed curve is peak-normalized per room (`curve / peak_value`, axis
   label `"Hazard (relative, this room's peak = 1)"`), so the overlay is not
   cross-room comparable either, by design.

If cross-room comparison is ever wanted, that is the deferred fixed-constant
normalization below — a metric change of the same weight class as moving
`GAMMA_REF_R`, not a display tweak. **Do not slip it into an unrelated
release.** Note also that any such change would invert the sign of a
scale-invariance property test, so do not freeze today's scale dependence as an
assertion in the meantime; record it as a baseline instead.

#### The reference sweep — the evidence a future change must keep reproducing

4.42 × 3.34 × 2.40 m, all six walls swept together. Confirmed exact against the
research code:

| all six walls at R | 0.95 | 0.90 | 0.80 | 0.70 | 0.60 | 0.40 |
|---|---|---|---|---|---|---|
| `f_s` (Hz) | 314.51 | 225.30 | 163.68 | 137.52 | 122.76 | 107.15 |
| `S_v5` | 0.010601 | 0.010484 | 0.006904 | 0.004414 | 0.002957 | 0.001465 |
| tail fraction > 150 Hz | 0.6325 | 0.6046 | 0.5657 | 0.5397 | 0.5216 | 0.4991 |

The tail column is not decoration: it is the evidence that **curve and score now
agree in direction.** Adding absorption must retract the tail *and* lower the
score. If a future change makes those two columns disagree, the V1.4.0
contradiction has been reintroduced.

#### Why the sweep is monotonic but strongly non-uniform — DO NOT "fix" the flat top

The steps are wildly uneven: 0.95 → 0.90 moves the score **1.1 %**, while
0.90 → 0.80 moves it **34 %**. Read cold this looks like a clamp or a saturating
term, and someone will try to remove it. It is real model behaviour — the
research code produces the same shape.

**The cause is the `1/N` normalisation interacting with the `3·f_s` enumeration
ceiling — NOT saturation of γ.** As `R → 1`, `f_s` climbs steeply, the score's
enumeration ceiling `3·f_s` climbs with it, and `N` grows roughly as the cube of
that ceiling. The pair sum grows too, and near R = 0.95 the two nearly cancel:

| R | `f_s` | ceiling `3·f_s` | `N` | pair sum | `S_v5` = sum / N |
|---|---|---|---|---|---|
| 0.95 | 314.5 | 944 Hz | 3505 | 37.156 | 0.010601 |
| 0.90 | 225.3 | 676 Hz | 1350 | 14.153 | 0.010484 |
| 0.80 | 163.7 | 491 Hz | 549 | 3.790 | 0.006904 |

Between R = 0.95 and 0.90 the pair sum falls 2.6× and `N` falls 2.6× — hence the
1.1 % net. **`w_order` does not saturate anywhere in the swept range**: isolate
it (freeze the mode set and the roll-off at R = 0.80 and vary only `R`) and the
0.95 → 0.90 step is −32.2 %, squarely in line with every other step (−29 % to
−44 %). γ *would* eventually collapse onto its floor `GAMMA_BASE + s·(n²)` as
`R → 1`, but at R = 0.95 the `GAMMA_SCALE·(1−R_eff)` term is still 2.0 against a
`GAMMA_BASE` of 3.0 — comparable, not vanished. Saturation does not bite below
about R = 0.99.

**What this means for a would-be fixer:** the flat top is produced by two
load-bearing choices — the `1/N` division and the `3·f_s` ceiling — both of
which are required for exact agreement with the research code (see 2.13's
pinned-constants rule and A.6's dual-ceiling split). Flattening or steepening
that region means changing one of them, which breaks the reference point.
Don't.

The one that will look like a bug and is not: **the scatter term `s` is pinned
at 0.30 and deliberately ignores the Room Scatter slider.** That slider defaults
to `0.0`, so reading it would silently delete the γ order penalty in the default
state and make every score incomparable with the research set. `hazard.compute()`
has no scatter parameter at all, so the slider cannot leak in.

`S_orig` and `S_v5` are **not comparable to each other** (different weighting,
and only v5 divides by N). Never render them side by side without the model name
attached.

**The Original model is independent of wall absorption entirely** — fixed
29-mode set by index cap, constant σ, no roll-off, no order penalty. Nothing in
it reads `Rx/Ry/Rz` or `f_s`. So:

- The six wall sliders being **inert** while Original is selected is correct
  behaviour, not a bug. It is a statement about room proportions alone; feeding
  absorption into it would just make it v5 with fewer modes.
- The `f_s <= 0` guard is **v5-only**. Original renders normally in a fully
  reflective room and shows `f_s —` (matching main.py's `Est. Schroeder: —`).
  The non-positive-dimension guard covers both models.

Its weights (1.0 / 0.5 / 0.25) coinciding with `physics.MODAL_NORMS` is **not
numerology**: the wave equation's modal normalization constant is
`Λ = (1/2)^(number of non-zero indices)` — 1/2 axial, 1/4 tangential, 1/8
oblique, i.e. ratios 1 : 0.5 : 0.25 exactly. The naive model was implicitly
weighting each mode by the energy it holds. That is the physical justification
for weights that otherwise look arbitrary, and it explains why the model holds
up in small rooms: there neither the roll-off nor the order penalty bites, so
energy weighting is the whole story. (The same note lives in `hazard.py`'s
pinned-weights block, at the definition site.)

**What that predicts — and it is falsifiable.** The Λ derivation makes Original
a *legitimate baseline*, not a strawman: it is the energy-weighted answer, which
is the correct answer wherever energy weighting is the only physics in play. It
follows that Original should degrade **specifically in large rooms**, where the
roll-off and the order penalty carry physics that energy weighting alone cannot
see — modal overlap crowding the spectrum, and high-order modes decaying faster.
If a future comparison finds Original degrading in *small* rooms instead, or
degrading uniformly with room size, the Λ justification is wrong and this
subsection needs revisiting.

#### Known design tension — the curve shows shape, the score holds the level

The curve is **peak-normalized**, so it displays *shape only*: the absolute
level now lives exclusively in the score. This is precisely why the V1.4.0
`GAMMA_MIN` contradiction was easy to miss — **the curve structurally cannot
show the quantity that was moving the wrong way.** Any future change to the
scoring should be checked against the score directly, never inferred from how
the overlay looks.

> **Option (not implemented):** divide `D(f)` by a fixed constant — the
> reference room's peak value — instead of by each render's in-band maximum.
> The shape of any single room's curve is unchanged (constant factor); 1.0
> becomes a readable baseline that reflective rooms exceed visibly; and the
> normalization factor stops depending on the display window, which would
> dissolve the `peak_value` question in section 16 entirely.
> **Costs:** y-axis autoscaling, and one more version-relevant constant
> alongside `GAMMA_REF_R`.
> **Deferred pending observation on the real display. Do not implement.**


---

## 3. Codebase Structure (MVC)

```
swv_desktop/
├── main.py         # Controller + View skeleton (~1 230 lines after V1.3.0 cleanup)
│                   #   CalibWorker(QThread) — full-band background sweep
│                   #   MainWindow
│                   #   Signal wiring, _refresh(), _on_render_mode_changed()
│                   #   Full-band scaling: _invalidate_calibration(),
│                   #     _compute_approx_global_max(), _on_fullband_toggled(),
│                   #     _on_calibrate_clicked(), _on_calib_progress(),
│                   #     _on_calib_finished()
│                   #   _on_display_param_committed() — display-only handler
│                   #   symmetry logic, settings dialog opener
│                   #   _num_src() — returns 1 or 2 (V1.3.0 helper)
│                   #   _physics_snapshot() — PhysicsSnapshot namedtuple (V1.3.0)
│                   #   on_import_clicked / _import_set_slider /
│                   #     _apply_imported_params — CSV import (V1.3.0)
│                   #   _update_schroeder_display() — live label (V1.3.0)
│                   #   Entry point: main()
│
├── widgets.py      # View — reusable Qt widgets (extracted V1.3.0)
│                   #   mono() — Courier font factory
│                   #   LabeledSlider — float slider (valueChanged + committed)
│                   #   XYZSliders — titled group of three LabeledSliders
│                   #   make_placeholder — simple labelled placeholder frame
│
├── csv_io.py       # I/O — Qt-free CSV format logic (extracted V1.3.0)
│                   #   load_parameters(path) — read + validate [Parameters] section
│                   #   write_export(path, *, ...) — full three-section CSV export
│                   #   read_parameters_section, parse_parameters — parse helpers
│                   #   phase_label_to_index — case-insensitive phase-label match
│
├── constants.py    # Shared literals (extracted V1.3.0)
│                   #   CorrMode — phase-correction token strings
│                   #   HazardMode — off/original/v5 tokens (V1.4.0)
│                   #   SPK_COLOR, MIC_COLOR — equipment marker colors
│                   #   WALL_* — wall identifier strings (6 constants)
│                   #   WALL_PAIRS, WALL_NAMES — axis-paired and flat tuples
│
├── render.py       # View — 3D (PyVista)
│                   #   Render3D class: QtInteractor wrapper
│                   #   In-place volume + contour + geometry updates
│                   #   _normalize(values, global_max, calib_median, calib_db_range)
│                   #     3-branch normalization: accurate dB / approx / 2σ default
│                   #   update_mesh(..., global_max, calib_median, calib_db_range)
│                   #   set_grid_size()     — camera-preserving grid rebuild
│                   #   set_render_mode()   — visibility-only mode switch
│                   #   _contour_levels()   — statistical iso-surface thresholds
│                   #   _update_contour()   — in-place shell regen via copy_from
│                   #   _apply_visibility() — centralised actor show/hide
│                   #   X-ray overlay, checkerboard floor, cube-axes
│
├── graphs.py       # View — 2D (Matplotlib)
│                   #   Plot2DWidget(FigureCanvasQTAgg)
│                   #   Top-down room layout + freq response + dB annotation
│                   #   _freqs, _db — cached for Full-band approx-mode reference
│                   #   Room-mode guide lines (mode_freqs kwarg)
│                   #   rebuild_freqs() — config-driven frequency axis
│                   #   ax_hazard — twinx() sibling, created ONCE (V1.4.0, 2.12)
│                   #   _restack() / _draw_hazard() / _hide_hazard()
│                   #   add_gridspec 4:6 split + margins (V1.4.0)
│
├── hazard.py       # Model — Modal Collision Hazard density (V1.4.0)
│                   #   Pure NumPy; no Qt, no Matplotlib
│                   #   compute(mode, lx, ly, lz, walls, rx, ry, rz)
│                   #     -> HazardResult(f_grid, curve, peak_value,
│                   #        peak_freq, score, f_s, mode)
│                   #   _enumerate_modes()   — vectorised, freq-capped
│                   #   _enumerate_original()— the fixed 29-mode set
│                   #   _axis_weight(), _order_weight(), _rolloff(), _sigma()
│                   #   _pair_score(), _pair_curve() — chunked accumulation
│                   #   PINNED calibrated constants (incl. SCATTER = 0.30,
│                   #     deliberately NOT the Room Scatter slider — see 2.13)
│
├── settings_ui.py  # View + state — runtime settings dialog
│                   #   SettingsDialog(QDialog); exposes a curated subset
│                   #   of config.py via QSpinBox/QDoubleSpinBox
│                   #   load_settings()/save_settings() — JSON persistence
│                   #   Mutates config in place, emits settings_applied
│                   #   Uses get_user_data_path() for settings.json
│
├── physics.py      # Model — physics engine
│                   #   RoomConfig, Position dataclasses
│                   #   calc_room_modes(), calc_tensor_space()
│                   #   compute_f_response_1d(), compute_tensor_3d()
│                   #   schroeder_frequency() — Sabine/Schroeder estimate (V1.3.0)
│
├── config.py       # Model — constants + path helpers
│                   #   get_resource_path()  — bundled read-only assets
│                   #   get_user_data_path() — writable user files
│                   #   AppDefaults, PhysicalConfig, SimResolution
│
├── settings.json   # Persisted runtime settings (auto-created on first Apply)
├── images/         # Assets — SWVlogo_s.jpg (banner)
│
├── old_src/        # Original Streamlit app (reference only, do not import)
│
└── SESSION_HANDOFF.md   # This file
```

---

## 4–9. Completed Tasks (V1.0–V1.2.0)

*(Preserved from the previous handoff — see git history for V1.0–V1.2.0 detail.)*

See CHANGELOG.md entries `[1.1.0]` through `[1.2.0]` for the full record.

---

## 10. Completed Tasks (V1.2.1) — Full-band Scaling

### Feature — Full-band Scaling Mode (`main.py`, `render.py`) ✅

**UI controls** added as an `QHBoxLayout` row below the frequency slider (left-aligned):
- `fullband_chk` — `QCheckBox("Full-band scaling")`; default OFF.
- `calibrate_btn` — `QPushButton("Calibrate")`; enabled only when Full-band ON and cache absent.
- `calib_progress_lbl` — `QLabel("")`; shows "Calibrating... 34%" during sweep.

**Approximate mode** (instant, no background work):
1. Read `plot2d._db` and `plot2d._freqs` (already computed).
2. Convert dB → linear: `linear = 10 ** (db / 20)`.
3. Find peak-frequency index: `peak_freq = freqs[argmax(linear)]`.
4. Compute one `calc_tensor_space()` field at that frequency.
5. `_global_max = field.max()`.

**Accurate mode** (`CalibWorker`):
- Sweeps `MIN_FREQ..MAX_FREQ` in `FREQ_1D_STEP` steps; same frequency coverage as the 1D response curve.
- Per-frequency: `2σ`-clipped spatial max: `min(p.max(), mean + 2·std)`.
- Converts to dB, takes median, converts back to linear: emits `(median_pressure, 20.0)`.
- All parameters are a **snapshot** at worker construction time — mid-sweep UI changes are ignored.

**Cache invalidation** (`_invalidate_calibration`):
- Triggered by `_on_param_committed` (geometry changes), NOT by `_on_display_param_committed`.
- Drops the in-flight worker reference (identity check in `_on_calib_finished` silently discards its result).
- When Full-band is ON: immediately calls `_compute_approx_global_max()` and `_refresh()`.

**`render._normalize` changes:**
- Signature: `_normalize(values, global_max=None, calib_median=None, calib_db_range=20.0)`.
- New accurate branch (evaluated first): median-centred dB window mapped to [0,1].
- Existing approximate branch and 2σ default are unchanged.

---

## 11. Completed Tasks (V1.2.2) — Accurate Mode Normalization Overhaul

### Fix — Median-centred dB Scale (`render.py`, `main.py`) ✅

The original accurate-mode normalisation (`clip(values / global_max, 0, 1)`) rendered almost entirely blue because the raw spatial maximum was dominated by extreme corner peaks.

**Solution — median-centred asymmetric dB window:**

```
[median_dB − 24 dB, median_dB + 15 dB]  →  [0.0, 1.0]
```

The asymmetry (wider below, narrower above) reflects the measured pressure distribution: deep nulls extend to −50 dB or below, while peaks typically reach only +12–18 dB above the median. Some saturation at the extremes is intentional — it improves mid-range contrast.

| dB re. median | Colour |
|---|---|
| −24 dB and below | Blue |
| 0 dB (median) | Green |
| +15 dB and above | Red |

**Implementation detail:** The `calib_db_range` emitted by `CalibWorker` is `20.0` (symmetric), but `render._normalize` applies the window asymmetrically by clipping `values / calib_median` to `[1e-9, 1.0]` before the log. This means the upper bound of the window is effectively `0 dB re. median` (anything above the median is treated as 0 dB before the log), and the `[−20, 0] → [0, 0.5]` linear mapping is then stretched to fill [0, 1] by the asymmetric colour map. **If the asymmetry needs to change, modify the clip upper bound in `render._normalize` (currently `1.0`) and/or the `calib_db_range` constant (currently `20.0`).**

---

## 12. How to Run

```bash
cd /home/ttatsuta/Projects/swv_desktop
.venv/bin/python main.py
```

`QT_QPA_PLATFORM=xcb` is set inside `main.py` (Wayland fix). No additional flags needed.

**Note on headless verification:** `pyvistaqt.QtInteractor` needs a real display. Physics/config/logic can be unit-tested headlessly, but **3D visual behavior must be eyeballed interactively.**

---

## 13. Completed Tasks (V1.3.0)

### Feature A — Room Data Import (`main.py`) ✅

**UI:** Export/Import/Settings buttons sit in one toolbar row, all at `mono(9, bold)` / `setFixedHeight(34)`.

**New methods on `MainWindow`:**

| Method | Role |
|--------|------|
| `on_import_clicked` | File dialog → `csv_io.load_parameters(path)` → apply or error dialog |
| `_import_set_slider(slider, value)` | Clamp to `[_vmin, _vmax]` + log warning on clamp |
| `_apply_imported_params(v)` | Block all signals → set room dims first → re-sync limits → set rest → unblock → single refresh |

**Parsing helpers (in `csv_io.py` — Qt-free, extracted during structural cleanup):**

| Function | Role |
|----------|------|
| `read_parameters_section(path)` | `csv.reader` walk; collects `{name: value}` from `[Parameters]` only |
| `parse_parameters(raw)` | Type-converts and validates all values; raises `KeyError`/`ValueError` on bad input |
| `phase_label_to_index(label)` | Case-insensitive substring match → combo index |
| `load_parameters(path)` | Convenience wrapper: `read_parameters_section` → `parse_parameters` |

**Signal-storm prevention:** `blockSignals(True)` on every affected `LabeledSlider` and `QComboBox` during batch-set. Room dimensions applied before speaker/mic so position-slider maxima are correct when those values land.

**Post-import sequence:** `_update_source_state()` → `_sync_position_limits()` → `_sync_symmetry()` → `update_room_modes()` → `_update_schroeder_display()` → `_refresh(recompute_response=True)` → `_invalidate_calibration()`.

---

### Feature B — Schroeder Frequency Display (`physics.py`, `main.py`) ✅

**`physics.schroeder_frequency(lx, ly, lz, wall_reflections: dict) -> float`:**
- `_WALL_AREA_DIMS` maps each wall name → the two dimension keys whose product is area.
- `α_i = 1 − r_i²`; total absorption `A = Σ(area_i · α_i)`.
- `RT60 = 0.161 · V / A`; `f_s = 2000 · √(RT60/V)`.
- Returns `0.0` when A ≤ 1e-9 (fully reflective, divergence guard) or V ≤ 0.

**UI:** `schroeder_lbl` (`mono(9)`, `#aaaaaa`) in the row beneath the frequency-response curve (left of "Show room modes" checkbox). Formatted as `Est. Schroeder: ~NNN Hz` or `Est. Schroeder: —`.

**`_update_schroeder_display(*_)`:** calls `physics.schroeder_frequency` with current room dims + wall slider values; wired to `valueChanged` of all three room-dim sliders and all six wall sliders (live, main thread). Also called once at end of `__init__` and inside `_apply_imported_params`.

---

## 14. Completed Tasks (V1.3.0 Structural Cleanup)

Five commits on branch `refactor/structural-cleanup`. Each was verified before the
next by a smoke-test harness (launch → recompute → full-band → contour → export/import
round-trip → stable Schroeder `~192 Hz`).

### §3.1 — Extract view widgets → `widgets.py` ✅

`LabeledSlider`, `XYZSliders`, `mono`, `make_placeholder`, `DARK_BG`,
`PLACEHOLDER_TEXT` extracted from `main.py` into a new `widgets.py`. These are
pure Qt presentation classes with no dependency on `MainWindow` or the physics
model. `main.py` now does `from widgets import LabeledSlider, XYZSliders, mono`.

### §1.1 — Remove dead overlay code from `render.py` ✅

- `_setup_overlay` method (~27 lines) deleted — it was already commented out at its
  only call site and had no other use.
- `import vtk` removed — its only reference was inside `_setup_overlay`.
- Module docstring trimmed: X-ray/overlay paragraphs that described the dead code
  were removed to avoid confusing future readers.

### §4.1+§4.2 — Controller helpers in `main.py` ✅

**`_num_src(self) -> int`** — returns `2 if self.source_combo.currentText() == "2" else 1`.
Replaced 5 identical inline expressions.

**`_physics_snapshot(self) -> PhysicsSnapshot`** — gathers the seven values
(`room`, `spk1`, `spk2`, `mic`, `num_src`, `corr`, `room_scatter`) that every
physics call needs. A `PhysicsSnapshot` namedtuple is defined at module level
(after `BANNER_H`). Replaced 3 duplicate gather blocks.

### §3.2 — Extract CSV logic → `csv_io.py` ✅

All CSV format knowledge moved to a new Qt-free `csv_io.py`:
- `read_parameters_section`, `parse_parameters`, `phase_label_to_index`,
  `load_parameters` — import path
- `write_export(path, *, room, spk1, spk2, mic, ...)` — export path

`main.py` lost `import csv`, `_IMPORT_WALL_NAMES`, `_read_parameters_section`,
`_parse_imported_params`, `_phase_label_to_index`, and the inline export formatter.
Both `on_import_clicked` and `on_export_clicked` now delegate to `csv_io`.

### §2.3+§2.1+§2.4 — Centralise literals → `constants.py` ✅

New `constants.py` with no project-module imports (cycle-safe):

```python
class CorrMode:
    UNCORRELATED = "Uncorrelated"
    GLOBAL_CANCEL = "Global Cancel"
    TRUE_COMPLEX = "True Complex Field"

SPK_COLOR = "#38bdf8"   # speaker cyan-blue
MIC_COLOR = "#f4f4f4"   # mic bright white

WALL_LEFT = "Left (X=0)";  WALL_RIGHT = "Right (X=Lx)"
WALL_FRONT = "Front (Y=0)"; WALL_BACK = "Back (Y=Ly)"
WALL_FLOOR = "Floor (Z=0)"; WALL_CEILING = "Ceiling (Z=Lz)"
WALL_PAIRS = ((WALL_LEFT, WALL_RIGHT), ...)
WALL_NAMES = tuple(name for pair in WALL_PAIRS for name in pair)
```

`main.py`, `physics.py`, `render.py`, `graphs.py` all `import constants` and
reference `constants.SPK_COLOR` / `constants.WALL_LEFT` / `constants.CorrMode.*`
instead of their previous local copies.

---

## 15. Completed Tasks (V1.3.1)

Both fixes originated from real usage (not planned work), diagnosed and
verified interactively in this session.

### Fix A — Flat-Field Warning (`main.py`) ✅

**Root cause:** `physics.calc_shape(n, pos, L, R)` collapses to a spatial
constant (`1.0`, independent of `pos`) whenever `R == 0`. If `Rx`, `Ry` AND
`Rz` are all `0` at once (every wall-pair average zero), every non-zero mode
degenerates to a constant, so the 3D field has no spatial structure left —
`render._normalize`'s default 2σ branch then returns an all-zero scalar
array (`robust_max - robust_min < 1e-12`), and the volume renders fully
transparent with no explanation. This is reachable from ordinary UI use: the
wall sliders range `[0.0, 1.0]` with no lower-bound guard (see 2.6).

**New method `_update_flat_field_warning(self, *_)`:** reads `Rx, Ry, Rz` via
the existing `_wall_reflection()` helper (no physics recompute) and sets
`flat_field_lbl`'s text only when all three are below `1e-9`; clears it
otherwise. A single wall at `R=0` — deliberately inspecting that wall's
first-order reflection — leaves the other two axes intact and does NOT
trigger the warning.

**UI:** `flat_field_lbl` (`mono(9)`, `#e6a23c`, word-wrapped) sits directly
under the "Wall reflection coefficients" `QGroupBox`.

**Wiring:** all six wall sliders' `valueChanged` (not `committed`) → live
while dragging, mirroring `_update_schroeder_display`'s pattern. Also called
once at startup.

---

### Fix B — Keyboard/Wheel Slider Changes Never Committed (`widgets.py`) ✅

**Root cause:** with **Dynamic update** OFF (the default), the 2D/3D views
refresh only on `LabeledSlider.committed`, which was wired solely to
`QSlider.sliderReleased` — a signal Qt emits **only for a mouse
press-drag-release gesture**. Keyboard (arrow/Page/Home/End) and mouse-wheel
changes fire `valueChanged` (so the numeric read-out was correct) but never
`sliderReleased`, so `committed` never fired: the 2D marker / 3D field
silently kept the pre-change state until an unrelated slider was next
dragged-and-released, at which point everything jumped to the already-changed
values at once. Reported symptom: the mic-position marker on the 2D view
"doesn't move" or "jumps to the wrong place," very rarely and
irreproducibly — an input-method-dependent gap, not a random fault.

**Fix:** `LabeledSlider._on_slider()` now checks `QSlider.isSliderDown()`
(`True` only during an actual mouse drag). When a value change arrives
without an active drag, a single-shot `QTimer` (`COMMIT_DEBOUNCE_MS = 150`)
is (re)started; on timeout it emits `committed`. A burst — key-repeat, a fast
wheel scroll — keeps restarting the timer and so collapses into exactly one
emission once input settles. `sliderPressed` stops any pending timer so a
fresh mouse drag never races a stray leftover firing. A genuine mouse drag
is completely unaffected: it still commits instantly on release, unchanged.

**Verified interactively (2026-08-12):** drag mic slider (marker moves
live) → release → nudge one more tick with the arrow key while focus
remains on the slider → marker now updates after the debounce settles,
promptly enough that no added lag is perceptible.

**Known residual gap (not fixed, low priority):** `setMaxValue()` /
`setMinValue()` clamp notifications (room resize shrinking a speaker/mic
position back into bounds) still bypass `_on_slider()` — they call
`self.valueChanged.emit(...)` directly — so they aren't covered by this
debounce. In practice this self-corrects because the room-dimension slider
that triggers the clamp always fires its own `committed` on release; see the
nice-to-haves list below if this ever needs closing fully.

---

## 16. Next Session Roadmap

### V1.4.x follow-ups — pending validation, NOT to be implemented yet

Both are agreed in principle but blocked on validation against the research
data. Do not start either without a fresh brief.

| Follow-up | What it is | Why it is blocked |
|---|---|---|
| **"Both" hazard mode** | A fourth selector state drawing Original and v5 simultaneously in two colours | Needs a presentation that does not invite comparing the two scores, which are not comparable (see 2.13). The single-curve peak normalisation also has to be rethought for two curves |
| **Scale-invariant normalisation** | Normalise `D(f)` against the Weyl-law *expected* hazard density instead of the curve's own peak, letting the right axis become **absolute** rather than peak-relative | Needs validation that the Weyl expectation matches the measured baseline across room sizes. Until then peak-normalisation stands — it answers "where is this room weak", which is the honest question for the current curve |

### Outstanding nice-to-haves (no commitment)

- `SMOOTHING_SAMPLES` re-exposed in Settings under a clearer name (`LISTENING_AREA_SAMPLES`).
- Windows `.exe` packaging: PyInstaller `.spec` file.
- Per-mode scalar bar, contour opacity slider, export of the 3D field to VTK/VTI format, mode labels on the guide lines.
- The `calib_db_range` asymmetry may need further tuning — the current implementation clips the ratio upper bound at `1.0`, making the upper dB window effectively 0 dB (values above the median all map to 0.5). A `10.0` clip would give a true +20 dB upper window if that proves preferable.
- `LabeledSlider.setMaxValue()` / `setMinValue()` clamp notifications still bypass the V1.3.1 commit-debounce (see Fix B's residual-gap note in section 15) — low priority since the room-dimension slider's own release already self-corrects it.

### Watch item — `peak_value` is an in-band maximum (V1.4.0, do not change yet)

`HazardResult.peak_value` is the maximum of `D(f)` over the **displayed
20–250 Hz band**, not the global maximum of the curve. In a small room with a
high `f_s` the true peak can sit above 250 Hz, so dragging the room-dimension
sliders could push the true peak in and out of the window and make the
peak-normalization factor **jump discontinuously**.

The author is watching for this on the real display. **Leave it as is for now.**
If it shows up, the fix is one of: relabel the read-out to `peak (in band)`, or
redefine the normalization explicitly as the in-band maximum. (A third route —
normalising against a fixed reference constant — would dissolve the question
entirely; see the design-tension note in 2.13. Also deferred.)

### Pending test/tooling work (V1.4.0) — none to be implemented without a brief

| Item | What it is | Why it is worth doing |
|---|---|---|
| **Property tests, not just golden values** | Assert that `S_v5` is strictly decreasing in `R` across the six-wall sweep, and that the four-geometry ordering is identical at R = 0.80 and R = 0.60 | The frozen reference point catches drift. These catch the *specific* bug that cost a full round: a change that keeps the reference point exact while reversing the direction off-reference. The live-`GAMMA_MIN` bug passed every golden-value check |
| **Headless 3D smoke test** | Build the figure under the Agg backend and write a PNG | It will not tell us whether the view looks *right*, but it will tell us it does not throw — which is most of what "un-exercised" currently costs us |
| **Instrumentation to settle `peak_value` without a display** | Compute `D(f)` over a wider band (20–500 Hz), compare its `argmax` against the in-band `argmax`, and flag when they differ or when the in-band peak lands within a bin or two of 250 Hz. Sweep the dimension sliders programmatically across the plausible geometry range and see whether the flag ever fires | If it never fires, the concern is theoretical and we relabel. If it fires, we get the exact geometry that triggers it — which is far better than waiting to notice a discontinuity by eye |

---

## 17. Session Conclusion

**V1.4.0** adds the Modal Collision Hazard overlay on top of the stable V1.3.1.
A new pure-NumPy `hazard.py` computes the MCFD metric in two models (Original
and v5); `graphs.py` draws it as a backdrop on a `twinx()` sibling and
rebalances the two 2D panels 1:1 → 4:6; `main.py` adds the selector and
memoizes the result on the metric's exact dependency set. `physics.py`,
`render.py` and the 3D pipeline are untouched.

The metric was verified headlessly (research agreement, live wall coupling,
pinned scatter, degenerate-room guard, 4.7 ms performance, memoization) and the
2D plot was verified by rendering it to PNG through Qt's offscreen platform.
**The 3D view still requires a real display and was not exercised.**

The metric was **confirmed numerically exact against the research code** by the
author — all six reference values to full precision, including the curve peak
value and its location, which validates the roll-off, `σ(f)` and the chunked
accumulation, not just the score. Two follow-up fixes then landed: `GAMMA_MIN`
pinned at its reference value (it had been recomputed live, which inverted how
the score responds to absorption), and the `f_s` guard narrowed to v5 only.

**This session is officially closed.** The next session should:

1. Read this document and `CHANGELOG.md` first.
2. **Read 2.13 before touching `hazard.py`.** Four things in it look like bugs
   and are not — this is the highest-value paragraph in the document:
   - the pinned scatter term (ignores the Room Scatter slider),
   - the pinned `GAMMA_MIN` (and `GAMMA_REF_R` being versioning-relevant),
   - the wall sliders being inert in Original mode,
   - the flat top of the absorption sweep between R = 0.95 and R = 0.90.
3. Note the `peak_value` watch item in section 16 — pending observation on the
   real display, not to be changed pre-emptively.
4. Do NOT start either V1.4.x follow-up, the deferred fixed-constant
   normalisation (2.13), or any section 16 pending item without a fresh brief.

**Still un-exercised:** the 3D view. Nothing in V1.4.0 touches `render.py`,
`physics.py` or the 3D pipeline — verified by diff across all eight commits —
but the app has not been launched end to end in this work. The headless 3D smoke
test in section 16 exists to shrink that gap.
