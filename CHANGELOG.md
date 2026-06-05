# Changelog

All notable changes to this project will be documented in this file.

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