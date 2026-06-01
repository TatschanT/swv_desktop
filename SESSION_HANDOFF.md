# Standing Wave Viewer — Session Handoff Document
**Date:** 2026-06-01  
**Status:** **V1.0 COMPLETE** ✅ — full Streamlit→desktop migration plus all 5 polish TODOs shipped and verified.  
**Project:** `swv_desktop` (`/home/ttatsuta/Projects/swv_desktop`)  
**Venv:** `.venv/` (Python 3.14, PySide6 6.11, PyVista 0.48, pyvistaqt 0.11, Matplotlib 3.10, NumPy 2.4)

---

## 1. Session Summary

We migrated "Standing Wave Viewer" in full from a Streamlit web app (`old_src/`) to a native **PySide6 + PyVista** desktop application. Every phase was implemented and verified with offscreen render tests:

| Phase | Deliverable |
|-------|-------------|
| 1 | UI skeleton — fixed 1600×1000 window with left/center/right panels, `LabeledSlider` + `XYZSliders` widgets, room-modes `QTableWidget`, wall-reflection sliders, placeholder frames |
| 2 | Controller — room-modes physics wired to sliders; room dimension→position slider clamping (`setMaxValue`); default values from `config.AppDefaults` |
| 3 | PyVista 3D view — `pyvistaqt.QtInteractor` volume rendering; in-place scalar + geometry updates; X-ray overlay markers; checkerboard floor; cube-axes framing |
| 3.5 | Visual polish — X-ray overlay on correct layer; floor z=-0.01 z-fight fix; scalar bar (later removed); `reset_camera(bounds=...)` on room resize only |
| 3.9 | L/R symmetry link — verified against `old_src`: X mirrored (`spk2.x = Lx - spk1.x`), Y/Z match; Speaker 2 locked while linked |
| 4 | Matplotlib 2D graphs — `Plot2DWidget` with top-down room layout (left) + frequency response (right); smart recompute gating |
| 4.1 | `committed` signal + release-gating; camera refit on room resize only; fixed freq-graph Y-axis `[-25, 5]`; live dB annotation |

---

## 2. Architectural Decisions & Critical Gotchas

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

**Rule:** All actors (volume, floor, outline, markers, cube-axes) are created **exactly once** in `Render3D.__init__`. `update_mesh` only mutates existing actor/mesh data, then calls `plotter.render()`. No `clear()`, no `remove_actor()`, no `add_*` calls during updates.

**Why:** `plotter.clear()` destroys and recreates the render window state, resetting the camera position, zoom, and rotation — breaking the "camera preserved" feature.

**Geometry-change helpers used instead of rebuilding:**
- `mesh.copy_from(new_mesh)` — updates an existing PolyData in place (floor, outline, markers)
- `actor.SetVisibility(bool)` — hides/shows without removing (spk2 in mono mode)
- `actor.SetBounds(...)` — repositions the CubeAxesActor

