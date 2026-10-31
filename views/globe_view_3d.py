"""
views/globe_view_3d.py
======================
Renders an interactive 3D Earth globe with the operational GPS satellite
constellation plotted in their Medium Earth Orbit (MEO) shells.

Overhauled for client-side Plotly native animation (go.Frame):
  - Precomputes all frames once; runs smoothly in-browser without Streamlit reruns.
  - Earth rendered via a lightweight 60x30 mesh with hoverinfo="skip".
  - Camera uses dragmode="orbit", fixed aspectmode="data", and uirevision="constant"
    to preserve user rotation/pan across playback frames.
  - Native Play/Pause buttons and time scrubber slider embedded directly in the figure.
"""

from typing import Dict, List, Optional
import numpy as np
import plotly.graph_objects as go
from core.orbit_engine import WGS84_EARTH_RADIUS_KM


def create_earth_mesh(radius_km: float = WGS84_EARTH_RADIUS_KM, n_phi: int = 30, n_theta: int = 60):
    """
    Generates a low-resolution spherical mesh for the Earth surface (Item 4).
    """
    phi = np.linspace(-np.pi / 2, np.pi / 2, n_phi)
    theta = np.linspace(-np.pi, np.pi, n_theta)
    phi, theta = np.meshgrid(phi, theta)

    x = radius_km * np.cos(phi) * np.cos(theta)
    y = radius_km * np.cos(phi) * np.sin(theta)
    z = radius_km * np.sin(phi)
    return x, y, z


def build_animation_controls(frames: List[go.Frame], frame_duration_ms: int = 65):
    """
    Constructs native Plotly updatemenus (Play/Pause) and time-scrubber slider.
    """
    updatemenus = [
        dict(
            type="buttons",
            showactive=False,
            x=0.04,
            y=-0.06,
            xanchor="left",
            yanchor="top",
            direction="left",
            pad=dict(r=10, t=10),
            bgcolor="rgba(15, 23, 42, 0.8)",
            bordercolor="rgba(56, 189, 248, 0.4)",
            borderwidth=1,
            font=dict(color="#38bdf8", size=12),
            buttons=[
                dict(
                    label="▶ Play",
                    method="animate",
                    args=[
                        None,
                        dict(
                            frame=dict(duration=frame_duration_ms, redraw=True),
                            fromcurrent=True,
                            transition=dict(duration=0),
                            mode="immediate"
                        )
                    ]
                ),
                dict(
                    label="⏸ Pause",
                    method="animate",
                    args=[
                        [None],
                        dict(
                            frame=dict(duration=0, redraw=False),
                            mode="immediate",
                            transition=dict(duration=0)
                        )
                    ]
                )
            ]
        )
    ]

    # Sample slider steps so ticks remain clean (show label every 30 or 60 min)
    slider_steps = []
    for frame in frames:
        slider_steps.append(
            dict(
                args=[
                    [frame.name],
                    dict(
                        frame=dict(duration=0, redraw=True),
                        mode="immediate",
                        transition=dict(duration=0)
                    )
                ],
                label=frame.name,
                method="animate"
            )
        )

    sliders = [
        dict(
            active=0,
            x=0.20,
            y=-0.06,
            xanchor="left",
            yanchor="top",
            len=0.76,
            pad=dict(b=10, t=10),
            bgcolor="rgba(15, 23, 42, 0.6)",
            bordercolor="rgba(56, 189, 248, 0.3)",
            borderwidth=1,
            font=dict(color="#94a3b8", size=10),
            currentvalue=dict(
                font=dict(size=12, color="#00f2fe", family="Orbitron, monospace"),
                prefix="Time: ",
                visible=True,
                xanchor="right"
            ),
            transition=dict(duration=0),
            steps=slider_steps
        )
    ]

    return updatemenus, sliders


