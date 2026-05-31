import plotly.graph_objects as go
import numpy as np
from physics import RoomConfig

def draw_room_wireframe(Lx: float, Ly: float, Lz: float) -> list[go.Scatter3d]:
    # 1. Room Boundaries
    x_lines = [0, Lx, Lx, 0, 0, 0, Lx, Lx, 0, 0, None, Lx, Lx, None, Lx, Lx, None, 0, 0]
    y_lines = [0, 0, Ly, Ly, 0, 0, 0, Ly, Ly, 0, None, 0, 0, None, Ly, Ly, None, Ly, Ly]
    z_lines = [0, 0, 0, 0, 0, Lz, Lz, Lz, Lz, Lz, None, 0, Lz, None, 0, Lz, None, 0, Lz]

    bounds_trace = go.Scatter3d(
        x=x_lines, y=y_lines, z=z_lines,
        mode='lines', line=dict(color='gray', width=3),
        name='Room Bounds', hoverinfo='skip'
    )

    # 2. 1/4 Subdivision Grid
    gx, gy, gz = [], [], []

    for i in [1, 2, 3]:
        x = Lx * i / 4.0
        gx.extend([x, x, None, x, x, None, x, x, None, x, x, None])
        gy.extend([0, Ly, None, 0, Ly, None, 0, 0, None, Ly, Ly, None])
        gz.extend([0, 0, None, Lz, Lz, None, 0, Lz, None, 0, Lz, None])

    for i in [1, 2, 3]:
        y = Ly * i / 4.0
        gx.extend([0, Lx, None, 0, Lx, None, 0, 0, None, Lx, Lx, None])
        gy.extend([y, y, None, y, y, None, y, y, None, y, y, None])
        gz.extend([0, 0, None, Lz, Lz, None, 0, Lz, None, 0, Lz, None])

    for i in [1, 2, 3]:
        z = Lz * i / 4.0
        gx.extend([0, Lx, None, 0, Lx, None, 0, 0, None, Lx, Lx, None])
        gy.extend([0, 0, None, Ly, Ly, None, 0, Ly, None, 0, Ly, None])
        gz.extend([z, z, None, z, z, None, z, z, None, z, z, None])

    grid_trace = go.Scatter3d(
        x=gx, y=gy, z=gz,
        mode='lines', line=dict(color='lightgray', width=1),
        name='1/4 Grid', hoverinfo='skip'
    )

    return [bounds_trace, grid_trace]

def create_layout_plot(room: RoomConfig, spk_xs: list, spk_ys: list, spk_zs: list, mic_x: float, mic_y: float, mic_z: float, num_sources: int, chart_height: int) -> go.Figure:
    fig_layout = go.Figure()

    # Room boundaries
    fig_layout.add_trace(go.Scatter(
        x=[0, room.Lx, room.Lx, 0, 0],
        y=[0, 0, room.Ly, room.Ly, 0],
        mode='lines', line=dict(color='gray', width=3),
        name='Room Bounds', hoverinfo='skip'
    ))

    # 4x4 internal grid lines
    for i in [1, 2, 3]:
        x_val = room.Lx * i / 4.0
        fig_layout.add_trace(go.Scatter(
            x=[x_val, x_val], y=[0, room.Ly],
            mode='lines', line=dict(color='lightgray', width=1, dash='dash'),
            showlegend=False, hoverinfo='skip'
        ))
        y_val = room.Ly * i / 4.0
        fig_layout.add_trace(go.Scatter(
            x=[0, room.Lx], y=[y_val, y_val],
            mode='lines', line=dict(color='lightgray', width=1, dash='dash'),
            showlegend=False, hoverinfo='skip'
        ))

    # Plot Equipment (Speakers)
    spk_texts = [f"Spk 1Z: {spk_zs[0]:.2f}m"] if num_sources == 1 else [f"Spk LZ: {spk_zs[0]:.2f}m", f"Spk RZ: {spk_zs[1]:.2f}m"]
    fig_layout.add_trace(go.Scatter(
        x=spk_xs, y=spk_ys, mode='markers+text',
        marker=dict(size=12, color='blue', symbol='square', line=dict(color='white', width=2)),
        text=spk_texts, textposition="top center",
        name="Speaker(s)"
    ))

    # Plot Microphone
    fig_layout.add_trace(go.Scatter(
        x=[mic_x], y=[mic_y], mode='markers+text',
        marker=dict(size=12, color='red', symbol='diamond', line=dict(color='white', width=2)),
        text=[f"MicZ: {mic_z:.2f}m"], textposition="top center",
        name="Mic"
    ))

    fig_layout.update_layout(
        xaxis=dict(
            range=[0, room.Lx], title="Width (X) [m]", 
            dtick=0.5, ticks="inside", ticklen=8,
            minor=dict(dtick=0.1, ticks="inside", ticklen=4),
            showgrid=False, zeroline=False
        ),
        yaxis=dict(
            range=[0, room.Ly], title="Depth (Y) [m]", 
            dtick=0.5, ticks="inside", ticklen=8,
            minor=dict(dtick=0.1, ticks="outside", ticklen=4),
            showgrid=False, zeroline=False
        ),
        yaxis_scaleanchor="x",
        yaxis_scaleratio=1,
        margin=dict(l=6, r=6, b=6, t=25),
        height=chart_height,
        title="Top-Down Placement View (XY Plane)"
    )
    
    return fig_layout

