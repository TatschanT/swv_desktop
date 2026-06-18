# Changelog

All notable changes to this project will be documented in this file.

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