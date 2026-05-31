import streamlit as st
import numpy as np
import pandas as pd
import config as app_config
import physics
from physics import Position, RoomConfig
import render

# ==========================================
# Application State & Configuration
# ==========================================

DEFAULT_STATE = {
    "Lx": app_config.AppDefaults.LX, "Ly": app_config.AppDefaults.LY, "Lz": app_config.AppDefaults.LZ,
    "spk_x": app_config.AppDefaults.SPK_X, "spk_y": app_config.AppDefaults.SPK_Y, "spk_z": app_config.AppDefaults.SPK_Z,
    "spk2_x": app_config.AppDefaults.SPK2_X, "spk2_y": app_config.AppDefaults.SPK2_Y, "spk2_z": app_config.AppDefaults.SPK2_Z,
    "mic_x": app_config.AppDefaults.MIC_X, "mic_y": app_config.AppDefaults.MIC_Y, "mic_z": app_config.AppDefaults.MIC_Z,
    "R": app_config.AppDefaults.R
}

st.set_page_config(page_title="Standing Wave Viewer V0.9.2", layout="wide")

# ==========================================
# UI Setup: Sidebar Controls
# ==========================================

st.sidebar.image("images/SWVlogo.jpg", width='stretch')
st.sidebar.markdown("### Control Panel")

source_mode = st.sidebar.radio("Sound Source Setup", [
    "🔊 1 Source (Mono)",
    "🔊🔊 2 Sources (Stereo)"
])
num_sources = 1 if "1 Source" in source_mode else 2

if num_sources == 2:
    corr_mode = st.sidebar.radio("L/R Bass Signal Correlation", [
        "🔀 Uncorrelated (Independent Power Sum)",
        "🔗 In-Phase (Global Cancel - Fast)",
        "🌊 In-Phase (True Complex Field - experimental)"
    ], help="Uncorrelated: adds power. Global Cancel: Fast approximation for cancel. True Complex: Real-world spatial interference.")
else:
    corr_mode = "Mono (Approx)"

mode = st.sidebar.radio("Operation Mode", [
    "🎛️ 1. Layout Placement (Ultra-fast)",
    "🌊 2. Standing Wave Viz (Current Setup)",
    "📐 3. Room Bare Specs (Rigid/Corner)"
])

# UI scaling and resolution toggles
st.sidebar.markdown("---")
high_res = st.sidebar.toggle("High Resolution Mode (Slower)", value=False, help="Enable 32x32x32 grid and 2Hz steps. Default is 24x24x24 grid and 5Hz steps.")
large_view = st.sidebar.toggle("Large 3D View", value=False, help="Increase the 3D graph height for high-resolution displays.")
chart_height = app_config.AppDefaults.CHART_HEIGHT_LARGE if large_view else app_config.AppDefaults.CHART_HEIGHT_NORMAL

st.sidebar.header("Room Dimensions (m)")
Lx = st.sidebar.slider("Width (Lx)", app_config.AppDefaults.ROOM_MIN_L, app_config.AppDefaults.ROOM_MAX_L_XY, DEFAULT_STATE["Lx"], 0.02)
Ly = st.sidebar.slider("Depth (Ly)", app_config.AppDefaults.ROOM_MIN_L, app_config.AppDefaults.ROOM_MAX_L_XY, DEFAULT_STATE["Ly"], 0.02)
Lz = st.sidebar.slider("Height (Lz)", app_config.AppDefaults.ROOM_MIN_L, app_config.AppDefaults.ROOM_MAX_L_Z, DEFAULT_STATE["Lz"], 0.02)

st.sidebar.header("Equipment Positions (m)")

# Init session states for mirrored speaker layout
if "spk2_x_state" not in st.session_state:
    st.session_state["spk2_x_state"] = DEFAULT_STATE["spk2_x"]
if "spk2_y_state" not in st.session_state:
    st.session_state["spk2_y_state"] = DEFAULT_STATE["spk2_y"]
if "spk2_z_state" not in st.session_state:
    st.session_state["spk2_z_state"] = DEFAULT_STATE["spk2_z"]
if "is_linked" not in st.session_state:
    st.session_state["is_linked"] = True

