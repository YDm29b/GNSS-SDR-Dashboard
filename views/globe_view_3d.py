"""
views/globe_view_3d.py
======================
Renders an interactive 3D Earth globe with the operational GPS satellite
constellation plotted in their Medium Earth Orbit (MEO) shells.

Features:
  - 3D WGS84 Earth representation (radius ~6378 km) with coordinate grid.
  - GPS satellites positioned at their real-time ECEF Cartesian coordinates (r ~26,560 km).
  - Satellites highlighted by visibility from the ground observer (e.g. Multan).
  - Hover tooltips showing PRN, NORAD ID, Altitude, Subpoint, and Topocentric Az/El.
  - 3D orbital plane guide rings showing the 55° inclined constellation architecture.
"""

from typing import List, Dict
import numpy as np
import plotly.graph_objects as go
from core.orbit_engine import WGS84_EARTH_RADIUS_KM


def create_earth_sphere_mesh(radius_km: float = WGS84_EARTH_RADIUS_KM, resolution: int = 36):
    """
    Generates a 3D spherical mesh grid for the Earth surface.
    """
    phi = np.linspace(-np.pi / 2, np.pi / 2, resolution)
    theta = np.linspace(-np.pi, np.pi, resolution * 2)
    phi, theta = np.meshgrid(phi, theta)

    x = radius_km * np.cos(phi) * np.cos(theta)
    y = radius_km * np.cos(phi) * np.sin(theta)
    z = radius_km * np.sin(phi)
    return x, y, z


