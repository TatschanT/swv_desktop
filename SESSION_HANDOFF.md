# Standing Wave Viewer — Session Handoff Document
**Date:** 2026-05-31  
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
│                   #   X-ray overlay, checkerboard floor, cube-axes
│
├── graphs.py       # View — 2D (Matplotlib)
│                   #   Plot2DWidget(FigureCanvasQTAgg)
│                   #   Top-down room layout + freq response + dB annotation
│
├── physics.py      # Model — physics engine
│                   #   RoomConfig, Position dataclasses
│                   #   calc_room_modes(), calc_tensor_space()
│                   #   compute_f_response_1d(), compute_tensor_3d()
│
├── config.py       # Model — constants
│                   #   AppDefaults, PhysicalConfig, SimResolution
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

## 4. Remaining Tasks (Next Session To-Do)

### TODO 1 — Spatial Smoothing Toggle
Implement the spatial smoothing feature from the original Streamlit version (`compute_f_response_1d(..., smoothing=True)`). Add a toggle switch (e.g., `QCheckBox`) to the top-right area of the Frequency Response subplot in `graphs.py`. When enabled, pass `smoothing=True` and recompute.

### TODO 2 — Replace "Camera Lock" with "Reset View" Button
The "Camera lock" `QCheckBox` in the center-bottom toolbar is currently non-functional. Remove it and replace it with a `QPushButton("Reset View")` that calls `render3d.plotter.reset_camera(bounds=render3d.grid.bounds)` to restore the camera to fit the current room.

### TODO 3 — Implement "Export Data" Button
The `export_btn` in the right panel (`QPushButton("Export data")`) is wired but has no handler. Implement `on_export_clicked()`:
- Gather current parameters (room dims, speaker/mic positions, reflection coefficients, frequency, source count)
- Gather the frequency response array (`plot2d._db`, `plot2d._freqs`)
- Gather the room modes table data
- Write to a timestamped CSV via `QFileDialog.getSaveFileName`

### TODO 4 — Settings Dialog
The `settings_btn` (`QPushButton("Settings")`) has no handler. Implement a `QDialog` subclass (e.g., `SettingsDialog`) that exposes editable fields for parameters currently hardcoded in `config.py` (e.g., `SPEED_OF_SOUND`, `MAX_CALC_FREQ`, `GRID_SIZE_NORMAL`). Apply changes back to the running app without restart.

### TODO 5 — SWV Logo Banner
The top-right panel contains a placeholder frame ("Title Banner", `bg="#b1b2b5"`, `BANNER_H=72px`). Replace it with a `QLabel` displaying the SWV logo image (asset path TBD). Use `QPixmap` scaled to fit (`Qt.KeepAspectRatio`).

---

## 5. How to Run

```bash
cd /home/ttatsuta/Projects/swv_desktop
.venv/bin/python main_ui.py
```

`QT_QPA_PLATFORM=xcb` is set inside `main_ui.py` (Wayland fix). No additional flags needed.