def create_animated_globe_3d_figure(
    sim_data: Dict,
    observer_name: str = "Multan, Pakistan",
    show_orbital_rings: bool = True
) -> go.Figure:
    """
    Builds the Plotly 3D Figure with native go.Frame client-side animation.
    Only satellite scatter traces are updated in frames; all static geometry is excluded.
    """
    fig = go.Figure()

    # =========================================================================
    # STATIC TRACES (Excluded from frames, hoverinfo='skip')
    # =========================================================================

    # 1. Earth Sphere Surface (Low-resolution mesh: ~60x30 grid)
    x_e, y_e, z_e = create_earth_mesh(WGS84_EARTH_RADIUS_KM, n_phi=30, n_theta=60)
    fig.add_trace(go.Surface(
        x=x_e,
        y=y_e,
        z=z_e,
        colorscale=[
            [0.0, "#040b17"],
            [0.35, "#081d38"],
            [0.7, "#103463"],
            [1.0, "#194a86"]
        ],
        showscale=False,
        hoverinfo="skip",
        opacity=0.92,
        name="Earth (WGS84)"
    ))

    # 2. Equator Ring on Earth (Latitude = 0°)
    eq_theta = np.linspace(-np.pi, np.pi, 90)
    eq_x = WGS84_EARTH_RADIUS_KM * np.cos(eq_theta)
    eq_y = WGS84_EARTH_RADIUS_KM * np.sin(eq_theta)
    eq_z = np.zeros_like(eq_theta)
    fig.add_trace(go.Scatter3d(
        x=eq_x, y=eq_y, z=eq_z,
        mode="lines",
        line=dict(color="rgba(0, 242, 254, 0.45)", width=2),
        hoverinfo="skip",
        showlegend=False,
        name="Equator"
    ))

    # 3. Observer Location on Earth Surface
    obs_lat = sim_data["observer_lat"]
    obs_lon = sim_data["observer_lon"]
    obs_lat_rad = np.radians(obs_lat)
    obs_lon_rad = np.radians(obs_lon)
    obs_x = (WGS84_EARTH_RADIUS_KM + 160) * np.cos(obs_lat_rad) * np.cos(obs_lon_rad)
    obs_y = (WGS84_EARTH_RADIUS_KM + 160) * np.cos(obs_lat_rad) * np.sin(obs_lon_rad)
    obs_z = (WGS84_EARTH_RADIUS_KM + 160) * np.sin(obs_lat_rad)

    fig.add_trace(go.Scatter3d(
        x=[obs_x], y=[obs_y], z=[obs_z],
        mode="markers+text",
        marker=dict(size=6, color="#ff007f", symbol="diamond", line=dict(color="#ffffff", width=1.5)),
        text=[f"  📍 {observer_name}"],
        textposition="top center",
        textfont=dict(color="#ffffff", size=11, family="Inter, sans-serif"),
        hovertext=(
            f"<b>Ground Station: {observer_name}</b><br>"
            f"Lat: {obs_lat:.4f}° | Lon: {obs_lon:.4f}°"
        ),
        hoverinfo="text",
        name=f"Observer ({observer_name})"
    ))

    # 4. GPS Orbital Plane Guide Rings (55° Inclination, faint cyan, hoverinfo='skip')
    if show_orbital_rings:
        r_orbit = 26560.0  # nominal GPS semi-major axis in km
        inc = np.radians(55.0)
        for plane_idx, raan_deg in enumerate(range(0, 360, 60)):
            raan = np.radians(raan_deg)
            u = np.linspace(0, 2 * np.pi, 72)
            x_orb = r_orbit * (np.cos(raan) * np.cos(u) - np.sin(raan) * np.sin(u) * np.cos(inc))
            y_orb = r_orbit * (np.sin(raan) * np.cos(u) + np.cos(raan) * np.sin(u) * np.cos(inc))
            z_orb = r_orbit * (np.sin(u) * np.sin(inc))

            fig.add_trace(go.Scatter3d(
                x=x_orb, y=y_orb, z=z_orb,
                mode="lines",
                line=dict(color="rgba(0, 242, 254, 0.16)", width=1.5, dash="dot"),
                hoverinfo="skip",
                showlegend=(plane_idx == 0),
                name="GPS Orbital Planes (55° Inc)"
            ))

    # =========================================================================
    # DYNAMIC SATELLITE TRACES (Indices to be updated in frames)
    # =========================================================================
    idx_vis = len(fig.data)
    idx_hid = idx_vis + 1

    # Base state at timestep 0
    t0 = 0
    vis_mask_0 = sim_data["is_visible"][:, t0]
    hid_mask_0 = ~vis_mask_0
    sats_meta = sim_data["satellites"]

    def extract_scatter_payload(step_idx: int, mask: np.ndarray, is_visible_group: bool):
        sat_indices = np.where(mask)[0]
        if len(sat_indices) == 0:
            return dict(x=[], y=[], z=[], text=[], customdata=[])

        x_vals = sim_data["x_ecef"][sat_indices, step_idx].tolist()
        y_vals = sim_data["y_ecef"][sat_indices, step_idx].tolist()
        z_vals = sim_data["z_ecef"][sat_indices, step_idx].tolist()

        texts = [sats_meta[i]["display_name"] for i in sat_indices]
        custom_data = [
            (
                sats_meta[i]["display_name"],
                sats_meta[i]["norad_id"],
                sats_meta[i]["block_type"],
                float(sim_data["alt_km"][i, step_idx]),
                float(sim_data["lat"][i, step_idx]),
                float(sim_data["lon"][i, step_idx]),
                float(sim_data["az"][i, step_idx]),
                float(sim_data["el"][i, step_idx]),
                "Visible (Acquisition Zone)" if is_visible_group else "Below Horizon"
            )
            for i in sat_indices
        ]
        return dict(x=x_vals, y=y_vals, z=z_vals, text=texts, customdata=custom_data)

    p0_vis = extract_scatter_payload(t0, vis_mask_0, True)
    p0_hid = extract_scatter_payload(t0, hid_mask_0, False)

    hover_template = (
        "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
        "Block: %{customdata[2]}<br>"
        "Altitude: %{customdata[3]:,.0f} km<br>"
        "Sub-point: Lat %{customdata[4]:.2f}°, Lon %{customdata[5]:.2f}°<br>"
        "Azimuth: %{customdata[6]:.1f}° | Elevation: <b>%{customdata[7]:.1f}°</b><br>"
        "Status: <b>%{customdata[8]}</b>"
        "<extra></extra>"
    )

    fig.add_trace(go.Scatter3d(
        x=p0_vis["x"], y=p0_vis["y"], z=p0_vis["z"],
        mode="markers+text",
        marker=dict(size=6, color="#00ff88", symbol="diamond", line=dict(color="#ffffff", width=1)),
        text=p0_vis["text"],
        textposition="top center",
        textfont=dict(color="#00ff88", size=9, family="Orbitron, monospace"),
        customdata=p0_vis["customdata"],
        hovertemplate=hover_template,
        name="Visible (El ≥ mask)"
    ))

    fig.add_trace(go.Scatter3d(
        x=p0_hid["x"], y=p0_hid["y"], z=p0_hid["z"],
        mode="markers",
        marker=dict(size=4, color="#ffa200", symbol="circle", opacity=0.75, line=dict(color="#222222", width=0.5)),
        text=None,
        customdata=p0_hid["customdata"],
        hovertemplate=hover_template,
        name="Below Horizon"
    ))

    # =========================================================================
    # BUILD NATIVE go.Frame OBJECTS
    # =========================================================================
    num_steps = sim_data["num_steps"]
    frames = []

    for step in range(num_steps):
        v_mask = sim_data["is_visible"][:, step]
        h_mask = ~v_mask
        p_v = extract_scatter_payload(step, v_mask, True)
        p_h = extract_scatter_payload(step, h_mask, False)

        frame = go.Frame(
            data=[
                go.Scatter3d(
                    x=p_v["x"], y=p_v["y"], z=p_v["z"],
                    text=p_v["text"], customdata=p_v["customdata"]
                ),
                go.Scatter3d(
                    x=p_h["x"], y=p_h["y"], z=p_h["z"],
                    text=None, customdata=p_h["customdata"]
                )
            ],
            traces=[idx_vis, idx_hid],
            name=sim_data["time_labels"][step]
        )
        frames.append(frame)

    fig.frames = frames

    # =========================================================================
    # LAYOUT: Camera, Controls, Aesthetic
    # =========================================================================
    updatemenus, sliders = build_animation_controls(frames, frame_duration_ms=70)

    axis_config = dict(
        showbackground=False,
        showgrid=True,
        gridcolor="rgba(56, 189, 248, 0.12)",
        zeroline=False,
        showticklabels=False,
        title=""
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, b=30, t=10),
        uirevision="constant",  # Preserves camera orientation during playback!
        dragmode="orbit",       # Smooth intuitive 3D orbit rotation
        scene=dict(
            xaxis=axis_config,
            yaxis=axis_config,
            zaxis=axis_config,
            aspectmode="data",  # Fixed equal aspect
            camera=dict(
                eye=dict(x=1.45, y=1.45, z=1.15),
                up=dict(x=0, y=0, z=1)
            ),
            bgcolor="rgba(0,0,0,0)"
        ),
        updatemenus=updatemenus,
        sliders=sliders,
        legend=dict(
            x=0.02, y=0.96,
            bgcolor="rgba(13, 20, 36, 0.75)",
            bordercolor="rgba(56, 189, 248, 0.3)",
            borderwidth=1,
            font=dict(size=11, color="#e2e8f0")
        ),
        height=660
    )

    return fig
