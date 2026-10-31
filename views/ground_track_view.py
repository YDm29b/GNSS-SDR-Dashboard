"""
views/ground_track_view.py
==========================
Renders a 2D global ground-track projection of the GPS constellation.
Visualizes sub-satellite points (intersections of the satellite vector with
the WGS84 Earth ellipsoid) and orbital ground track curves over time.

Physics Context:
  - GPS orbital inclination is 55.0 degrees. Consequently, ground tracks
    oscillate between latitudes of +55° (North) and -55° (South).
  - The semi-synchronous period (~11h 58m) creates repeating ground tracks
    that shift slightly each day due to Earth's sidereal rotation.
"""

from typing import List, Dict, Optional
import plotly.graph_objects as go


def create_ground_track_figure(
    satellites_data: List[Dict],
    observer_lat: float,
    observer_lon: float,
    observer_name: str = "Multan, Pakistan",
    ground_tracks: Optional[Dict[str, Dict]] = None,
    show_tracks: bool = True
) -> go.Figure:
    """
    Builds the Plotly 2D Scattergeo world ground-track map.
    """
    fig = go.Figure()

    # 1. Plot Orbital Ground Track Curves (12-hour period trails)
    if show_tracks and ground_tracks:
        for sat_name, track_data in ground_tracks.items():
            lats = track_data["lats"]
            lons = track_data["lons"]
            fig.add_trace(go.Scattergeo(
                lat=lats,
                lon=lons,
                mode="lines",
                line=dict(width=1.0, color="rgba(70, 160, 240, 0.3)"),
                hoverinfo="none",
                showlegend=False,
                name=f"{sat_name} Orbit Trail"
            ))

    # 2. Observer Ground Station Pin
    fig.add_trace(go.Scattergeo(
        lat=[observer_lat],
        lon=[observer_lon],
        mode="markers+text",
        marker=dict(
            size=11,
            color="#ff0055",
            symbol="star",
            line=dict(width=1.5, color="#ffffff")
        ),
        text=[f" 📍 {observer_name}"],
        textposition="top right",
        textfont=dict(color="#ffffff", size=12, family="sans-serif"),
        hovertext=(
            f"<b>Ground Station: {observer_name}</b><br>"
            f"Latitude: {observer_lat:.4f}° N<br>"
            f"Longitude: {observer_lon:.4f}° E"
        ),
        hoverinfo="text",
        name=f"Observer ({observer_name})"
    ))

    # 3. Partition Satellites into Visible vs Horizon-Masked
    visible_sats = [s for s in satellites_data if s["is_visible"]]
    hidden_sats = [s for s in satellites_data if not s["is_visible"]]

    for sat_group, label, color, symbol, size, is_vis in [
        (visible_sats, "Visible Overhead (El ≥ 5°)", "#00ff88", "diamond", 9, True),
        (hidden_sats, "Below Horizon", "#ffa200", "circle", 6, False)
    ]:
        if not sat_group:
            continue

        lats = [s["latitude"] for s in sat_group]
        lons = [s["longitude"] for s in sat_group]
        labels = [s["display_name"] for s in sat_group]

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
            "Sub-point: Lat %{customdata[4]:.2f}°, Lon %{customdata[5]:.2f}°<br>"
            "Altitude: %{customdata[3]:,.0f} km<br>"
            "Azimuth: %{customdata[6]:.1f}° | Elevation: %{customdata[7]:.1f}°<br>"
            "Status: <b>%{customdata[8]}</b>"
            "<extra></extra>"
        )

        fig.add_trace(go.Scattergeo(
            lat=lats,
            lon=lons,
            mode="markers+text",
            marker=dict(
                size=size,
                color=color,
                symbol=symbol,
                line=dict(color="#ffffff", width=1)
            ),
            text=labels if is_vis else None,
            textposition="top center",
            textfont=dict(color="#00ff88" if is_vis else "#888888", size=10),
            customdata=custom_data,
            hovertemplate=hover_template,
            name=f"{label} ({len(sat_group)})"
        ))

    # Configure Geo Layout
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0c1017",
        plot_bgcolor="#0c1017",
        margin=dict(l=0, r=0, b=0, t=25),
        geo=dict(
            projection_type="equirectangular",
            showland=True,
            landcolor="#182230",
            showocean=True,
            oceancolor="#0c131d",
            showlakes=True,
            lakecolor="#0c131d",
            showcountries=True,
            countrycolor="#2e3e52",
            countrywidth=0.8,
            coastlinecolor="#3d526d",
            coastlinewidth=1.0,
            showgrid=True,
            gridcolor="rgba(255, 255, 255, 0.08)",
            lataxis=dict(range=[-75, 75], dtick=30),
            lonaxis=dict(range=[-180, 180], dtick=60),
            bgcolor="#0c1017"
        ),
        legend=dict(
            x=0.01, y=0.02,
            bgcolor="rgba(12, 16, 23, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.15)",
            borderwidth=1,
            font=dict(size=11)
        ),
        height=540
    )

    return fig
