# Standing Wave Viewer — Session Handoff Document
**Date:** 2026-06-10  
**Status:** **V1.2.0 STABLE** ✅ — Advanced acoustics sliders, unified frequency config, and tech-debt cleanup complete. Session closed.  
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

---

## 2. Architectural Decisions & Critical Gotchas

**These rules held across every V1.0 and V1.1 feature without exception. Future agents MUST follow them strictly — any deviation risks invisible renders, camera resets, or signal storms.**

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

**This rule was extended to the V1.1 contour actor:** the contour `PolyData` mesh is created once in `__init__`, regenerated in place with `contour_mesh.copy_from(self.grid.contour(...))` on each update, and the actor is shown/hidden with `SetVisibility`. No `add_mesh`/`remove_actor` ever runs on mode switch.

**Camera refit exception:** On **room resize only**, call `self.plotter.reset_camera(bounds=self.grid.bounds)`. This recenters and steps back while preserving view direction (the user's rotation is kept). Detected via `room_resized = new_spacing != self._last_spacing`.

### 2.3 X-Ray Marker Overlay — Layer Collision

**Problem:** `pyvistaqt.QtInteractor` adds its orientation-axes widget on **layer 1**. Placing the marker overlay on layer 1 (as a bare `Plotter` test suggested) causes the axes widget to overdraw the markers.

**Fix:** In `_setup_overlay`, scan all existing renderers and pick `top_layer = max_existing_layer + 1` (lands on layer 2 in practice). Markers are moved from the main renderer into this overlay renderer; the overlay shares the main camera so everything stays synchronized.

**V1.1 note:** The markers (spk1, spk2, mic) remain **visible in both Volume and Contour modes**. In Contour mode the field is transparent enough that they read cleanly. `_apply_visibility` in `render.py` now only gates spk2 on `num_src == 2` — it no longer touches spk1 or mic visibility.

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

Show room modes / Spatial Smoothing checkboxes:
  toggled → _on_param_committed                # discrete commit → full 2D recompute

Contour Mode checkbox:
  toggled → _on_render_mode_changed            # lightweight 3D-only, NO physics/2D
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

### 2.8 PyInstaller Path Resolution (V1.1)

Two helpers live at the top of `config.py` (imported by `main.py` and `settings_ui.py`):

| Helper | When to use | How it works |
|--------|------------|--------------|
| `get_resource_path(relative)` | Read-only bundled assets (logo image, etc.) | `sys._MEIPASS` in frozen build, `os.path.abspath(".")` in script mode |
| `get_user_data_path(filename)` | Read/write user data (`settings.json`) | `os.path.dirname(sys.executable)` in frozen build, `os.path.abspath(".")` in script mode |

**Why the split matters:** `sys._MEIPASS` is a temporary extraction directory deleted when the `.exe` exits — any file written there is lost. Writable files MUST go to the directory containing the executable.

### 2.9 HiDPI Scaling Lock (V1.1.1)

`os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"` is set at the very top of `main.py`, before any Qt imports. This hard-locks the window to its intended 1600×1000 physical pixels regardless of Windows Display Scaling. Without it, a 150% OS scaling setting would render the window at 2400×1500 — too large for a 1080p screen.

**Rule:** This env-var must remain at the module top-level so it takes effect before `QApplication` initialises.

### 2.10 Mode Energy Weighting — `mode_norm` (V1.1.2)

In `physics.py`, mode amplitude is now weighted by mode type (Axial / Tangential / Oblique) to reflect real-world energy decay from wall reflections. The weighting factor is called `mode_norm`.

- **Axial** (one non-zero index): full amplitude — reflects off only 2 walls.
- **Tangential** (two non-zero indices): reduced amplitude — reflects off 4 walls, more loss.
- **Oblique** (all three indices non-zero): lowest amplitude — reflects off all 6 walls.

**Rationale:** without weighting, all modes contribute equally regardless of how many wall interactions they undergo, producing physically incorrect pressure distributions (exaggerated peaks in corners at low freq; excessive cancellation at high freq in Complex Field mode). `mode_norm` corrects the relative contributions before summation. The old name `mode_weight` was replaced by `mode_norm` as of commit `bdec28a`.

---

## 3. Codebase Structure (MVC)

```
swv_desktop/
├── main.py      # Controller + View skeleton
│                   #   MainWindow, LabeledSlider, XYZSliders
│                   #   Signal wiring, _refresh(), _on_render_mode_changed()
│                   #   symmetry logic, export, settings dialog opener
│                   #   Entry point: main()
│
├── render.py       # View — 3D (PyVista)
│                   #   Render3D class: QtInteractor wrapper
│                   #   In-place volume + contour + geometry updates
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
│   ├── main.py
│   ├── physics.py  # Has @st.cache_data decorators — not usable directly
│   ├── render.py   # Plotly-based; source of the statistical-scaling contour logic
│   └── config.py
│
└── SESSION_HANDOFF.md   # This file
```

---

## 4. Completed Tasks (V1.0)

All five polish TODOs from the V1.0 session are **done, wired, and verified**.

### TODO 1 — Spatial Smoothing Toggle ✅
`QCheckBox("Spatial Smoothing")` lives in the **bottom-right toggle row of the top-center 2D-graph panel** (`main.py`, in `_build_center`). State is owned by the controller and threaded into `Plot2DWidget.update_all(..., smoothing=)` → `update_freq_response(..., smoothing=)`. Toggling fires `_on_param_committed` (a discrete commit → one full response recompute).
- **Strength tuning:** the original ±0.1 m / 27-sample cube was too weak. Smoothing now samples a configurable cube via `SimResolution.SMOOTHING_RADIUS` (default 0.3 m) × `SMOOTHING_SAMPLES` (default 5 → 5³ = 125 points), `np.linspace(-r, r, n)` so the center point is included. Measured effect: peak-to-trough range ~18 dB → ~11 dB.

### TODO 2 — "Reset View" Button ✅
"Camera lock" checkbox removed; replaced with `QPushButton("Reset View")` in the center-bottom toolbar. Handler `_on_reset_view` forcefully restores the canonical isometric view. Final, robust sequence:
```python
plotter.camera_position = "iso"                       # break out of manual focal point / view-up
plotter.renderer.ResetCamera(*self.render3d.grid.bounds)  # refit to current room (vtkRenderer level)
plotter.update()                                      # QtInteractor: flush Qt repaint (NOT just render())
```
**Gotcha learned:** `plotter.render()` is only a VTK draw; a standalone button click needs `plotter.update()` (which runs `processEvents()`) to actually repaint the embedded widget.

### TODO 3 — "Export Data" Button ✅
`on_export_clicked()` in `main.py`: `QFileDialog.getSaveFileName` (timestamped default `swv_export_YYYYMMDD_HHMMSS.csv`, cancel-safe, auto-appends `.csv`). Writes three labelled CSV sections — **[Parameters]**, **[Frequency Response]**, **[Room Modes]**. I/O wrapped in `try/except OSError` with `QMessageBox` success/failure feedback.

### TODO 4 — Settings Dialog ✅ (file `settings_ui.py`)
`SettingsDialog(QDialog)` extracted to its own module. Exposes `SPEED_OF_SOUND`, `MAX_CALC_FREQ`, `FREQ_1D_START/END/STEP`, `GRID_SIZE_NORMAL`, `SMOOTHING_RADIUS`, `SMOOTHING_SAMPLES` via spin boxes. **State model:** mutates live `config` attributes in place AND persists to `settings.json` via `get_user_data_path`. `load_settings()` runs at the top of `MainWindow.__init__`. The dialog emits `settings_applied`; the controller's `_on_settings_applied` performs rebuilds + one refresh.

### TODO 5 — SWV Logo Banner ✅
Placeholder replaced with a `QLabel` showing `images/SWVlogo_s.jpg` via `QPixmap.scaled(..., Qt.KeepAspectRatio, Qt.SmoothTransformation)`, loaded via `get_resource_path`. An `isNull()` guard keeps the grey `#b1b2b5` background as fallback if the asset is missing.

### Post-TODO V1.0 polish ✅
- **Reflection defaults:** wall sliders initialize from `AppDefaults.R` (0.8).
- **Group-box title corruption:** fixed by scoping panel stylesheets to object-name selectors (`#leftPanel`/`#rightPanel { ... }`). Reuse this pattern for any future panel borders.
- **Room modes table:** font 9→10, `QTableWidget::item { padding: 1px; }`, `QHeaderView.Stretch`.
- **3D frame ghosting on room shrink:** fixed with `all_edges=False` on `show_bounds` + `cube_axes.Modified()` after `SetBounds()`.

---

## 5. Completed Tasks (V1.1)

### Feature 1 — Room Mode Frequency Lines on the 2D Frequency Response ✅

**What was added:**
- `QCheckBox("Show room modes")` placed to the left of the existing `QCheckBox("Spatial Smoothing")` in the shared toggle row at the bottom-right of the 2D-graph panel (`main.py`, `_build_center`).
- Toggling fires `_on_param_committed` — same discrete-commit lane as `smoothing_chk`.

**Signal flow:**
`show_modes_chk.toggled` → `_on_param_committed` → `_refresh(recompute_response=True)` → controller computes `mode_freqs = [f for f, _, _ in physics.calc_room_modes(room)]` (only when checked, else `None`) → `plot2d.update_all(..., mode_freqs=mode_freqs)` → `update_freq_response(..., mode_freqs=mode_freqs)` → `ax.axvline(...)` per mode.

**Rendering:** drawn in `graphs.py:update_freq_response` immediately after `ax.clear()`, before the response curve and red marker:
```python
if mode_freqs:
    fmin, fmax = self._freqs[0], self._freqs[-1]
    for mf in mode_freqs:
        if fmin <= mf <= fmax:
            ax.axvline(mf, color="#777", lw=0.6, alpha=0.4, zorder=1)
```
- `color="#777"`, `lw=0.6`, `alpha=0.4`, `zorder=1` — visually secondary to the response curve (lw=1.5, zorder=2) and the red marker. The `ax.clear()` in each recompute means no persistent artist handles are needed.

**Data source:** reuses `physics.calc_room_modes(room)` — no second room-mode algorithm. The controller owns the call; `graphs.py` only receives the frequency list.

### Feature 2 — 3D Rendering Mode Toggle: Volume vs. Contour ✅

**What was added:**
- `QCheckBox("Contour Mode")` in the bottom 3D toggle row (left of "Dynamic update").
- Toggling fires a **dedicated lightweight handler** `_on_render_mode_changed` — it calls `render3d.set_render_mode(checked, num_src)` only; it does NOT trigger `_refresh`, so the physics and 2D plots are untouched.

**Camera preservation:** Strictly maintained per §2.2:
- The `contour_mesh` (`pv.PolyData`) and `contour_actor` are created **exactly once** in `Render3D.__init__`, hidden initially (`SetVisibility(False)`).
- On each `update_mesh` call when contour mode is active, `_update_contour()` regenerates the iso-surfaces and pushes them **in place** via `self.contour_mesh.copy_from(self.grid.contour(...))`.
- Mode switching only calls `actor.SetVisibility(bool)` via `_apply_visibility` — **never** `add_mesh`/`remove_actor`/`clear`.
- Marker visibility: spk1 and mic are always visible in both modes. spk2 follows `num_src == 2` only. Markers are NOT hidden in Contour mode (the field is transparent enough, and hiding them degrades usability).

**Statistical threshold math** (ported from `old_src/render.py`), implemented in `Render3D._contour_levels(scalars)`:
1. `mean`, `std` of the (normalized [0,1]) scalar field.
2. `robust_min = max(0, mean − 2·std)`, `robust_max = mean + 2·std`, `span = robust_max − robust_min`.
3. **Valleys:** `np.linspace(smin, robust_min + span·0.3, 7)` — bottom 30% of the robust band.
4. **Peaks:** `np.linspace(robust_min + span·0.7, smax, 7)` — top 30% of the robust band.
5. Combined, de-duped, out-of-data-range values clipped. The **middle 40% is deliberately skipped**, making the field transparent and easy to see through.
6. Returns `[]` for a flat field (handled gracefully — empties the mesh).

**Config constants** added to `AppDefaults` in `config.py`:
```python
CONTOUR_STD_DEV_LIMIT = 2.0
CONTOUR_VALLEY_FRAC = 0.3
CONTOUR_PEAK_FRAC = 0.7
CONTOUR_LEVELS_PER_BAND = 7
```

**Rendering:** `cmap="jet"`, `clim=[0,1]`, `opacity=0.45` (module constant `CONTOUR_OPACITY` in `render.py`) — matches the volume color scale for visual continuity.

**Performance:** `update_mesh` only calls `_update_contour()` when `self.contour_mode` is `True` — volume mode pays zero contour cost.

### Feature 3 — PyInstaller Path Resolution ✅

**What was added** (two helper functions at the top of `config.py`):

```python
def get_resource_path(relative_path: str) -> str:
    """Absolute path to a bundled read-only asset (image, etc.)."""
    base = sys._MEIPASS if hasattr(sys, "_MEIPASS") else os.path.abspath(".")
    return os.path.join(base, relative_path)

def get_user_data_path(filename: str) -> str:
    """Absolute path for a read/write user file (e.g., settings.json)."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.abspath(".")
    return os.path.join(base, filename)
```

**Applied in:**
- `main.py` — logo: `app_config.get_resource_path(os.path.join("images", "SWVlogo_s.jpg"))`.
- `settings_ui.py` — `SETTINGS_PATH = app_config.get_user_data_path("settings.json")`.

**Why the split:** `sys._MEIPASS` is a temporary extraction directory deleted on `.exe` exit — files written there are lost. `settings.json` must live next to the executable; logo is read-only so `_MEIPASS` is correct for it.

---

## 6. Completed Tasks (V1.1.1)

### Hotfix — PySide6 HiDPI Scaling ✅

`os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"` added at the top of `main.py` (before Qt imports). Prevents the 1600×1000 window from exceeding screen bounds on Windows with Display Scaling >100%. See §2.9.

### Startup Splash Screen ✅

`pyi_splash` integration added for the frozen (PyInstaller) build. Provides visual feedback while PyVista and PySide6 load. No impact on script-mode execution.

---

## 6a. Completed Tasks (V1.1.2)

### Fix — VTK CubeAxesActor Grid Rendering ✅

Fixed upstream VTK bug affecting rooms with any dimension <2.5 m: the CubeAxesActor would stretch or omit grid lines. Solution: replaced axis tick-number rendering with clean, evenly spaced 4-division grid lines that scale correctly with any room dimension. Dramatically improves 3D visual clarity at small room sizes.

### Change — Mode Energy Weighting (`mode_norm`) ✅

Overhauled `physics.py` to weight each room mode's amplitude by its type (Axial > Tangential > Oblique), reflecting the progressive energy loss from multiple wall reflections. See §2.10 for the full rationale. The variable was renamed from `mode_weight` → `mode_norm` (commit `bdec28a`).

### Fix — Complex Field Accuracy ✅

The "True Complex Field" simulation mode (`compute_tensor_3d` with phase-aware summation) was producing:
- Excessive blue cancellation zones at high frequencies
- Unnatural extreme red peaks in room corners at low frequencies

Both artefacts were caused by equal-amplitude mode summation (pre-`mode_norm`). With the energy weighting applied, the simulated pressure field is substantially more physically accurate.

---

## 7. How to Run

```bash
cd /home/ttatsuta/Projects/swv_desktop
.venv/bin/python main.py
```

`QT_QPA_PLATFORM=xcb` is set inside `main.py` (Wayland fix). No additional flags needed.

**Note on headless verification:** `pyvistaqt.QtInteractor` needs a real display (it X-errors under `QT_QPA_PLATFORM=offscreen`, and no `xvfb` is installed in this env). Physics/config/logic can be unit-tested headlessly, but **3D visual behavior (camera, ghosting, render modes, contour shells) must be eyeballed interactively.**

---

## 8. V1.2.0 Development Roadmap — COMPLETED ✅

All four steps of the V1.2.0 development phase were completed during this session:

| Step | Type | Task | Status |
|------|------|------|--------|
| 1 | Bugfix | **2-Sigma Statistical Clipping** — 2σ clipping on the volume rendering scalar range to prevent extreme hotspots from washing out the colour scale | ✅ **Completed** |
| 2 | Refactor | **Energy Weighting naming** — fix "Energy Weighting" naming conventions and comments throughout codebase | ✅ **Completed** |
| 3 | Feature | **Room Scatter slider** — "Room Scatter" (Order Damping) slider in the "Advanced Acoustics" group box | ✅ **Completed** |
| 4 | Feature | **Listening Area slider** — "Listening Area (m)" (Spatial Smoothing) slider in the "Advanced Acoustics" group box | ✅ **Completed** |

---

## 9. Completed Tasks (V1.2.0)

### Bugfix — 2-Sigma Statistical Clipping (`render.py`) ✅

`Render3D._normalize` switched from strict min/max scaling to a 2σ robust clipping approach. The scalar field is clipped to `[max(0, mean − 2σ), mean + 2σ]` before normalising to `[0, 1]`, discarding the extreme ~5% of outlier voxels. This prevents corner pressure hotspots from compressing the rest of the room into a uniform blue band. The floor `max(0, …)` ensures pressure magnitudes never produce a negative lower bound.

### Feature — Advanced Acoustics Sliders (`main.py`, `physics.py`, `graphs.py`, `render.py`) ✅

A new **"Advanced Acoustics"** `QGroupBox` was added to the right panel (between Wall Reflection Coefficients and Room Modes), containing two `LabeledSlider` widgets side-by-side:

**Room Scatter** (0.0 – 0.5, step 0.01, default 0.0):
- Adds an order-dependent damping penalty to `calc_gamma`: `room_scatter × (nx² + ny² + nz²)`. Using the square of the mode order (not the square root) provides more physically realistic high-order mode decay.
- Threaded through the full call chain: `_refresh` → `render3d.update_mesh` → `calc_tensor_space` → `compute_tensor_3d` → `calc_gamma`; and `_refresh` → `plot2d.update_all` → `update_freq_response` → `compute_f_response_1d` → `calc_gamma`.

**Listening Area (m)** (0.0 – 0.3, step 0.01, default 0.0):
- Replaces the old boolean "Spatial Smoothing" checkbox. When `> 0`, `compute_f_response_1d` samples a mic cube of half-width = slider value (metres) with `SMOOTHING_SAMPLES` points per axis (5³ = 125 points) and RMS-averages the response.
- Old `smoothing_chk` checkbox removed from the 2D-graph toggle row.

Both sliders follow the existing `valueChanged` / `committed` signal gating (live with Dynamic ON, one recompute on release). CSV export updated to log both parameters.

### Refactor — Unified Frequency Bounds (`config.py`, `physics.py`, `main.py`, `graphs.py`, `settings_ui.py`) ✅

`PhysicalConfig.MAX_CALC_FREQ` replaced by `MIN_FREQ = 20.0` and `MAX_FREQ = 250.0` — the single source of truth for both the physics engine and the display layer. `SimResolution.FREQ_1D_START` / `FREQ_1D_END` removed; only `FREQ_1D_STEP` remains.

Propagation chain:
- **physics.py**: all 6 `MAX_CALC_FREQ` references → `MAX_FREQ`.
- **graphs.py**: `rebuild_freqs` and `set_xlim` both read `MIN_FREQ`/`MAX_FREQ` directly.
- **main.py**: `freq_slider` constructed from `MIN_FREQ`/`MAX_FREQ`; `_on_settings_applied` calls `setMaxValue`/`setMinValue` to retune the slider live (ceiling first to avoid a collapsed intermediate range). New `LabeledSlider.setMinValue` method added (mirror of `setMaxValue`, re-bases tick mapping).
- **settings_ui.py**: exposes `MIN_FREQ` + `MAX_FREQ` under the "Physical" group; `FREQ_1D_START`/`END` entries removed.

Result: changing Min/Max Frequency in the Settings dialog instantly redraws the 2D plot X-axis, resets the frequency slider bounds, and re-limits mode generation — with no restart.

### Cleanup — Removed Obsolete `SMOOTHING_RADIUS` (`config.py`, `settings_ui.py`) ✅

`SimResolution.SMOOTHING_RADIUS` removed entirely (the Listening Area slider now owns the radius dynamically). `SMOOTHING_SAMPLES` kept as a fixed resolution constant (still read by `compute_f_response_1d`), but no longer exposed in the Settings dialog. The entire "Spatial smoothing" group removed from the Settings UI.

---

## 10. Session Conclusion

**V1.2.0 is a stable, feature-complete milestone for this development phase.** All four roadmap items shipped and verified. The codebase is clean: no known technical debt introduced in this session, all obsolete constants removed, and the physics → UI propagation paths are fully consistent.

**This session is officially closed.** The next session should start by reading this document and `CHANGELOG.md`, then deciding on the V1.3 roadmap.

**Outstanding nice-to-haves (no commitment):**
- `SMOOTHING_SAMPLES` could be re-exposed in Settings under a clearer name (`LISTENING_AREA_SAMPLES`) if users need to trade quality vs. speed on the listening-area averaging.
- Windows `.exe` packaging: PyInstaller `.spec` file (the path helpers are already in place from V1.1).
- V1.3 feature ideas: per-mode scalar bar, contour opacity slider, export of the 3D field to VTK/VTI format, mode labels on the guide lines.
