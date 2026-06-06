"""View layer for the 3D sound-pressure field.

``Render3D`` wraps a ``pyvistaqt.QtInteractor`` and renders the standing-wave
pressure magnitude as a volume inside the room box. The key design rule is that
updates happen strictly IN PLACE: every actor (volume, contour, floor, outline,
markers, cube-axes) is created exactly once, and ``update_mesh`` only mutates
their data before calling ``plotter.render()``. Nothing is ever cleared or
re-added, so the user's camera (zoom / rotation / pan) is fully preserved.

Render modes (Volume vs. Contour):
  * Volume  - dense, full-information volumetric map (default).
  * Contour - "Clear Visibility" iso-surfaces drawn only in the statistical
              valley/peak bands (see config.AppDefaults.CONTOUR_*), so the
              field reads as a transparent set of shells you can see through.
Switching modes only toggles ``actor.SetVisibility(...)`` -- it never
clears/re-adds actors, so the camera is preserved. The speaker/mic markers stay
visible in both modes.

Supporting actors:
  * X-ray markers  - speaker/mic spheres live in a top-layer overlay renderer so
                     they always draw *over* the volume, even when buried inside
                     a dense pressure field.
  * Floor grid     - a checkerboard plane at Z=0 (resizes with the room).
  * Cube axes      - show_bounds() frames the space; bounds update with the room.
"""

import numpy as np
import pyvista as pv
import vtk
from pyvistaqt import QtInteractor

import config as app_config
import physics

# Colors
SPK_COLOR = "#38bdf8"      # bright cyan-blue
MIC_COLOR = "#f43f5e"      # bright red
OUTLINE_COLOR = "#dddddd"
FLOOR_DARK = "#16233f"     # checkerboard: dark blue
FLOOR_LIGHT = "#b8c4d0"    # checkerboard: light gray
AXES_COLOR = "#cccccc"
BG_COLOR = "#101418"

# Resolution (cells per side) of the checkerboard floor.
FLOOR_RES = 8

# Opacity transfer function across the (normalized) [0, 1] range.
# IMPORTANT: the lowest value keeps a fairly HIGH base opacity so the blue
# (low-pressure) regions render as a real blue mist with saturated color,
# instead of a near-transparent "black mist" that just shows the dark
# background through jet's dark-navy low end. Without this floor the volume
# reads as "black -> green -> red" rather than the full "blue -> green ->
# yellow -> red" spectrum. High pressure (anti-nodes) stays fully opaque (1.0)
# so reds saturate at the high end.
OPACITY_TF = [0.3, 0.4, 0.55, 0.75, 1.0]

# Per-surface opacity for the contour ("Clear Visibility") render mode. Kept low
# so the nested valley/peak shells stay translucent and you can see through to
# the markers / room interior, matching the original Streamlit look.
CONTOUR_OPACITY = 0.45