if num_sources == 2:
    link_lr = st.sidebar.checkbox("🔗 L/R Symmetry Link", value=st.session_state["is_linked"], help="Automatically mirror Spk 2 based on Spk 1's position")
    st.session_state["is_linked"] = link_lr
    
    st.sidebar.markdown("**Spk 1 (L)**")

    max_x_spk1 = Lx / 2.0 if link_lr else Lx
    current_spk_x = st.session_state.get("s1x", DEFAULT_STATE["spk_x"])
    if current_spk_x > max_x_spk1:
        current_spk_x = max_x_spk1

    spk_x = st.sidebar.slider("X", 0.0, float(max_x_spk1), float(current_spk_x), 0.01, key="s1x")
    spk_y = st.sidebar.slider("Y", 0.0, Ly, DEFAULT_STATE["spk_y"], 0.01, key="s1y")
    spk_z = st.sidebar.slider("Z", 0.0, Lz, DEFAULT_STATE["spk_z"], 0.01, key="s1z")

    if link_lr:
        st.sidebar.info(f"👉 **Spk 2 (R)** is locked symmetrically at:\nX: {Lx - spk_x:.2f}m, Y: {spk_y:.2f}m, Z: {spk_z:.2f}m")
        spk2_x = float(Lx - spk_x)
        spk2_y = float(spk_y)
        spk2_z = float(spk_z)
        st.session_state["spk2_x_state"] = spk2_x
        st.session_state["spk2_y_state"] = spk2_y
        st.session_state["spk2_z_state"] = spk2_z
    else:
        st.sidebar.markdown("**Spk 2 (R)**")
        safe_spk2_x = min(st.session_state["spk2_x_state"], Lx)
        spk2_x = st.sidebar.slider("X", 0.0, Lx, float(safe_spk2_x), 0.01, key="s2x")
        spk2_y = st.sidebar.slider("Y", 0.0, Ly, st.session_state["spk2_y_state"], 0.01, key="s2y")
        spk2_z = st.sidebar.slider("Z", 0.0, Lz, st.session_state["spk2_z_state"], 0.01, key="s2z")

        st.session_state["spk2_x_state"] = spk2_x
        st.session_state["spk2_y_state"] = spk2_y
        st.session_state["spk2_z_state"] = spk2_z
else:
    spk_x = st.sidebar.slider("Speaker X", 0.0, Lx, DEFAULT_STATE["spk_x"], 0.01)
    spk_y = st.sidebar.slider("Speaker Y", 0.0, Ly, DEFAULT_STATE["spk_y"], 0.01)
    spk_z = st.sidebar.slider("Speaker Z", 0.0, Lz, DEFAULT_STATE["spk_z"], 0.01)
    spk2_x, spk2_y, spk2_z = spk_x, spk_y, spk_z

st.sidebar.markdown("---")
st.sidebar.markdown("**Microphone Position**")
mic_x = st.sidebar.slider("Mic X", 0.0, Lx, DEFAULT_STATE["mic_x"], 0.01)
mic_y = st.sidebar.slider("Mic Y", 0.0, Ly, DEFAULT_STATE["mic_y"], 0.01)
mic_z = st.sidebar.slider("Mic Z", 0.0, Lz, DEFAULT_STATE["mic_z"], 0.01)