def create_globe_3d_figure(
    satellites_data: List[Dict],
    observer_lat: float,
    observer_lon: float,
    observer_name: str = "Multan, Pakistan",
    show_orbital_rings: bool = True
) -> go.Figure:
    """
    Builds the Plotly 3D Figure depicting the Earth globe and satellite constellation.
    """
    fig = go.Figure()

    # 1. Earth Sphere Surface
    x_e, y_e, z_e = create_earth_sphere_mesh(WGS84_EARTH_RADIUS_KM, resolution=32)
    fig.add_trace(go.Surface(
        x=x_e,
        y=y_e,
        z=z_e,
        colorscale=[
            [0.0, "#081b26"],
            [0.3, "#0d2b45"],
            [0.7, "#14365d"],
            [1.0, "#1f487e"]
        ],
        showscale=False,
        hoverinfo="none",
        opacity=0.88,
        name="Earth (WGS84)"
    ))

    # 2. Equator Ring on Earth (Latitude = 0°)
    eq_theta = np.linspace(-np.pi, np.pi, 120)
    eq_x = WGS84_EARTH_RADIUS_KM * np.cos(eq_theta)
    eq_y = WGS84_EARTH_RADIUS_KM * np.sin(eq_theta)
    eq_z = np.zeros_like(eq_theta)
    fig.add_trace(go.Scatter3d(
        x=eq_x, y=eq_y, z=eq_z,
        mode="lines",
        line=dict(color="rgba(0, 200, 255, 0.45)", width=2),
        hoverinfo="none",
        name="Equator"
    ))

    # 3. Observer Location on Earth Surface
    obs_lat_rad = np.radians(observer_lat)
    obs_lon_rad = np.radians(observer_lon)
    obs_x = (WGS84_EARTH_RADIUS_KM + 150) * np.cos(obs_lat_rad) * np.cos(obs_lon_rad)
    obs_y = (WGS84_EARTH_RADIUS_KM + 150) * np.cos(obs_lat_rad) * np.sin(obs_lon_rad)
    obs_z = (WGS84_EARTH_RADIUS_KM + 150) * np.sin(obs_lat_rad)

    fig.add_trace(go.Scatter3d(
        x=[obs_x], y=[obs_y], z=[obs_z],
        mode="markers+text",
        marker=dict(size=7, color="#ff0055", symbol="circle"),
        text=[f"  📍 {observer_name}"],
        textposition="top center",
        textfont=dict(color="#ffffff", size=11),
        hovertext=(
            f"<b>Observer Station: {observer_name}</b><br>"
            f"Lat: {observer_lat:.4f}° | Lon: {observer_lon:.4f}°"
        ),
        hoverinfo="text",
        name=f"Observer ({observer_name})"
    ))

    # 4. Optional: GPS Constellation Orbital Shell Guide Rings (55° Inclination)
    if show_orbital_rings:
        r_orbit = 26560.0  # nominal GPS semi-major axis in km
        inc = np.radians(55.0)
        # 6 nominal planes separated by 60° in RAAN
        for plane_idx, raan_deg in enumerate(range(0, 360, 60)):
            raan = np.radians(raan_deg)
            u = np.linspace(0, 2 * np.pi, 90)
            # Standard orbital plane coordinates
            x_orb = r_orbit * (np.cos(raan) * np.cos(u) - np.sin(raan) * np.sin(u) * np.cos(inc))
            y_orb = r_orbit * (np.sin(raan) * np.cos(u) + np.cos(raan) * np.sin(u) * np.cos(inc))
            z_orb = r_orbit * (np.sin(u) * np.sin(inc))

            fig.add_trace(go.Scatter3d(
                x=x_orb, y=y_orb, z=z_orb,
                mode="lines",
                line=dict(color="rgba(100, 180, 255, 0.18)", width=1.5, dash="dot"),
                hoverinfo="none",
                showlegend=(plane_idx == 0),
                name="GPS Orbital Planes (55° Inc)"
            ))

    # 5. GPS Satellites: Partition into Visible vs Below Horizon
    visible_sats = [s for s in satellites_data if s["is_visible"]]
    hidden_sats = [s for s in satellites_data if not s["is_visible"]]

    for sat_group, label, color, symbol, size, is_vis in [
        (visible_sats, "Visible to Observer (El ≥ 5°)", "#00ff88", "diamond", 7, True),
        (hidden_sats, "Below Horizon", "#ffa200", "circle", 5, False)
    ]:
        if not sat_group:
            continue

        x_vals = [s["x_ecef"] for s in sat_group]
        y_vals = [s["y_ecef"] for s in sat_group]
        z_vals = [s["z_ecef"] for s in sat_group]
        texts = [s["display_name"] for s in sat_group]

        custom_data = [
            (
                s["display_name"],
                s["norad_id"],
                s["block_type"],
                s["altitude_km"],
                s["latitude"],
                s["longitude"],
                s["azimuth_deg"],
                s["elevation_deg"],
                "Visible (Acquisition Zone)" if s["is_visible"] else "Below Horizon"
            )
            for s in sat_group
        ]

        hover_template = (
            "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
            "Block: %{customdata[2]}<br>"
            "Altitude: %{customdata[3]:,.0f} km<br>"
            "Sub-point: Lat %{customdata[4]:.2f}°, Lon %{customdata[5]:.2f}°<br>"
            "Azimuth: %{customdata[6]:.1f}° | Elevation: %{customdata[7]:.1f}°<br>"
            "Status: <b>%{customdata[8]}</b>"
            "<extra></extra>"
        )

        fig.add_trace(go.Scatter3d(
            x=x_vals, y=y_vals, z=z_vals,
            mode="markers+text",
            marker=dict(
                size=size,
                color=color,
                symbol=symbol,
                line=dict(color="#ffffff", width=1)
            ),
            text=texts if is_vis else None,
            textposition="top center",
            textfont=dict(color="#00ff88" if is_vis else "#888888", size=9),
            customdata=custom_data,
            hovertemplate=hover_template,
            name=f"{label} ({len(sat_group)})"
        ))

    # Configure 3D Camera and Layout
    axis_config = dict(
        showbackground=False,
        showgrid=True,
        gridcolor="rgba(255, 255, 255, 0.08)",
        zeroline=False,
        showticklabels=False,
        title=""
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0c1017",
        plot_bgcolor="#0c1017",
        margin=dict(l=0, r=0, b=0, t=30),
        scene=dict(
            xaxis=axis_config,
            yaxis=axis_config,
            zaxis=axis_config,
            aspectmode="cube",
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.2),
                up=dict(x=0, y=0, z=1)
            )
        ),
        legend=dict(
            x=0.02, y=0.98,
            bgcolor="rgba(12, 16, 23, 0.75)",
            bordercolor="rgba(255, 255, 255, 0.15)",
            borderwidth=1,
            font=dict(size=11)
        ),
        height=620
    )

    return fig
