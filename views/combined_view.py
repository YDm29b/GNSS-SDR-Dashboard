"""
views/combined_view.py
======================
Unified Side-by-Side 3D Constellation & 2D Ground-Track Dashboard.
Fulfills Item 5: Places the 3D Globe and 2D World Map in ONE unified
Plotly figure with subplots, sharing ONE set of animation frames,
ONE Play/Pause button, and ONE interactive time-scrubber slider.
"""

from typing import Dict, List, Optional
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from core.orbit_engine import WGS84_EARTH_RADIUS_KM
from views.globe_view_3d import create_earth_mesh, build_animation_controls


def create_unified_constellation_figure(
    sim_data: Dict,
    observer_name: str = "Multan, Pakistan",
    show_orbital_rings: bool = True,
    show_tracks: bool = True
) -> go.Figure:
    """
    Builds a single dual-panel figure (3D Globe on Left, 2D Map on Right)
    with synchronized client-side animation frames and shared slider controls.
    """
    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "scene"}, {"type": "geo"}]],
        subplot_titles=[
            "<b>3D Constellation Orbit Shell</b>",
            "<b>2D Sub-Satellite Ground-Track Projection</b>"
        ],
        horizontal_spacing=0.03
    )

    obs_lat = sim_data["observer_lat"]
    obs_lon = sim_data["observer_lon"]
    sats_meta = sim_data["satellites"]
    num_steps = sim_data["num_steps"]

    # =========================================================================
    # 1. 3D STATIC TRACES (Col 1)
    # =========================================================================
    # Earth surface
    x_e, y_e, z_e = create_earth_mesh(WGS84_EARTH_RADIUS_KM, n_phi=28, n_theta=54)
    fig.add_trace(
        go.Surface(
            x=x_e, y=y_e, z=z_e,
            colorscale=[[0.0, "#040b17"], [0.35, "#081d38"], [0.7, "#103463"], [1.0, "#194a86"]],
            showscale=False, hoverinfo="skip", opacity=0.92, name="Earth"
        ),
        row=1, col=1
    )

    # Equator ring
    eq_theta = np.linspace(-np.pi, np.pi, 72)
    fig.add_trace(
        go.Scatter3d(
            x=WGS84_EARTH_RADIUS_KM * np.cos(eq_theta),
            y=WGS84_EARTH_RADIUS_KM * np.sin(eq_theta),
            z=np.zeros_like(eq_theta),
            mode="lines", line=dict(color="rgba(0, 242, 254, 0.4)", width=2),
            hoverinfo="skip", showlegend=False, name="Equator"
        ),
        row=1, col=1
    )

    # Observer 3D pin
    obs_lat_rad = np.radians(obs_lat)
    obs_lon_rad = np.radians(obs_lon)
    obs_x = (WGS84_EARTH_RADIUS_KM + 150) * np.cos(obs_lat_rad) * np.cos(obs_lon_rad)
    obs_y = (WGS84_EARTH_RADIUS_KM + 150) * np.cos(obs_lat_rad) * np.sin(obs_lon_rad)
    obs_z = (WGS84_EARTH_RADIUS_KM + 150) * np.sin(obs_lat_rad)
    fig.add_trace(
        go.Scatter3d(
            x=[obs_x], y=[obs_y], z=[obs_z],
            mode="markers+text",
            marker=dict(size=6, color="#ff007f", symbol="diamond", line=dict(color="#ffffff", width=1.5)),
            text=[f" 📍 {observer_name}"],
            textposition="top center",
            textfont=dict(color="#ffffff", size=10),
            hovertext=f"<b>{observer_name}</b><br>Lat: {obs_lat:.2f}° | Lon: {obs_lon:.2f}°",
            hoverinfo="text",
            name="Observer Pin"
        ),
        row=1, col=1
    )

    # 3D Orbital plane guide rings
    if show_orbital_rings:
        r_orbit = 26560.0
        inc = np.radians(55.0)
        for plane_idx, raan_deg in enumerate(range(0, 360, 60)):
            raan = np.radians(raan_deg)
            u = np.linspace(0, 2 * np.pi, 60)
            x_orb = r_orbit * (np.cos(raan) * np.cos(u) - np.sin(raan) * np.sin(u) * np.cos(inc))
            y_orb = r_orbit * (np.sin(raan) * np.cos(u) + np.cos(raan) * np.sin(u) * np.cos(inc))
            z_orb = r_orbit * (np.sin(u) * np.sin(inc))
            fig.add_trace(
                go.Scatter3d(
                    x=x_orb, y=y_orb, z=z_orb,
                    mode="lines", line=dict(color="rgba(0, 242, 254, 0.15)", width=1.2, dash="dot"),
                    hoverinfo="skip", showlegend=(plane_idx == 0), name="Orbital Planes (55°)"
                ),
                row=1, col=1
            )

    # =========================================================================
    # 2. 3D DYNAMIC TRACES (Col 1)
    # =========================================================================
    idx_3d_vis = len(fig.data)
    idx_3d_hid = idx_3d_vis + 1

    hover_tmpl_3d = (
        "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
        "Block: %{customdata[2]}<br>"
        "Altitude: %{customdata[3]:,.0f} km<br>"
        "Az: %{customdata[6]:.1f}° | El: <b>%{customdata[7]:.1f}°</b><br>"
        "Status: <b>%{customdata[8]}</b><extra></extra>"
    )

    fig.add_trace(
        go.Scatter3d(
            x=[], y=[], z=[], mode="markers+text",
            marker=dict(size=5.5, color="#00ff88", symbol="diamond", line=dict(color="#ffffff", width=1)),
            textfont=dict(color="#00ff88", size=8.5, family="Orbitron, monospace"),
            hovertemplate=hover_tmpl_3d, name="3D: Visible (El ≥ mask)"
        ),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter3d(
            x=[], y=[], z=[], mode="markers",
            marker=dict(size=3.8, color="#ffa200", symbol="circle", opacity=0.75),
            hovertemplate=hover_tmpl_3d, name="3D: Below Horizon"
        ),
        row=1, col=1
    )

    # =========================================================================
    # 3. 2D STATIC TRACES (Col 2)
    # =========================================================================
    # Ground station pin on 2D map
    fig.add_trace(
        go.Scattergeo(
            lat=[obs_lat], lon=[obs_lon], mode="markers+text",
            marker=dict(size=9, color="#ff007f", symbol="star", line=dict(width=1.5, color="#ffffff")),
            text=[f"  📍 {observer_name}"], textposition="top right",
            textfont=dict(color="#ffffff", size=10),
            hovertext=f"<b>Ground Station: {observer_name}</b>", hoverinfo="text",
            showlegend=False
        ),
        row=1, col=2
    )

    # Decimated 12h ground track curves
    if show_tracks and "ground_tracks" in sim_data:
        for sat_name, track_data in sim_data["ground_tracks"].items():
            fig.add_trace(
                go.Scattergeo(
                    lat=track_data["lats"], lon=track_data["lons"],
                    mode="lines", line=dict(width=0.8, color="rgba(56, 189, 248, 0.2)"),
                    hoverinfo="skip", showlegend=False
                ),
                row=1, col=2
            )

    # =========================================================================
    # 4. 2D DYNAMIC TRACES (Col 2)
    # =========================================================================
    idx_2d_vis = len(fig.data)
    idx_2d_hid = idx_2d_vis + 1

    hover_tmpl_2d = (
        "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
        "Sub-point: Lat %{customdata[4]:.2f}°, Lon %{customdata[5]:.2f}°<br>"
        "El: <b>%{customdata[7]:.1f}°</b> | Az: %{customdata[6]:.1f}°<extra></extra>"
    )

    fig.add_trace(
        go.Scattergeo(
            lat=[], lon=[], mode="markers+text",
            marker=dict(size=6.5, color="#00ff88", symbol="diamond", line=dict(color="#ffffff", width=1)),
            textfont=dict(color="#00ff88", size=8.5, family="Orbitron, monospace"),
            hovertemplate=hover_tmpl_2d, name="2D: Visible Overhead"
        ),
        row=1, col=2
    )
    fig.add_trace(
        go.Scattergeo(
            lat=[], lon=[], mode="markers",
            marker=dict(size=4.0, color="#ffa200", symbol="circle", opacity=0.75),
            hovertemplate=hover_tmpl_2d, name="2D: Below Horizon"
        ),
        row=1, col=2
    )

    # Satellite metadata for fast hover string generation
    names = [s["display_name"] for s in sats_meta]
    norads = [str(s["norad_id"]) for s in sats_meta]
    blocks = [s["block_type"] for s in sats_meta]

    def build_frame_payloads(step: int):
        v_mask = sim_data["is_visible"][:, step]
        h_mask = ~v_mask
        v_idx = np.where(v_mask)[0]
        h_idx = np.where(h_mask)[0]

        def get_hover_3d(indices, is_vis):
            st_str = "Visible (El ≥ mask)" if is_vis else "Below Horizon"
            return [
                (
                    f"<b>{names[i]}</b> (NORAD {norads[i]})<br>"
                    f"Block: {blocks[i]}<br>"
                    f"Altitude: {float(sim_data['alt_km'][i, step]):,.0f} km<br>"
                    f"Sub-point: Lat {float(sim_data['lat'][i, step]):.2f}°, Lon {float(sim_data['lon'][i, step]):.2f}°<br>"
                    f"Azimuth: {float(sim_data['az'][i, step]):.1f}° | Elevation: <b>{float(sim_data['el'][i, step]):.1f}°</b><br>"
                    f"Status: <b>{st_str}</b>"
                )
                for i in indices
            ]

        def get_hover_2d(indices, is_vis):
            st_str = "Visible Overhead" if is_vis else "Below Horizon"
            return [
                (
                    f"<b>{names[i]}</b> (NORAD {norads[i]})<br>"
                    f"Sub-point: Lat {float(sim_data['lat'][i, step]):.2f}°, Lon {float(sim_data['lon'][i, step]):.2f}°<br>"
                    f"Elevation: <b>{float(sim_data['el'][i, step]):.1f}°</b> | Az: {float(sim_data['az'][i, step]):.1f}°<br>"
                    f"Status: <b>{st_str}</b>"
                )
                for i in indices
            ]

        # 3D
        x3_v = sim_data["x_ecef"][v_idx, step].tolist()
        y3_v = sim_data["y_ecef"][v_idx, step].tolist()
        z3_v = sim_data["z_ecef"][v_idx, step].tolist()
        t3_v = [names[i] for i in v_idx]
        h3_v = get_hover_3d(v_idx, True)

        x3_h = sim_data["x_ecef"][h_idx, step].tolist()
        y3_h = sim_data["y_ecef"][h_idx, step].tolist()
        z3_h = sim_data["z_ecef"][h_idx, step].tolist()
        h3_h = get_hover_3d(h_idx, False)

        # 2D
        lat_v = sim_data["lat"][v_idx, step].tolist()
        lon_v = sim_data["lon"][v_idx, step].tolist()
        h2_v = get_hover_2d(v_idx, True)

        lat_h = sim_data["lat"][h_idx, step].tolist()
        lon_h = sim_data["lon"][h_idx, step].tolist()
        h2_h = get_hover_2d(h_idx, False)

        return (
            (x3_v, y3_v, z3_v, t3_v, h3_v),
            (x3_h, y3_h, z3_h, h3_h),
            (lat_v, lon_v, t3_v, h2_v),
            (lat_h, lon_h, h2_h)
        )

    # Initialize trace state at step 0
    p3v, p3h, p2v, p2h = build_frame_payloads(0)
    fig.data[idx_3d_vis].update(x=p3v[0], y=p3v[1], z=p3v[2], text=p3v[3], hovertext=p3v[4], hoverinfo="text")
    fig.data[idx_3d_hid].update(x=p3h[0], y=p3h[1], z=p3h[2], hovertext=p3h[3], hoverinfo="text")
    fig.data[idx_2d_vis].update(lat=p2v[0], lon=p2v[1], text=p2v[2], hovertext=p2v[3], hoverinfo="text")
    fig.data[idx_2d_hid].update(lat=p2h[0], lon=p2h[1], hovertext=p2h[2], hoverinfo="text")

    frames = []
    for step in range(num_steps):
        p3v, p3h, p2v, p2h = build_frame_payloads(step)
        frame = go.Frame(
            data=[
                go.Scatter3d(x=p3v[0], y=p3v[1], z=p3v[2], text=p3v[3], hovertext=p3v[4], hoverinfo="text"),
                go.Scatter3d(x=p3h[0], y=p3h[1], z=p3h[2], text=None, hovertext=p3h[3], hoverinfo="text"),
                go.Scattergeo(lat=p2v[0], lon=p2v[1], text=p2v[2], hovertext=p2v[3], hoverinfo="text"),
                go.Scattergeo(lat=p2h[0], lon=p2h[1], text=None, hovertext=p2h[2], hoverinfo="text")
            ],
            traces=[idx_3d_vis, idx_3d_hid, idx_2d_vis, idx_2d_hid],
            name=sim_data["time_labels"][step]
        )
        frames.append(frame)

    fig.frames = frames

    # =========================================================================
    # 6. LAYOUT & UNIFIED CONTROLS
    # =========================================================================
    updatemenus, sliders = build_animation_controls(frames, frame_duration_ms=70)

    axis_config = dict(
        showbackground=False, showgrid=True,
        gridcolor="rgba(56, 189, 248, 0.12)", zeroline=False,
        showticklabels=False, title=""
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, b=30, t=35),
        uirevision="constant",
        scene=dict(
            xaxis=axis_config, yaxis=axis_config, zaxis=axis_config,
            aspectmode="data", dragmode="orbit",
            camera=dict(eye=dict(x=1.45, y=1.45, z=1.15), up=dict(x=0, y=0, z=1)),
            bgcolor="rgba(0,0,0,0)"
        ),
        geo=dict(
            projection_type="equirectangular",
            showland=True, landcolor="#0e1726",
            showocean=True, oceancolor="#040b17",
            showlakes=True, lakecolor="#040b17",
            showcountries=True, countrycolor="#1e293b", countrywidth=0.7,
            coastlinecolor="#334155", coastlinewidth=0.9,
            lataxis=dict(showgrid=True, gridcolor="rgba(56, 189, 248, 0.08)", range=[-75, 75], dtick=30),
            lonaxis=dict(showgrid=True, gridcolor="rgba(56, 189, 248, 0.08)", range=[-180, 180], dtick=60),
            bgcolor="rgba(0,0,0,0)"
        ),
        updatemenus=updatemenus,
        sliders=sliders,
        legend=dict(
            x=0.01, y=-0.12,
            orientation="h",
            bgcolor="rgba(13, 20, 36, 0.75)",
            bordercolor="rgba(56, 189, 248, 0.3)",
            borderwidth=1,
            font=dict(size=10, color="#e2e8f0")
        ),
        height=660
    )

    return fig