**Camera refit exception:** On **room resize only**, call `self.plotter.reset_camera(bounds=self.grid.bounds)`. This recenters and steps back while preserving view direction (the user's rotation is kept). Detected via `room_resized = new_spacing != self._last_spacing`.

### 2.3 X-Ray Marker Overlay — Layer Collision

**Problem:** `pyvistaqt.QtInteractor` adds its orientation-axes widget on **layer 1**. Placing the marker overlay on layer 1 (as a bare `Plotter` test suggested) causes the axes widget to overdraw the markers.

**Fix:** In `_setup_overlay`, scan all existing renderers and pick `top_layer = max_existing_layer + 1` (lands on layer 2 in practice). Markers are moved from the main renderer into this overlay renderer; the overlay shares the main camera so everything stays synchronized.

### 2.4 Signal Gating — `valueChanged` vs `committed`

`LabeledSlider` emits two signals:

| Signal | When | Use for |
|--------|------|---------|
| `valueChanged(float)` | Every tick while dragging | Lightweight live UI (QLineEdit text, moving the 2D graph marker line) |
| `committed(float)` | `sliderReleased` + `editingFinished` | Heavy physics recompute (3D field, 1D freq response) |

**Wiring matrix:**

```
Frequency slider:
  valueChanged → _on_freq_changed:
      plot2d.update_freq_marker(freq)          # always: just moves the red line
      if Dynamic ON: _refresh(recompute=False) # optional live 3D
  committed    → _on_freq_committed:
      _refresh(recompute_response=False)       # 3D update; freq-response curve is freq-independent

Room / Speaker / Mic / Wall sliders:
  valueChanged → _on_param_changed:
      if Dynamic ON: _refresh(recompute=True)  # live preview
  committed    → _on_param_committed:
      _refresh(recompute_response=True)        # always recompute once on release

Source / Phase combos:
  currentIndexChanged → _on_param_committed    # discrete commits, always recompute
```

**Result:** With Dynamic **OFF**, dragging does no heavy work but releases always trigger exactly one recompute. With Dynamic **ON**, you get live preview during drag AND a final recompute on release (idempotent).

### 2.5 Frequency Response — Recompute Trigger Logic

The 1D frequency response curve is **independent of the current frequency** (it shows dB at *all* frequencies). Therefore:
- Moving the frequency **slider** must NOT recompute the curve — only the vertical marker line moves.
- Room / speaker / mic / wall / source / phase changes DO require a recompute.

The `_db` array is cached on `Plot2DWidget` and `update_freq_marker` uses `np.interp` on it to display the dB value at the current freq, with no physics call.

### 2.6 Reflection Coefficients

`RoomConfig.Rx/Ry/Rz` must not be zero — when `R=0`, `calc_shape(n, pos, L, 0)` collapses to a spatial constant, rendering the volume pressure field flat (invisible). Correct derivation (from `old_src/main.py`):

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

---

## 3. Codebase Structure (MVC)

```
swv_desktop/
├── main_ui.py      # Controller + View skeleton
│                   #   MainWindow, LabeledSlider, XYZSliders
│                   #   Signal wiring, _refresh(), symmetry logic
│                   #   Entry point: main()
│
├── render.py       # View — 3D (PyVista)
│                   #   Render3D class: QtInteractor wrapper
│                   #   In-place volume + geometry updates
│                   #   set_grid_size() — camera-preserving grid rebuild
│                   #   X-ray overlay, checkerboard floor, cube-axes
│
├── graphs.py       # View — 2D (Matplotlib)
│                   #   Plot2DWidget(FigureCanvasQTAgg)
│                   #   Top-down room layout + freq response + dB annotation
│                   #   rebuild_freqs() — config-driven frequency axis
│
├── settings_ui.py  # View + state — runtime settings dialog (V1.0 TODO 4)
│                   #   SettingsDialog(QDialog); exposes a curated subset
│                   #   of config.py via QSpinBox/QDoubleSpinBox
│                   #   load_settings()/save_settings() — JSON persistence
│                   #   Mutates config in place, emits settings_applied
│
├── physics.py      # Model — physics engine
│                   #   RoomConfig, Position dataclasses
│                   #   calc_room_modes(), calc_tensor_space()
│                   #   compute_f_response_1d(), compute_tensor_3d()
│
├── config.py       # Model — constants
│                   #   AppDefaults, PhysicalConfig, SimResolution
│
├── settings.json   # Persisted runtime settings (auto-created on first Apply)
├── images/         # Assets — SWVlogo_s.jpg (banner)
│
├── old_src/        # Original Streamlit app (reference only, do not import)
│   ├── main.py
│   ├── physics.py  # Has @st.cache_data decorators — not usable directly
│   ├── render.py   # Plotly-based, reference only
│   └── config.py
│
└── SESSION_HANDOFF.md   # This file
```

---

## 4. Completed Tasks (V1.0)

All five polish TODOs from the previous handoff are **done, wired, and verified**.

### TODO 1 — Spatial Smoothing Toggle ✅
`QCheckBox("Spatial Smoothing")` lives in the **bottom-right of the top-center 2D-graph panel** (`main_ui.py`, in `_build_center`) — NOT overlaid on the Matplotlib canvas (an early overlay attempt was rejected as cluttered). State is owned by the controller and threaded into `Plot2DWidget.update_all(..., smoothing=)` → `update_freq_response(..., smoothing=)`. Toggling fires `_on_param_committed` (a discrete commit → one full response recompute).
- **Strength tuning:** the original ±0.1 m / 27-sample cube was too weak. Smoothing now samples a configurable cube via `SimResolution.SMOOTHING_RADIUS` (default 0.3 m) × `SMOOTHING_SAMPLES` (default 5 → 5³ = 125 points), `np.linspace(-r, r, n)` so the center point is included. Measured effect: peak-to-trough range ~18 dB → ~11 dB.

### TODO 2 — "Reset View" Button ✅
"Camera lock" checkbox removed; replaced with `QPushButton("Reset View")` in the center-bottom toolbar. Handler `_on_reset_view` forcefully restores the canonical isometric view (a bare `reset_camera()` *preserves* the manual view direction, so it appeared to do nothing). Final, robust sequence:
```python
plotter.camera_position = "iso"                       # break out of manual focal point / view-up
plotter.renderer.ResetCamera(*self.render3d.grid.bounds)  # refit to current room (vtkRenderer level)
plotter.update()                                      # QtInteractor: flush Qt repaint (NOT just render())
```
**Gotcha learned:** `plotter.render()` is only a VTK draw; a standalone button click needs `plotter.update()` (which runs `processEvents()`) to actually repaint the embedded widget.

### TODO 3 — "Export Data" Button ✅
`on_export_clicked()` in `main_ui.py`: `QFileDialog.getSaveFileName` (timestamped default `swv_export_YYYYMMDD_HHMMSS.csv`, cancel-safe, auto-appends `.csv`). Writes three labelled CSV sections — **[Parameters]** (room, positions, per-axis + per-wall reflection, freq, sources, phase, smoothing), **[Frequency Response]** (`plot2d._freqs`/`_db`), **[Room Modes]** (recomputed via `calc_room_modes` for the *full* list, not the truncated table). I/O wrapped in `try/except OSError` with `QMessageBox` success/failure feedback.

### TODO 4 — Settings Dialog ✅ (new file `settings_ui.py`)
`SettingsDialog(QDialog)` extracted to its own module to keep `main_ui.py` lean. Exposes `SPEED_OF_SOUND`, `MAX_CALC_FREQ`, `FREQ_1D_START/END/STEP`, `GRID_SIZE_NORMAL`, `SMOOTHING_RADIUS`, `SMOOTHING_SAMPLES` via spin boxes grouped by section. **State model:** the dialog mutates the live `config` class attributes in place (physics/views read them at call time, so changes propagate on next recompute) AND persists to `settings.json`; `load_settings()` runs at the top of `MainWindow.__init__` before panels are built. The dialog is recompute-agnostic — it emits `settings_applied`, and the controller's `_on_settings_applied` performs the rebuilds + one refresh.

### TODO 5 — SWV Logo Banner ✅
Placeholder replaced with a `QLabel` showing `images/SWVlogo_s.jpg` via `QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`, with an `isNull()` guard (keeps the grey `#b1b2b5` background as fallback if the asset is missing).

### Post-TODO V1.0 polish ✅
- **Reflection defaults:** wall sliders now initialize from `AppDefaults.R` (0.8), not a hardcoded 1.0.
- **Group-box title corruption:** root cause was an **unscoped panel stylesheet** (`border-left: ...`) cascading into every child widget. Fixed by scoping to the panel via object-name selectors (`#leftPanel`/`#rightPanel { ... }`). **Reuse this pattern for any future panel borders.**
- **Room modes table:** font 9→10, `QTableWidget::item { padding: 1px; }`, and `QHeaderView.Stretch` so columns fill the panel width evenly.
- **3D frame ghosting on room shrink:** root cause was `show_bounds(all_edges=True)` adding a **separate static bounding-box actor** that `SetBounds()` never updates. Fixed with `all_edges=False` (the box edges already come from the in-place-updated `self.outline`) plus `cube_axes.Modified()` after `SetBounds()`.

### Key architectural wins (read before extending the 3D view)

1. **PyVista in-place update discipline (§2.1/§2.2) held up across every feature.** Scalars are written into the existing buffer (`arr[:] = ...` + `GetScalars().Modified()`); geometry reaches the mapper only because it was rebound to `self.grid` once in `__init__`. No `clear()`/`remove_actor()`/`add_*` ever runs during updates → camera is always preserved.
2. **Grid resize WITHOUT losing the camera (`Render3D.set_grid_size`).** Changing `GRID_SIZE_NORMAL` changes the point count, so a fresh `ImageData` is unavoidable — but instead of re-adding the volume actor, we build the new grid, re-seed its scalar buffer, and **re-point the existing mapper** (`self._vol_mapper.SetInputData(new_grid)`). The volume actor is reused, so zoom/rotation/pan survive a resolution change. The invariant that makes the follow-up `update_mesh` safe: `calc_tensor_space(grid_size=n)` always yields exactly `n³` points = the new grid's `n_points`.
3. **`settings_ui.py` refactor — clean separation.** All config-mutation + persistence knowledge lives in `settings_ui`; all recompute knowledge lives in the controller. They communicate through a single `settings_applied` signal. This is the template for future dialogs.
4. **Signal gating (§2.4) is the law.** `valueChanged` = lightweight live UI only; `committed` / discrete combo & checkbox toggles = heavy recompute. New controls must pick the correct lane.

---

## 5. Future Roadmap / Next Steps (V1.1)

Two new user-requested features. **UI placement for BOTH:** add the toggle switches in the currently-empty space **between the center panels** (i.e. the center column's vertical gap between the top 2D-graph section and the bottom 3D section in `main_ui.py._build_center`). Group them in a small horizontal toolbar there. Reuse the existing signal-gating discipline: a toggle is a discrete commit → route to `_on_param_committed` (or a dedicated handler that ends in a single refresh).

### Feature 1 — Room Mode Frequency Lines on the 2D Frequency Response
A toggle (`QCheckBox`, e.g. "Show room modes") that overlays thin gray **vertical lines** on the frequency-response subplot at each calculated room-mode frequency, so the user can correlate peaks/dips with specific modes.

**Suggested architecture:**
- Mode frequencies already come from `physics.calc_room_modes(room)` (returns `(freq, (nx,ny,nz), length)`); the controller already calls this for the table — reuse it (consider passing the freqs into `plot2d` or recomputing in `update_freq_response`).
- In `graphs.py`, draw the lines inside `update_freq_response` with `ax.axvline(f, color="#666", lw=0.6, alpha=0.5, zorder=1)` for each mode freq within the current x-range. Keep them BELOW the response curve and the red marker (`zorder`).
- Respect the existing fixed axes (`DB_MIN/DB_MAX`, x from `self._freqs`). Only draw modes that fall within `[self._freqs[0], self._freqs[-1]]`.
- Gate visibility on the toggle. Cheapest: store the state on the controller and pass it through `update_all`/`update_freq_response` (mirror exactly how `smoothing` is threaded). A full recompute on toggle is fine (cheap), or redraw-only if you want to optimize later.
- **Caution:** these are *static* artists redrawn on each `update_freq_response` (which does `ax.clear()`), so no in-place-handle juggling is needed — unlike the 3D view, the 2D canvas is rebuilt per recompute.

### Feature 2 — 3D Rendering Mode Toggle: Volume vs. Iso-surface/Contour
A toggle to switch the 3D view between the current **volumetric** density map and a **contour / iso-surface** rendering (~20 nested iso-surface layers, à la the original Streamlit `old_src/render.py`). **This is the larger task and touches `render.py` heavily.**

**Critical architectural constraints (do NOT regress the V1.0 wins):**
- The **camera-preservation rule (§2.2) still applies.** Switching modes will require showing/hiding actors, but prefer `actor.SetVisibility(bool)` over `remove_actor()`/`add_*`. Ideal design: create BOTH the volume actor and a contour actor **once in `__init__`**, then toggle visibility — never clear the plotter.
- **Contour generation is geometry-dependent and per-frame.** `pv.ImageData.contour(isosurfaces=N, scalars="Pressure")` returns a NEW PolyData each call. To stay in-place, generate it into a persistent mesh with `contour_mesh.copy_from(self.grid.contour(...))` inside `update_mesh` (only when contour mode is active, to save cost), exactly like the floor/outline/marker pattern. Map it with a fixed `clim=[0,1]` + the same "jet" cmap for visual continuity.
- **In contour mode, the X-ray speaker/mic marker overlay (§2.3) can be skipped/hidden** — the user explicitly noted the complex surface mapping/X-ray is unnecessary there. Toggle the overlay markers' visibility alongside the mode switch.
- Skip the expensive branch you're not showing: when in volume mode don't recompute contours, and vice-versa, to keep `update_mesh` fast.
- The toggle is a discrete commit → it should trigger one `_refresh(recompute_response=...)` (or a lighter render-only path) and set the appropriate actor visibilities.

**Reference:** `old_src/render.py` (Plotly-based) shows the intended ~20-layer contour look — reference only, do not import.

---

## 6. How to Run

```bash
cd /home/ttatsuta/Projects/swv_desktop
.venv/bin/python main_ui.py
```

`QT_QPA_PLATFORM=xcb` is set inside `main_ui.py` (Wayland fix). No additional flags needed.

**Note on headless verification:** `pyvistaqt.QtInteractor` needs a real display (it X-errors under `QT_QPA_PLATFORM=offscreen`, and no `xvfb` is installed in this env). Physics/config/logic can be unit-tested headlessly, but **3D visual behavior (camera, ghosting, render modes) must be eyeballed interactively.**