with st.sidebar.expander("🧱 Wall Reflection Coefficients"):
    Rx1 = st.slider("Left Wall (X=0)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)
    Rx2 = st.slider("Right Wall (X=Lx)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)
    Ry1 = st.slider("Front Wall (Y=0)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)
    Ry2 = st.slider("Back Wall (Y=Ly)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)
    Rz1 = st.slider("Floor (Z=0)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)
    Rz2 = st.slider("Ceiling (Z=Lz)", 0.0, 1.0, DEFAULT_STATE["R"], 0.05)

Rx = (Rx1 + Rx2) / 2.0
Ry = (Ry1 + Ry2) / 2.0
Rz = (Rz1 + Rz2) / 2.0

# ==========================================
# Application Settings Initialization
# ==========================================

FREQS_1D = np.arange(app_config.SimResolution.FREQ_1D_START, app_config.SimResolution.FREQ_1D_END, app_config.SimResolution.FREQ_1D_STEP)

if high_res:
    FREQS_3D = np.arange(app_config.SimResolution.FREQ_3D_START_HIGH, app_config.SimResolution.FREQ_3D_END_HIGH, app_config.SimResolution.FREQ_3D_STEP_HIGH)
    grid_size = app_config.SimResolution.GRID_SIZE_HIGH
else:
    FREQS_3D = np.arange(app_config.SimResolution.FREQ_3D_START_NORMAL, app_config.SimResolution.FREQ_3D_END_NORMAL, app_config.SimResolution.FREQ_3D_STEP_NORMAL)
    grid_size = app_config.SimResolution.GRID_SIZE_NORMAL

room = RoomConfig(Lx=Lx, Ly=Ly, Lz=Lz, Rx=Rx, Ry=Ry, Rz=Rz)
spk1_pos = Position(x=spk_x, y=spk_y, z=spk_z)
spk2_pos = Position(x=spk2_x, y=spk2_y, z=spk2_z)
mic_pos = Position(x=mic_x, y=mic_y, z=mic_z)

# ==========================================
# Main Rendering Block
# ==========================================

if num_sources == 2:
    spk_xs, spk_ys, spk_zs = [spk_x, spk2_x], [spk_y, spk2_y], [spk_z, spk2_z]
else:
    spk_xs, spk_ys, spk_zs = [spk_x], [spk_y], [spk_z]

if mode == "🎛️ 1. Layout Placement (Ultra-fast)":
    col_header1, col_header2 = st.columns([6, 4])
    with col_header1:
        st.info("Layout Placement Mode: Adjust coordinates with top-down 2D view.")
    with col_header2:
        smoothing_on = st.toggle("Spatial Smoothing (3x3x3, 10cm)", value=False, help="Averages 27 points around mic to smooth out local dips.")

    col1, col2 = st.columns([5, 5])
    
    with col1:
        fig_layout = render.create_layout_plot(room, spk_xs, spk_ys, spk_zs, mic_x, mic_y, mic_z, num_sources, chart_height)
        st.plotly_chart(fig_layout, width='stretch', config={'responsive': True})

    with col2:
        f_response_db = physics.compute_f_response_1d(room, spk1_pos, spk2_pos, mic_pos, num_sources, corr_mode, FREQS_1D, smoothing=smoothing_on)
        fig_f = render.create_freq_response_plot(FREQS_1D, f_response_db, chart_height)
        st.plotly_chart(fig_f, width='stretch', config={'responsive': True})

else:
    if mode == "📐 3. Room Bare Specs (Rigid/Corner)":
        eff_num_sources = 1
        eff_corr = "Mono"
        eff_spk1 = Position(0.0, 0.0, 0.0)
        eff_spk2 = Position(0.0, 0.0, 0.0)
        eff_room = RoomConfig(Lx, Ly, Lz, 1.0, 1.0, 1.0)
        render_spk_xs, render_spk_ys, render_spk_zs = [0.0], [0.0], [0.0]
        is_corner_mode = True
    else:
        eff_num_sources = num_sources
        eff_corr = corr_mode
        eff_spk1 = spk1_pos
        eff_spk2 = spk2_pos
        eff_room = room
        render_spk_xs, render_spk_ys, render_spk_zs = spk_xs, spk_ys, spk_zs
        is_corner_mode = False

    X_flat, Y_flat, Z_flat, tensor_abs = physics.compute_tensor_3d(eff_room, eff_spk1, eff_spk2, eff_num_sources, eff_corr, FREQS_3D, grid_size)

    fig_vol = render.create_volume_plot(
        room=eff_room,
        spk_xs=render_spk_xs,
        spk_ys=render_spk_ys,
        spk_zs=render_spk_zs,
        mic_x=mic_x,
        mic_y=mic_y,
        mic_z=mic_z,
        X_flat=X_flat,
        Y_flat=Y_flat,
        Z_flat=Z_flat,
        tensor_abs=tensor_abs,
        freqs_3d=FREQS_3D,
        chart_height=chart_height,
        is_corner_mode=is_corner_mode
    )

    st.plotly_chart(fig_vol, width='stretch')

    if "3." in mode:
        st.markdown("### Fundamental Room Modes (1st to 3rd Order)")
        
        base_modes = [
            ("Axial X (1,0,0)", 1, 0, 0),
            ("Axial Y (0,1,0)", 0, 1, 0),
            ("Axial Z (0,0,1)", 0, 0, 1),
            ("Tangential XY (1,1,0)", 1, 1, 0),
            ("Tangential XZ (1,0,1)", 1, 0, 1),
            ("Tangential YZ (0,1,1)", 0, 1, 1),
            ("Oblique (1,1,1)", 1, 1, 1)
        ]

        table_data = []
        c = app_config.PhysicalConfig.SPEED_OF_SOUND

        for name, nx, ny, nz in base_modes:
            f1 = (c / 2.0) * np.sqrt((nx/room.Lx)**2 + (ny/room.Ly)**2 + (nz/room.Lz)**2)
            length = c / (2.0 * f1)
            
            table_data.append({
                "Mode": name,
                "Length (m)": round(length, 2),
                "1st (Hz)": round(f1, 1),
                "2nd (Hz)": round(f1 * 2, 1),
                "3rd (Hz)": round(f1 * 3, 1)
            })

        df_modes = pd.DataFrame(table_data)

        # UI components remain in main.py
        st.dataframe(df_modes, width='stretch', hide_index=True)

        csv_data = df_modes.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 Download Table as CSV",
            data=csv_data,
            file_name="room_modes_specs.csv",
            mime="text/csv"
        )