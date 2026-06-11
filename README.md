![Standing Wave Viewer image](images/SWVtitle.jpg)

Standing Wave Viewer is a 3D acoustic simulation and visualization tool built with Python, **PySide6 (Qt)**, and **PyVista (VTK)**. It calculates and visualizes room modes (standing waves) and low-frequency interference patterns to help optimize subwoofer/speaker placement and listening positions. To learn technical details behind it, please refer to documents/Q_A_en.md.

Please note that this is an amateur project that began as a personal endeavor, and is not intended to serve as a fully rigorous verification tool for professional use.
I originally created it for myself, with the goal of making it as intuitive as possible to understand the acoustic characteristics of a room. However, now that it’s finished, I feel it has turned into something fairly unique, so I decided to make it available to the public.
If it proves useful to anyone out there, I couldn’t be happier.

## ✨ Key Features

- **Native Desktop UI**: Fully integrated single-window application built with PySide6. The 3D view, 3D top view, frequency response graph, controls and room modes are all visible at once without page reloads. You can adjust room dimensions, wall reflection coefficients, speaker coordinates, and microphone positions using slider controls intuitively. 
- **Accurate Frequency Response**: Simulates the frequency response (20Hz - 250Hz, adjustable) at the microphone position, accounting for room dimensions and wall reflection coefficients.
- **Volumetric 3D Visualization**: Powered by **PyVista and VTK**, it animates the sound pressure distribution (nodes and antinodes) across the entire 3D room space for any given frequency with high-performance volumetric rendering. The camera viewpoint is perfectly preserved during real-time updates. **NEW in V1.1** You can now toggle the rendering mode to Contour mode. This allows you to see through objects when necessary.
- **Advanced Stereo Interference Models**: 
  Supports both Mono and Stereo configurations with three calculation modes:
  - **Uncorrelated (Independent Power Sum)**: Adds acoustic power without wave interference. It's perfect for visualizing the room's default state.
  - **Global Cancel**: A fast approximation model for phase cancellation. This is particularly valuable when sound sources are arranged symmetrically.
  - **In-Phase (True Complex Field - Experimental)**: The ultimate physics engine. It synthesizes the exact complex field (real + imaginary parts) across the entire 3D space, perfectly reproducing the spatial warping of wave nodes when subwoofers are placed asymmetrically. However, in the real world, the perfect interference that is theoretically possible is not perceived. This is because various scattering factors are present. Furthermore, actual sound sources are not point sources, and the range of human perception is not limited to a single point.
- **Advanced Acoustics**
To bridge the gap between ideal theoretical physics and real-world perception, use the Advanced Acoustics sliders:
  - **Room Scatter (Order Damping)**: Real rooms have furniture that scatters high-frequency tangential and oblique modes. This slider applies an $n^2$ penalty to high-order modes, allowing you to dial in the "liveliness" of your specific space.
  - **Listening Area (Spatial Smoothing)**: We don't listen with a mathematically infinitely small point. This slider averages the pressure field over a localized 3D area around the mic, giving you a realistic frequency response that matches actual human perception.
- **Data Export**: Export your room configurations, frequency response data, and complete room modes directly to a CSV file.
- **Live Settings Tuning**: Dynamically adjust simulation resolutions, grid sizes, and the calculation range via the built-in Settings dialog without restarting the application.

## 🚀 3D View Controls
- When **Contour mode** is enabled, the sound pressure distribution display switches to contour mode, providing a clearer view (though the amount of information displayed decreases)
- When you turn on **Dynamic mode toggle**, the sound pressure distribution follows all parameter adjustments (requires power)
- **Reset View**: Returns the camera to its initial position.
- **Basic Mouse Operations**
  - Moving the mouse while holding down the left mouse button rotates the view.
  - Moving the mouse up or down while holding the right mouse button zooms in or out. Scrolling the mouse wheel also zooms in or out.
  - Moving the mouse while clicking the scroll wheel pans the view horizontally. Holding down the Shift key while moving the mouse has the same effect.
  - Holding down the Ctrl key while moving the mouse allows you to rotate the view horizontally around the center of the screen.

## Screenshot
![Standing Wave Viewer image](images/swvdesktopss.jpg)

## 🛠️ Installation & Usage

### Windows
Please download the Windows build from [Release](https://github.com/TatschanT/swv_desktop/releases/). Extract it to any folder and run SWV.exe.

### Running on a local environment on Mac and Linux 
### Prerequisites
- Python 3.10+ (Tested with Python 3.14/3.10)
- `PySide6`
- `pyvista`
- `pyvistaqt`
- `matplotlib` 
- `numpy`

### Running the App (Local)
1. Clone the repository.
2. It is recommended to use a virtual environment (`venv`).
3. Install dependencies:
   ```bash
   pip install PySide6 pyvista pyvistaqt matplotlib numpy
   ```
4. Run the application:
   ```bash
   python main.py
   ```

**Linux / Wayland Note:** 
If you are using a Linux distribution with Wayland (e.g., Fedora), VTK might have compatibility issues. The application handles this internally by forcing X11 mode (`QT_QPA_PLATFORM="xcb"`) on Linux, so no extra launch flags are needed.

---
Disclaimer

This software is provided "AS IS", without any warranty of any kind, express or implied, including but not limited to warranties of merchantability, fitness for a particular purpose, or non‑infringement.
In no event shall the author be liable for any claim, damages, or other liability arising from, out of, or in connection with the software or the use or other dealings in the software.
This software is provided as a reference and educational tool for personal use, and is not intended to serve as the sole rigorous basis for professional‑grade verification, design decisions, or commercial services.
This repository is also not intended as a venue for general discussions or assertions that are unrelated to the actual behavior, usability, or quality of this software.
Such topics are considered out of scope for this project, and issues or comments along those lines may not receive a response.