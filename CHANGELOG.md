# Changelog

All notable changes to this project will be documented in this file.

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