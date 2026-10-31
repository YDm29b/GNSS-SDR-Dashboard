"""
views/skyplot_view.py
=====================
Renders a topocentric polar sky-plot (Azimuth vs. Elevation) as observed
from a ground receiver station (e.g., Multan, Pakistan).

Significance for GPS SDR Receivers (Supervisor Defense Context):
  - In GNSS signal acquisition, the 2D search space spans PRN code phase
    (1023 half-chips) and Doppler frequency shift (+/- 5 kHz).
  - Acquiring 32 satellites blind requires enormous FFT / correlation resources.
  - A sky-plot predicts exactly which PRNs are overhead, pruning the search space
    to only the ~8-12 visible satellites and estimating Doppler offsets.
  - The elevation mask (typically 5° or 10°) excludes satellites suffering from
    severe tropospheric delays, ground obstruction, and multipath reflections.
"""

from typing import List, Dict
import numpy as np
import plotly.graph_objects as go


def create_skyplot_figure(
    satellites_data: List[Dict],
    observer_name: str = "Multan, Pakistan",
    mask_angle_deg: float = 5.0
) -> go.Figure:
    """
    Builds a standard GNSS polar sky-plot.
    - Radial distance: 90° - Elevation (Center = Zenith 90°, Outer Ring = Horizon 0°).
    - Angular theta: Azimuth (0° North, 90° East, 180° South, 270° West).
    """
    fig = go.Figure()

    # 1. Outer Horizon Circle (Elevation = 0°) -> Radial = 90
    theta_circle = np.linspace(0, 360, 180)
    fig.add_trace(go.Scatterpolar(
        r=[90] * len(theta_circle),
        theta=theta_circle,
        mode="lines",
        line=dict(color="#4a5568", width=1.5),
        hoverinfo="none",
        showlegend=False
    ))

    # 2. Elevation Mask Circle (e.g. 5° or 10°) -> Radial = 90 - mask_angle
    mask_r = 90.0 - mask_angle_deg
    fig.add_trace(go.Scatterpolar(
        r=[mask_r] * len(theta_circle),
        theta=theta_circle,
        mode="lines",
        line=dict(color="rgba(255, 75, 75, 0.6)", width=1.5, dash="dash"),
        hoverinfo="none",
        name=f"Mask Angle ({mask_angle_deg:.0f}°)"
    ))

    # 3. Intermediate Elevation Reference Rings (30°, 60°)
    for elev_ref in [30, 60]:
        r_ref = 90.0 - elev_ref
        fig.add_trace(go.Scatterpolar(
            r=[r_ref] * len(theta_circle),
            theta=theta_circle,
            mode="lines",
            line=dict(color="rgba(255, 255, 255, 0.12)", width=1, dash="dot"),
            hoverinfo="none",
            showlegend=False
        ))

    # 4. Filter Satellites Above Horizon (Elevation > 0°)
    visible_sats = [s for s in satellites_data if s["elevation_deg"] >= 0.0]

    # Partition into Acquired (above mask) vs Degraded (between 0° and mask)
    acquired_sats = [s for s in visible_sats if s["elevation_deg"] >= mask_angle_deg]
    masked_sats = [s for s in visible_sats if s["elevation_deg"] < mask_angle_deg]

    for sat_group, label, color, size, symbol in [
        (acquired_sats, f"Acquirable (El ≥ {mask_angle_deg:.0f}°)", "#00ff88", 16, "circle"),
        (masked_sats, f"Degraded (0° ≤ El < {mask_angle_deg:.0f}°)", "#ffaa00", 12, "circle-open")
    ]:
        if not sat_group:
            continue

        r_vals = [90.0 - s["elevation_deg"] for s in sat_group]
        theta_vals = [s["azimuth_deg"] for s in sat_group]
        labels = [f"PRN {s['prn']:02d}" if s["prn"] is not None else s["display_name"] for s in sat_group]
        
        custom_data = [
            (
                s["display_name"],
                s["norad_id"],
                s["block_type"],
                s["elevation_deg"],
                s["azimuth_deg"],
                s["slant_range_km"],
                "Acquirable" if s["elevation_deg"] >= mask_angle_deg else "Masked / Low El"
            )
            for s in sat_group
        ]

        hover_template = (
            "<b>%{customdata[0]}</b> (NORAD %{customdata[1]})<br>"
            "Elevation: <b>%{customdata[3]:.1f}°</b><br>"
            "Azimuth: <b>%{customdata[4]:.1f}°</b><br>"
            "Slant Range: %{customdata[5]:,.0f} km<br>"
            "Block: %{customdata[2]}<br>"
            "Status: %{customdata[6]}"
            "<extra></extra>"
        )

        fig.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=theta_vals,
            mode="markers+text",
            marker=dict(
                size=size,
                color=color,
                symbol=symbol,
                line=dict(color="#000000", width=1.5)
            ),
            text=labels,
            textposition="top center",
            textfont=dict(color="#ffffff", size=10, family="monospace"),
            customdata=custom_data,
            hovertemplate=hover_template,
            name=f"{label} ({len(sat_group)})"
        ))

    # Polar Layout Configuration
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0c1017",
        plot_bgcolor="#0c1017",
        margin=dict(l=30, r=30, b=30, t=40),
        title=dict(
            text=f"Sky-Plot from {observer_name} — Active In-View Satellites: {len(acquired_sats)}",
            x=0.5,
            xanchor="center",
            font=dict(size=14, color="#e2e8f0")
        ),
        polar=dict(
            bgcolor="#0e1726",
            radialaxis=dict(
                visible=True,
                range=[0, 90],
                tickvals=[0, 30, 60, 90],
                ticktext=["Zenith (90°)", "60°", "30°", "0° (Horizon)"],
                angle=90,
                tickfont=dict(size=10, color="#94a3b8"),
                gridcolor="rgba(255, 255, 255, 0.12)",
                linecolor="rgba(255, 255, 255, 0.15)"
            ),
            angularaxis=dict(
                direction="clockwise",
                rotation=90,  # 0° (North) placed at top
                period=360,
                tickmode="array",
                tickvals=[0, 45, 90, 135, 180, 225, 270, 315],
                ticktext=["N (0°)", "NE", "E (90°)", "SE", "S (180°)", "SW", "W (270°)", "NW"],
                tickfont=dict(size=11, color="#cbd5e1"),
                gridcolor="rgba(255, 255, 255, 0.12)",
                linecolor="rgba(255, 255, 255, 0.2)"
            )
        ),
        legend=dict(
            x=0.0, y=-0.15,
            orientation="h",
            bgcolor="rgba(12, 16, 23, 0.8)",
            bordercolor="rgba(255, 255, 255, 0.15)",
            borderwidth=1,
            font=dict(size=11)
        ),
        height=540
    )

    return fig