def create_freq_response_plot(freqs_1d: np.ndarray, f_response_db: np.ndarray, chart_height: int) -> go.Figure:
    fig_f = go.Figure(data=go.Scatter(x=freqs_1d, y=f_response_db, mode='lines+markers', line=dict(color='red', width=2)))
    fig_f.update_layout(
        xaxis_title="Frequency (Hz)", yaxis_title="Relative SPL (dB)", 
        yaxis=dict(range=[-25, 2]),
        margin=dict(l=10, r=10, b=10, t=30), height=chart_height, title="Frequency Response (Max Peak = 0dB)"
    )
    return fig_f

def create_volume_plot(room: RoomConfig, spk_xs: list, spk_ys: list, spk_zs: list, mic_x: float, mic_y: float, mic_z: float, 
                       X_flat: np.ndarray, Y_flat: np.ndarray, Z_flat: np.ndarray, tensor_abs: np.ndarray, freqs_3d: np.ndarray, 
                       chart_height: int, is_corner_mode: bool = False) -> go.Figure:
    fig_vol = go.Figure()

    for trace in draw_room_wireframe(room.Lx, room.Ly, room.Lz):
        fig_vol.add_trace(trace)

    if is_corner_mode:
        trace_spk = go.Scatter3d(x=spk_xs, y=spk_ys, z=spk_zs, mode='markers', marker=dict(size=8, color='black', symbol='square', line=dict(color='white', width=2)), name="Source (Corner)")
        trace_mic = go.Scatter3d(x=[mic_x], y=[mic_y], z=[mic_z], mode='markers', marker=dict(size=8, color='red', symbol='diamond', line=dict(color='white', width=2)), name="Mic (Current)")
    else:
        trace_spk = go.Scatter3d(x=spk_xs, y=spk_ys, z=spk_zs, mode='markers', marker=dict(size=8, color='blue', symbol='square', line=dict(color='white', width=2)), name="Speaker(s)")
        trace_mic = go.Scatter3d(x=[mic_x], y=[mic_y], z=[mic_z], mode='markers', marker=dict(size=8, color='red', symbol='diamond', line=dict(color='white', width=2)), name="Mic")

    fig_vol.add_trace(trace_spk)
    fig_vol.add_trace(trace_mic)

    # --- Statistical Scaling via Standard Deviation ---
    mean_val = np.mean(tensor_abs)
    std_val = np.std(tensor_abs)

    robust_min = max(0.0, mean_val - 2 * std_val)
    robust_max = mean_val + 2 * std_val
    range_span = robust_max - robust_min
    fixed_valley_max = robust_min + range_span * 0.3
    fixed_peak_min = robust_min + range_span * 0.7

    abs_min = np.min(tensor_abs)
    abs_max = np.max(tensor_abs)

    initial_val = tensor_abs[0].flatten().astype(np.float32)

    # Trace: Valleys
    fig_vol.add_trace(go.Volume(
        x=X_flat, y=Y_flat, z=Z_flat, value=initial_val,
        isomin=abs_min, isomax=fixed_valley_max,
        opacity=0.25, surface_count=8, colorscale='RdYlBu_r',
        cmin=robust_min, cmax=robust_max,
        caps=dict(x_show=False, y_show=False, z_show=False),
        name='Valleys', showscale=False
    ))

    # Trace: Peaks
    fig_vol.add_trace(go.Volume(
        x=X_flat, y=Y_flat, z=Z_flat, value=initial_val,
        isomin=fixed_peak_min, isomax=abs_max,
        opacity=0.3, surface_count=6, colorscale='RdYlBu_r',
        cmin=robust_min, cmax=robust_max,
        caps=dict(x_show=False, y_show=False, z_show=False),
        name='Peaks'
    ))

    # --- Generate Animation Frames ---
    frames = []
    for i, f in enumerate(freqs_3d):
        val = tensor_abs[i].flatten().astype(np.float32)
        frames.append(go.Frame(
            data=[
                go.Volume(value=val, isomin=abs_min, isomax=fixed_valley_max),
                go.Volume(value=val, isomin=fixed_peak_min, isomax=abs_max)
            ],
            traces=[4, 5], 
            name=str(f)
        ))
    fig_vol.frames = frames

    fig_vol.update_layout(
        uirevision="constant",
        scene=dict(xaxis_title='X', yaxis_title='Y', zaxis_title='Z', aspectmode='data'),
        margin=dict(l=0, r=0, b=0, t=30), height=chart_height, showlegend=False,
        updatemenus=[dict(
            type="buttons",
            x=0.05, y=0,
            direction="left",
            buttons=[
                dict(label="Play", method="animate", args=[None, dict(frame=dict(duration=500, redraw=True), transition=dict(duration=0), fromcurrent=True)]),
                dict(label="Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate", transition=dict(duration=0))])
            ]
        )],
        sliders=[dict(
            active=0, yanchor="top", xanchor="left", currentvalue=dict(font=dict(size=16), prefix="Frequency: ", suffix=" Hz"),
            transition=dict(duration=0), pad=dict(b=10, t=50), len=0.9, x=0.15, y=0,
            steps=[dict(args=[[str(f)], dict(frame=dict(duration=300, redraw=True), mode="immediate", transition=dict(duration=0))],
                        label=str(f), method="animate") for f in freqs_3d]
        )]
    )

    return fig_vol