class Render3D:
    """Owns the QtInteractor and the in-place-updatable pressure volume."""

    SCALARS = "Pressure"

    def __init__(self, parent=None, grid_size=None):
        self.grid_size = int(grid_size or app_config.SimResolution.GRID_SIZE_NORMAL)

        # QtInteractor is *both* the embeddable QWidget and the PyVista plotter.
        # `.interactor` is the widget the controller drops into its layout.
        self.interactor = QtInteractor(parent)
        self.plotter = self.interactor
        self.plotter.set_background(BG_COLOR)

        # Build the initial field from the default room so the view is populated
        # before any user interaction.
        D = app_config.AppDefaults
        room = physics.RoomConfig(D.LX, D.LY, D.LZ, 0.0, 0.0, 0.0)

        # Uniform grid: because the room is sampled on a regular lattice we can
        # use ImageData, which the volume mapper renders directly (no resample),
        # guaranteeing that later in-place edits to `self.grid` show up on render.
        self.grid = self._make_grid(room)
        self._last_spacing = self._spacing(room)   # for detecting room resizes
        seed = np.linspace(0.0, 1.0, self.grid.n_points, dtype=np.float32)
        self.grid.point_data[self.SCALARS] = seed
        self.grid.point_data.active_scalars_name = self.SCALARS

        # ---- Volume (no scalar bar) -------------------------------------
        # cmap="jet" + clim=[0,1]; shade=False keeps colors at their true (unlit)
        # value and linear interpolation (set below) avoids blocky washed cells.
        # The scalar bar is intentionally omitted -- opacity blending made it
        # read as a mismatch against the volume, so it was removed.
        self.vol_actor = self.plotter.add_volume(
            self.grid,
            scalars=self.SCALARS,
            cmap="jet",
            opacity=OPACITY_TF,
            clim=[0.0, 1.0],            # data normalized to exactly [0, 1]
            shade=False,                # no lighting darkening -> colors stay true
            opacity_unit_distance=min(self._spacing(room)),
            show_scalar_bar=False,
        )
        # Smooth (linear) sampling so colors blend cleanly instead of rendering
        # as washed-out nearest-neighbour blocks.
        self.vol_actor.prop.SetInterpolationTypeToLinear()
        self._tune_opacity_distance(room)

        # CRITICAL (geometry-update fix): add_volume() binds the mapper to a
        # *shallow copy* of the ImageData. That copy shares the scalar arrays by
        # reference (so color updates work) but copies spacing/origin/extent by
        # VALUE -- so changing self.grid.spacing later never reaches the mapper
        # and the volume stays clipped to the original room bounds. Rebinding the
        # mapper's input to self.grid itself makes geometry edits propagate too.
        self._vol_mapper = self.vol_actor.GetMapper()
        self._vol_mapper.SetInputData(self.grid)

        # ---- Contour ("Clear Visibility") representation ----------------
        # Created EXACTLY ONCE alongside the volume. Mode switching only flips
        # actor visibility (never add/remove), so the camera is preserved. The
        # iso-surface geometry is regenerated in place via copy_from() whenever
        # contour mode is active (see _update_contour). Mapped with the SAME
        # jet/clim=[0,1] as the volume so the two modes are visually consistent.
        self.contour_mode = False
        self.contour_mesh = self.grid.contour(
            isosurfaces=self._contour_levels(self.grid.point_data[self.SCALARS]) or [0.5],
            scalars=self.SCALARS,
        )
        self.contour_actor = self.plotter.add_mesh(
            self.contour_mesh, scalars=self.SCALARS, cmap="jet",
            clim=[0.0, 1.0], opacity=CONTOUR_OPACITY, show_scalar_bar=False,
            smooth_shading=True,
        )
        self.contour_actor.SetVisibility(False)   # volume is the default mode

        # ---- Checkerboard floor at Z=0 (resizes with the room) ----------
        # Solid (opacity 1.0), high-contrast light-gray / dark-blue tiles so the
        # floor instantly reads as a real ground plane and "down" is obvious.
        self.floor = self._make_floor(room)
        self.floor_actor = self.plotter.add_mesh(
            self.floor, scalars="checker", cmap=[FLOOR_DARK, FLOOR_LIGHT],
            show_scalar_bar=False, opacity=1.0, lighting=False,
            show_edges=True, edge_color="#33405a", line_width=1, name="floor",
        )

        # ---- Room outline ----------------------------------------------
        self.outline = self.grid.outline()
        self.plotter.add_mesh(self.outline, color=OUTLINE_COLOR, line_width=2)

        # ---- Equipment markers (created in main renderer, then moved to an
        #      overlay so they render on top of the volume) ---------------
        self._marker_r = 0.15
        self.spk1_marker = self._sphere(D.SPK_X, D.SPK_Y, D.SPK_Z)
        self.spk2_marker = self._sphere(D.SPK2_X, D.SPK2_Y, D.SPK2_Z)
        self.mic_marker = self._sphere(D.MIC_X, D.MIC_Y, D.MIC_Z)
        self.spk1_actor = self._add_marker(self.spk1_marker, SPK_COLOR)
        self.spk2_actor = self._add_marker(self.spk2_marker, SPK_COLOR)
        self.mic_actor = self._add_marker(self.mic_marker, MIC_COLOR)

        # ---- Cube-axes framing (bounds updated in place) ---------------
        # all_edges=False: with it True, show_bounds() adds a SEPARATE static
        # bounding-box actor fixed at the initial bounds that SetBounds() never
        # updates -- so it ghosts when the room shrinks. The box edges arep
        # already drawn (and updated in place) by self.outline above, so the
        # all_edges box is redundant anyway.
        self.cube_axes = self.plotter.show_bounds(
            grid="front", location="outer", all_edges=False,
            color=AXES_COLOR,
            xtitle="X (m)", ytitle="Y (m)", ztitle="Z (m)",
            axes_ranges=[0, D.LX, 0, D.LY, 0, D.LZ],
            use_3d_text=False,
        )

        self.plotter.add_axes()

        # X-ray overlay must be set up after the marker actors exist.
        self._setup_overlay()
        self.cube_axes.update_bounds(self.grid.bounds)
        try:
            self.cube_axes.SetXAxisRange(0, D.LX)
            self.cube_axes.SetYAxisRange(0, D.LY)
            self.cube_axes.SetZAxisRange(0, D.LZ)
        except AttributeError:
            pass
        self.plotter.reset_camera()

    # -- construction helpers -------------------------------------------
    def _make_grid(self, room) -> pv.ImageData:
        n = self.grid_size
        return pv.ImageData(
            dimensions=(n, n, n),
            spacing=self._spacing(room),
            origin=(0.0, 0.0, 0.0),
        )

    def _spacing(self, room):
        n = self.grid_size
        return (room.Lx / (n - 1), room.Ly / (n - 1), room.Lz / (n - 1))

    def _make_floor(self, room) -> pv.PolyData:
        # Fixed resolution so it can be updated later with copy_from(). A small
        # negative Z offset keeps the solid floor from z-fighting the volume's
        # bottom face and the room outline at Z=0.
        plane = pv.Plane(
            center=(room.Lx / 2.0, room.Ly / 2.0, -0.01),
            direction=(0.0, 0.0, 1.0),
            i_size=room.Lx, j_size=room.Ly,
            i_resolution=FLOOR_RES, j_resolution=FLOOR_RES,
        )
        # Per-cell 0/1 checkerboard pattern (tile color alternates with parity).
        idx = np.arange(plane.n_cells)
        checker = (((idx // FLOOR_RES) + (idx % FLOOR_RES)) % 2).astype(np.float32)
        plane.cell_data["checker"] = checker
        plane.set_active_scalars("checker")
        return plane

    def _sphere(self, x, y, z) -> pv.PolyData:
        return pv.Sphere(radius=self._marker_r, center=(x, y, z))

    def _add_marker(self, mesh, color):
        actor = self.plotter.add_mesh(
            mesh, color=color, smooth_shading=True,
            specular=0.3, ambient=0.45, diffuse=0.7,
        )
        return actor

    def _setup_overlay(self):
        """Move the equipment markers into a layer-1 renderer that shares the
        main camera. A higher layer composites on top of the volume, so the
        markers stay visible even when fully inside a dense field (X-ray)."""
        render_window = getattr(self.plotter, "render_window", None) or self.plotter.ren_win
        main = self.plotter.renderer

        # Pick a layer strictly above every existing renderer. PyVista's
        # orientation-axes widget (add_axes) already sits on layer 1, so reusing
        # that layer lets it overdraw our markers; a dedicated top layer doesn't.
        existing = render_window.GetRenderers()
        existing.InitTraversal()
        max_layer = 0
        for _ in range(existing.GetNumberOfItems()):
            max_layer = max(max_layer, existing.GetNextItem().GetLayer())
        top_layer = max_layer + 1

        self._overlay = vtk.vtkRenderer()
        self._overlay.SetLayer(top_layer)
        self._overlay.InteractiveOff()
        self._overlay.SetActiveCamera(main.GetActiveCamera())   # share camera
        render_window.SetNumberOfLayers(top_layer + 1)
        render_window.AddRenderer(self._overlay)

        for actor in (self.spk1_actor, self.spk2_actor, self.mic_actor):
            main.RemoveActor(actor)
            self._overlay.AddActor(actor)

    def _tune_opacity_distance(self, room):
        """Set the scalar-opacity unit distance to roughly one cell so opacity
        accumulates visibly across the volume (VTK default can be too sparse)."""
        unit = max(min(self._spacing(room)), 1e-3)
        try:
            self.vol_actor.prop.SetScalarOpacityUnitDistance(unit)
        except AttributeError:
            self.vol_actor.GetProperty().SetScalarOpacityUnitDistance(unit)

    @staticmethod
    def _normalize(values: np.ndarray) -> np.ndarray:
        """Force the field to span exactly [0.0, 1.0] via min-max scaling so the
        fixed color/opacity transfer functions always cover the data."""
        values = np.asarray(values, dtype=np.float32)
        lo = float(values.min())
        hi = float(values.max())
        if hi - lo < 1e-12:
            return np.zeros_like(values, dtype=np.float32)
        return ((values - lo) / (hi - lo)).astype(np.float32)

    # -- contour ("Clear Visibility") helpers ---------------------------
    @staticmethod
    def _contour_levels(scalars) -> list:
        """Compute iso-surface levels via the statistical-scaling rule.

        Ported from old_src/render.py: build a robust value band
        ``mean +/- LIMIT*std`` (clamped at 0), then return iso-values spread
        across only the bottom ``VALLEY_FRAC`` of that band (valleys) and the
        top ``(1 - PEAK_FRAC)`` of it (peaks). The middle band is skipped, which
        is what makes the field "see-through". Returns ``[]`` for a degenerate
        (flat) field so the caller can render nothing.
        """
        D = app_config.AppDefaults
        s = np.asarray(scalars, dtype=np.float64)
        smin, smax = float(s.min()), float(s.max())
        if smax - smin < 1e-9:
            return []

        mean, std = float(s.mean()), float(s.std())
        robust_min = max(0.0, mean - D.CONTOUR_STD_DEV_LIMIT * std)
        robust_max = mean + D.CONTOUR_STD_DEV_LIMIT * std
        span = robust_max - robust_min
        if span <= 1e-9:
            return []

        n = D.CONTOUR_LEVELS_PER_BAND
        valley_hi = robust_min + span * D.CONTOUR_VALLEY_FRAC
        peak_lo = robust_min + span * D.CONTOUR_PEAK_FRAC
        valleys = np.linspace(smin, valley_hi, n)
        peaks = np.linspace(peak_lo, smax, n)

        # Dedupe + sort, and drop anything outside the data range (out-of-range
        # iso-values would just yield empty surfaces).
        levels = np.unique(np.concatenate([valleys, peaks]))
        levels = levels[(levels >= smin) & (levels <= smax)]
        return levels.tolist()

    def _update_contour(self):
        """Regenerate the iso-surface geometry from the CURRENT grid scalars and
        push it into the persistent ``contour_mesh`` IN PLACE via copy_from().

        Like the floor/outline/marker pattern, the actor's mapper keeps pointing
        at ``self.contour_mesh``, so mutating it in place reaches the screen
        without any add/remove -- preserving the camera.
        """
        levels = self._contour_levels(self.grid.point_data[self.SCALARS])
        if not levels:
            # Flat field -> no surfaces; empty the mesh so nothing draws.
            self.contour_mesh.copy_from(pv.PolyData())
            return
        contoured = self.grid.contour(isosurfaces=levels, scalars=self.SCALARS)
        self.contour_mesh.copy_from(contoured)
        if self.contour_mesh.n_points and self.SCALARS in self.contour_mesh.point_data:
            self.contour_mesh.set_active_scalars(self.SCALARS)

    def _apply_visibility(self, num_src):
        """Set actor visibility for the current render mode.

        Only the field representation swaps: volume in volume mode, contour
        shells in contour mode. The equipment markers stay visible in BOTH modes
        (contour mode is transparent enough that the markers read cleanly), with
        Speaker 2 shown only when there are two sources.
        """
        contour = self.contour_mode
        self.vol_actor.SetVisibility(not contour)
        self.contour_actor.SetVisibility(contour)
        self.spk1_actor.SetVisibility(True)
        self.mic_actor.SetVisibility(True)
        self.spk2_actor.SetVisibility(num_src == 2)

    def set_render_mode(self, contour_mode, num_src):
        """Switch between volume and contour rendering WITHOUT a physics
        recompute. The pressure field already lives in ``self.grid``; we only
        (re)generate the iso-surfaces when contour mode is active and flip
        visibility. No clear()/add/remove -> the camera is preserved.
        """
        self.contour_mode = bool(contour_mode)
        if self.contour_mode:
            self._update_contour()
        self._apply_visibility(num_src)
        self.plotter.render()

    # -- the in-place update --------------------------------------------
    def update_mesh(self, room, spk1, spk2, mic, num_src, corr_mode, freq):
        """Recompute the pressure field for ``freq`` and update everything in
        place. Never clears the plotter, so the camera is preserved."""
        # 1. New pressure field. physics returns an [ix, iy, iz] array; ImageData
        #    expects x-fastest ordering -> ravel order='F' matches exactly.
        pressure = physics.calc_tensor_space(
            room, spk1, spk2, num_src, corr_mode, freq, grid_size=self.grid_size
        )
        scalars = self._normalize(pressure.ravel(order="F"))

        # 2. Geometry follows the room. The point count (extent) is fixed, only
        #    the spacing changes -> the box grows/shrinks. Because the mapper
        #    input IS self.grid (rebound in __init__), this reaches the volume;
        #    we still flag both the data and the mapper modified so VTK drops any
        #    cached bounding box and re-evaluates the new extent.
        new_spacing = self._spacing(room)
        room_resized = new_spacing != self._last_spacing
        self._last_spacing = new_spacing

        self.grid.spacing = new_spacing
        self.grid.Modified()
        self._vol_mapper.Modified()
        self._tune_opacity_distance(room)
        self.outline.copy_from(self.grid.outline())
        self.floor.copy_from(self._make_floor(room))
        self.floor.set_active_scalars("checker")   # keep checkerboard mapping
        # CubeAxesActor must frame the NEW bounds. update_bounds() (PyVista wrapper)
        # sets the bounds AND the per-axis display ranges to match, then regenerates
        # the explicit tick labels from those ranges (np.linspace(min, max, n)). This
        # is what fixes stale labels; a bare native SetBounds() leaves old labels.
        # NOTE: this PyVista build (0.48) writes explicit string labels rather than
        # relying on VTK's native auto-tick generator, so the axes never "round up"
        # past the room's true extent -- no extra range clamping is needed.
        self.cube_axes.update_bounds(self.grid.bounds)
        self.cube_axes.Modified()

        # 3. Write the new values *into the existing* VTK scalar array (not a
        #    fresh array) and flag it modified, so the volume mapper re-reads it.
        arr = self.grid.point_data[self.SCALARS]
        arr[:] = scalars
        self.grid.point_data.active_scalars_name = self.SCALARS
        self.grid.GetPointData().GetScalars().Modified()
        self.grid.Modified()

        # 3b. Contour shells follow the field, but ONLY when contour mode is
        #     active -- skip the iso-surface generation entirely in volume mode.
        if self.contour_mode:
            self._update_contour()

        # 4. Move the equipment markers in place. Visibility (volume vs. contour,
        #    Speaker-2-in-mono, and hiding the markers in contour mode) is applied
        #    centrally by _apply_visibility below.
        self.spk1_marker.copy_from(self._sphere(spk1.x, spk1.y, spk1.z))
        self.mic_marker.copy_from(self._sphere(mic.x, mic.y, mic.z))
        if num_src == 2:
            self.spk2_marker.copy_from(self._sphere(spk2.x, spk2.y, spk2.z))
        self._apply_visibility(num_src)

        # 5. Camera. Normally we DON'T touch it (so zoom/rotation/pan are
        #    preserved across frequency / speaker changes). But when the room
        #    size changes, refit so the (now larger/smaller) box stays in view.
        #    reset_camera(bounds=...) recenters + steps back while preserving the
        #    current view direction, so the user's rotation is kept.
        if room_resized:
            self.plotter.reset_camera(bounds=self.grid.bounds)

        # 6. Re-render. No clear() / no re-add -> zoom, rotation, pan preserved.
        self.plotter.render()

    def set_grid_size(self, new_size, room):
        """Rebuild the volume grid at a new per-axis resolution, IN PLACE.

        Changing the sample count changes the point count, so a fresh ImageData
        is unavoidable. We rebuild it, re-seed its scalar buffer and re-point the
        EXISTING volume mapper at it (``SetInputData``). The volume actor itself
        is reused -- no ``clear()`` / ``add_volume()`` / ``remove_actor()`` -- so
        the camera (zoom / rotation / pan) is preserved per the in-place rule.

        Does nothing if the size is unchanged. The grid is seeded with zeros;
        the caller is expected to follow up with ``update_mesh`` to fill in the
        real field at the current parameters.
        """
        new_size = int(new_size)
        if new_size == self.grid_size:
            return
        self.grid_size = new_size

        # Fresh grid at the new resolution; spacing follows the current room.
        self.grid = self._make_grid(room)
        self._last_spacing = self._spacing(room)
        seed = np.zeros(self.grid.n_points, dtype=np.float32)
        self.grid.point_data[self.SCALARS] = seed
        self.grid.point_data.active_scalars_name = self.SCALARS

        # Re-point the existing mapper at the new grid (keeps the volume actor).
        self._vol_mapper.SetInputData(self.grid)
        self._vol_mapper.Modified()

        # Outline frames the same bounds; refresh it from the new grid.
        self.outline.copy_from(self.grid.outline())
        self._tune_opacity_distance(room)

    def close(self):
        """Release the VTK render window (call on app shutdown)."""
        self.plotter.close()
