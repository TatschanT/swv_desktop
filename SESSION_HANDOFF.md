# Standing Wave Viewer — Session Handoff Document
**Date:** 2026-06-19  
**Status:** **V1.3.0 STABLE** ✅ — Room Data Import + Schroeder Frequency Display complete. Session closed.  
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

### V1.3.0 (Room Data Import + Schroeder Frequency Display)

| Feature | Deliverable |
|---------|-------------|
| Room Data Import | "Import data" button between Export/Settings; reads `[Parameters]` section of exported CSV; validates all values before applying any; signals blocked during batch-set; single recompute after import; clean error dialog on any failure |
| Schroeder Frequency Display | `schroeder_frequency()` in `physics.py`; live-updating `Est. Schroeder: ~NNN Hz` label beneath the frequency-response curve; `valueChanged` wired to all room-dim + wall-reflection sliders |

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

### 2.6 Reflection Coefficients

`RoomConfig.Rx/Ry/Rz` must not be zero — when `R=0`, `calc_shape(n, pos, L, 0)` collapses to a spatial constant, rendering the volume pressure field flat (invisible). Correct derivation:

```python
Rx = (wall_sliders["Left (X=0)"].value() + wall_sliders["Right (X=Lx)"].value()) / 2.0
Ry = (wall_sliders["Front (Y=0)"].value() + wall_sliders["Back (Y=Ly)"].value()) / 2.0
Rz = (wall_sliders["Floor (Z=0)"].value() + wall_sliders["Ceiling (Z=Lz)"].value()) / 2.0
```

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

---

## 3. Codebase Structure (MVC)

```
swv_desktop/
├── main.py      # Controller + View skeleton
│                   #   CalibWorker(QThread) — full-band background sweep
│                   #   MainWindow, LabeledSlider, XYZSliders
│                   #   Signal wiring, _refresh(), _on_render_mode_changed()
│                   #   Full-band scaling: _invalidate_calibration(),
│                   #     _compute_approx_global_max(), _on_fullband_toggled(),
│                   #     _on_calibrate_clicked(), _on_calib_progress(),
│                   #     _on_calib_finished()
│                   #   _on_display_param_committed() — display-only handler
│                   #   symmetry logic, export, settings dialog opener
│                   #   on_import_clicked / _read_parameters_section /
│                   #     _parse_imported_params / _apply_imported_params —
│                   #     CSV import (V1.3.0)
│                   #   _update_schroeder_display() — live label (V1.3.0)
│                   #   Entry point: main()
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
| `on_import_clicked` | File dialog → parse → validate → apply or abort |
| `_read_parameters_section(path)` | `csv.reader` walk; collects `{name: value}` from `[Parameters]` only |
| `_parse_imported_params(raw)` | Type-converts and validates all values; raises `KeyError`/`ValueError` on bad input |
| `_phase_label_to_index(label)` | Case-insensitive substring match → combo index |
| `_import_set_slider(slider, value)` | Clamp to `[_vmin, _vmax]` + log warning on clamp |
| `_apply_imported_params(v)` | Block all signals → set room dims first → re-sync limits → set rest → unblock → single refresh |

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

## 14. Next Session Roadmap

No features are currently planned. Outstanding nice-to-haves from prior sessions:

---

**Both V1.3.0 features are implemented.** See section 13 above for full implementation detail.

---

## 15. Session Conclusion

**V1.3.0 is a stable, feature-complete milestone.** Room Data Import and Schroeder Frequency Display are both complete and tested.

**This session is officially closed.** The next session should:
1. Read this document and `CHANGELOG.md` first.
2. No features are currently queued — pick from the nice-to-haves below or a new brief.

**Outstanding nice-to-haves (no commitment):**
- `SMOOTHING_SAMPLES` re-exposed in Settings under a clearer name (`LISTENING_AREA_SAMPLES`).
- Windows `.exe` packaging: PyInstaller `.spec` file.
- Per-mode scalar bar, contour opacity slider, export of the 3D field to VTK/VTI format, mode labels on the guide lines.
- The `calib_db_range` asymmetry may need further tuning — the current implementation clips the ratio upper bound at `1.0`, making the upper dB window effectively 0 dB (values above the median all map to 0.5). A `10.0` clip would give a true +20 dB upper window if that proves preferable.
