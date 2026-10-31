"""
views/ground_track_view.py
==========================
Renders a 2D global ground-track projection of the GPS constellation.
Visualizes sub-satellite points on the WGS84 Earth ellipsoid and repeating
orbital ground tracks bounded between +/-55° latitude.

Overhauled for client-side Plotly native animation (go.Frame):
  - Base map and 12-hour ground track lines are static (hoverinfo="skip").
  - Ground tracks decimated to every ~5th point for lightweight rendering.
  - Only moving satellite points are updated in frames via trace indices.
  - uirevision="constant" ensures zoom/pan states are maintained during animation.
"""

from typing import Dict, List, Optional
import numpy as np
import plotly.graph_objects as go
from views.globe_view_3d import build_animation_controls


def create_animated_ground_track_figure(
    sim_data: Dict,
    observer_name: str = "Multan, Pakistan",
    show_tracks: bool = True
) -> go.Figure:
    """
    Builds the Plotly 2D Scattergeo world ground-track map with native animation frames.
    """
    fig = go.Figure()

    # =========================================================================
    # STATIC TRACES
    # =========================================================================

    # 1. Ground station pin
    obs_lat = sim_data["observer_lat"]
    obs_lon = sim_data["observer_lon"]

    fig.add_trace(go.Scattergeo(
        lat=[obs_lat],
        lon=[obs_lon],
        mode="markers+text",
        marker=dict(
            size=10,
            color="#ff007f",
            symbol="star",
            line=dict(width=1.5, color="#ffffff")
        ),
        text=[f"  📍 {observer_name}"],
        textposition="top right",
        textfont=dict(color="#ffffff", size=11, family="Inter, sans-serif"),
        hovertext=(
            f"<b>Ground Station: {observer_name}</b><br>"
            f"Latitude: {obs_lat:.4f}° N<br>"
            f"Longitude: {obs_lon:.4f}° E"
        ),
        hoverinfo="text",
        name=f"Observer ({observer_name})"
    ))

    # 2. Orbital Ground Track Curves (Decimated trails over ~12 hours)
    if show_tracks and "ground_tracks" in sim_data:
        for sat_name, track_data in sim_data["ground_tracks"].items():
            fig.add_trace(go.Scattergeo(
                lat=track_data["lats"],
                lon=track_data["lons"],
                mode="lines",
                line=dict(width=1.0, color="rgba(56, 189, 248, 0.22)"),
                hoverinfo="skip",
                showlegend=False,
                name=f"{sat_name} Orbit Trail"
            ))

    # =========================================================================
    # DYNAMIC TRACES (Indices updated in frames)
    # =========================================================================
    idx_vis = len(fig.data)
    idx_hid = idx_vis + 1

    t0 = 0
    vis_mask_0 = sim_data["is_visible"][:, t0]
    hid_mask_0 = ~vis_mask_0
    sats_meta = sim_data["satellites"]

    def extract_geo_payload(step_idx: int, mask: np.ndarray, is_vis: bool):
        sat_indices = np.where(mask)[0]
        if len(sat_indices) == 0:
            return dict(lat=[], lon=[], text=[], customdata=[])

        lat_vals = sim_data["lat"][sat_indices, step_idx].tolist()
        lon_vals = sim_data["lon"][sat_indices, step_idx].tolist()
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
                "Visible (Acquisition Zone)" if is_vis else "Below Horizon"
            )
            for i in sat_indices
        ]
        return dict(lat=lat_vals, lon=lon_vals, text=texts, customdata=custom_data)

    p0_vis = extract_geo_payload(t0, vis_mask_0, True)
    p0_hid = extract_geo_payload(t0, hid_mask_0, False)

    hover_template = (
        "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
        "Block: %{customdata[2]}<br>"
        "Sub-point: Lat %{customdata[4]:.2f}°, Lon %{customdata[5]:.2f}°<br>"
        "Altitude: %{customdata[3]:,.0f} km<br>"
        "Azimuth: %{customdata[6]:.1f}° | Elevation: <b>%{customdata[7]:.1f}°</b><br>"
        "Status: <b>%{customdata[8]}</b>"
        "<extra></extra>"
    )

    fig.add_trace(go.Scattergeo(
        lat=p0_vis["lat"], lon=p0_vis["lon"],
        mode="markers+text",
        marker=dict(size=7, color="#00ff88", symbol="diamond", line=dict(color="#ffffff", width=1)),
        text=p0_vis["text"],
        textposition="top center",
        textfont=dict(color="#00ff88", size=9, family="Orbitron, monospace"),
        customdata=p0_vis["customdata"],
        hovertemplate=hover_template,
        name="Visible Overhead (El ≥ mask)"
    ))

    fig.add_trace(go.Scattergeo(
        lat=p0_hid["lat"], lon=p0_hid["lon"],
        mode="markers",
        marker=dict(size=4.5, color="#ffa200", symbol="circle", opacity=0.75, line=dict(color="#222222", width=0.5)),
        text=None,
        customdata=p0_hid["customdata"],
        hovertemplate=hover_template,
        name="Below Horizon"
    ))

    # =========================================================================
    # BUILD FRAMES
    # =========================================================================
    num_steps = sim_data["num_steps"]
    frames = []

    for step in range(num_steps):
        v_mask = sim_data["is_visible"][:, step]
        h_mask = ~v_mask
        p_v = extract_geo_payload(step, v_mask, True)
        p_h = extract_geo_payload(step, h_mask, False)

        frame = go.Frame(
            data=[
                go.Scattergeo(
                    lat=p_v["lat"], lon=p_v["lon"],
                    text=p_v["text"], customdata=p_v["customdata"]
                ),
                go.Scattergeo(
                    lat=p_h["lat"], lon=p_h["lon"],
                    text=None, customdata=p_h["customdata"]
                )
            ],
            traces=[idx_vis, idx_hid],
            name=sim_data["time_labels"][step]
        )
        frames.append(frame)

    fig.frames = frames

    # =========================================================================
    # LAYOUT
    # =========================================================================
    updatemenus, sliders = build_animation_controls(frames, frame_duration_ms=70)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, b=30, t=10),
        uirevision="constant",
        geo=dict(
            projection_type="equirectangular",
            showland=True,
            landcolor="#0e1726",
            showocean=True,
            oceancolor="#040b17",
            showlakes=True,
            lakecolor="#040b17",
            showcountries=True,
            countrycolor="#1e293b",
            countrywidth=0.8,
            coastlinecolor="#334155",
            coastlinewidth=1.0,
            lataxis=dict(showgrid=True, gridcolor="rgba(56, 189, 248, 0.1)", range=[-75, 75], dtick=30),
            lonaxis=dict(showgrid=True, gridcolor="rgba(56, 189, 248, 0.1)", range=[-180, 180], dtick=60),
            bgcolor="rgba(0,0,0,0)"
        ),
        updatemenus=updatemenus,
        sliders=sliders,
        legend=dict(
            x=0.01, y=0.02,
            bgcolor="rgba(13, 20, 36, 0.8)",
            bordercolor="rgba(56, 189, 248, 0.3)",
            borderwidth=1,
            font=dict(size=11, color="#e2e8f0")
        ),
        height=580
    )

    return fig
