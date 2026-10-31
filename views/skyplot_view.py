"""
views/skyplot_view.py
=====================
Renders a topocentric Cartesian sky-plot (Azimuth vs. Elevation) as observed
from a ground receiver station (e.g., Multan, Pakistan).

ITEM 5 OVERHAUL — ZOOM & PAN FIX:
  - Replaced go.Scatterpolar with standard Cartesian go.Scatter:
      x = (90 - elevation) * sin(azimuth)
      y = (90 - elevation) * cos(azimuth)
  - Equal aspect ratio (yaxis scaleanchor="x", scaleratio=1).
  - Fixed axis ranges [-102, 102] with axes/ticks hidden.
  - Manually drawn concentric elevation rings at 0° (Horizon), 30°, 60°,
    and the user-configured elevation mask boundary.
  - 45° radial spokes and cardinal N/E/S/W labels.
  - Zoom, pan, and double-click reset behave identically to standard 2D plots.
  - Client-side Plotly animation (go.Frame) with redraw=False for instant 60 FPS playback.
"""

from typing import Dict, List, Optional
import numpy as np
import plotly.graph_objects as go
from views.globe_view_3d import build_animation_controls


def create_animated_skyplot_figure(
    sim_data: Dict,
    observer_name: str = "Multan, Pakistan"
) -> go.Figure:
    """
    Builds the Cartesian Sky Plot figure with native animation frames.
    """
    fig = go.Figure()
    mask_angle_deg = sim_data["mask_angle_deg"]

    # =========================================================================
    # STATIC TRACES (Elevation circles, radial spokes, cardinal labels)
    # =========================================================================
    theta = np.linspace(0, 2 * np.pi, 120)

    # 1. Concentric elevation circles (0°, 30°, 60°)
    for elev_val, color, dash, width in [
        (0.0, "rgba(74, 85, 104, 0.8)", "solid", 2.0),
        (30.0, "rgba(255, 255, 255, 0.14)", "dot", 1.0),
        (60.0, "rgba(255, 255, 255, 0.14)", "dot", 1.0),
    ]:
        r = 90.0 - elev_val
        fig.add_trace(go.Scatter(
            x=r * np.sin(theta),
            y=r * np.cos(theta),
            mode="lines",
            line=dict(color=color, dash=dash, width=width),
            hoverinfo="skip",
            showlegend=False
        ))

    # 2. Elevation Mask Circle (dashed magenta/neon red)
    r_mask = 90.0 - mask_angle_deg
    fig.add_trace(go.Scatter(
        x=r_mask * np.sin(theta),
        y=r_mask * np.cos(theta),
        mode="lines",
        line=dict(color="rgba(244, 63, 94, 0.85)", dash="dash", width=1.5),
        hoverinfo="skip",
        name=f"Mask Angle ({mask_angle_deg:.0f}°)"
    ))

    # 3. Radial Spoke Lines (Every 45 degrees: 0, 45, 90, 135, 180, 225, 270, 315)
    for az_deg in range(0, 360, 45):
        rad = np.radians(az_deg)
        fig.add_trace(go.Scatter(
            x=[0, 90.0 * np.sin(rad)],
            y=[0, 90.0 * np.cos(rad)],
            mode="lines",
            line=dict(color="rgba(56, 189, 248, 0.12)", width=1),
            hoverinfo="skip",
            showlegend=False
        ))

    # 4. Cardinal & Intercardinal Direction Labels
    cardinal_markers = [
        ("N (0°)", 0, 97),
        ("NE", 67, 67),
        ("E (90°)", 97, 0),
        ("SE", 67, -67),
        ("S (180°)", 0, -97),
        ("SW", -67, -67),
        ("W (270°)", -97, 0),
        ("NW", -67, 67),
    ]
    fig.add_trace(go.Scatter(
        x=[m[1] for m in cardinal_markers],
        y=[m[2] for m in cardinal_markers],
        mode="text",
        text=[m[0] for m in cardinal_markers],
        textfont=dict(color="#cbd5e1", size=10, family="Orbitron, monospace"),
        hoverinfo="skip",
        showlegend=False
    ))

    # 5. Elevation Ring Labels (Zenith, 60°, 30°, 0°)
    ring_labels = [
        ("Zenith (90°)", 0, 4),
        ("60°", 0, 34),
        ("30°", 0, 64),
        ("Horizon (0°)", 0, 92),
    ]
    fig.add_trace(go.Scatter(
        x=[rl[1] for rl in ring_labels],
        y=[rl[2] for rl in ring_labels],
        mode="text",
        text=[rl[0] for rl in ring_labels],
        textfont=dict(color="rgba(148, 163, 184, 0.65)", size=9, family="Inter, sans-serif"),
        hoverinfo="skip",
        showlegend=False
    ))

    # =========================================================================
    # DYNAMIC SATELLITE TRACES
    # =========================================================================
    idx_acq = len(fig.data)
    idx_low = idx_acq + 1

    t0 = 0
    el_0 = sim_data["el"][:, t0]
    acq_mask_0 = (el_0 >= mask_angle_deg)
    low_mask_0 = (el_0 >= 0.0) & (el_0 < mask_angle_deg)
    # Satellite metadata for fast hover string generation
    sats_meta = sim_data["satellites"]
    names = [s["display_name"] for s in sats_meta]
    norads = [str(s["norad_id"]) for s in sats_meta]
    blocks = [s["block_type"] for s in sats_meta]
    prn_labels = [
        f"PRN {s['prn']:02d}" if s["prn"] is not None else s["display_name"]
        for s in sats_meta
    ]

    def build_sky_payload(step: int, mask: np.ndarray, is_acq: bool):
        indices = np.where(mask)[0]
        if len(indices) == 0:
            return dict(x=[], y=[], text=[], hovertext=[])

        x_vals = sim_data["cart_x"][indices, step].tolist()
        y_vals = sim_data["cart_y"][indices, step].tolist()
        texts = [prn_labels[i] for i in indices]

        status_str = "Acquirable (El ≥ mask)" if is_acq else "Low Elevation (< mask)"
        hover_list = [
            (
                f"<b>{names[i]}</b> (NORAD {norads[i]})<br>"
                f"Elevation: <b>{float(sim_data['el'][i, step]):.1f}°</b><br>"
                f"Azimuth: <b>{float(sim_data['az'][i, step]):.1f}°</b><br>"
                f"Slant Range: {float(sim_data['dist_km'][i, step]):,.0f} km<br>"
                f"Block: {blocks[i]}<br>"
                f"Signal: <b>{status_str}</b>"
            )
            for i in indices
        ]
        return dict(x=x_vals, y=y_vals, text=texts, hovertext=hover_list)

    p0_acq = build_sky_payload(t0, acq_mask_0, True)
    p0_low = build_sky_payload(t0, low_mask_0, False)

    # Acquirable satellites (Neon green, high visibility)
    fig.add_trace(go.Scatter(
        x=p0_acq["x"], y=p0_acq["y"],
        mode="markers+text",
        marker=dict(size=14, color="#00ff88", symbol="circle", line=dict(color="#000000", width=1.5)),
        text=p0_acq["text"],
        textposition="top center",
        textfont=dict(color="#ffffff", size=9, family="Orbitron, monospace"),
        hovertext=p0_acq["hovertext"],
        hoverinfo="text",
        name=f"Acquirable (El ≥ {mask_angle_deg:.0f}°)"
    ))

    # Low-elevation satellites (Amber, open circle)
    fig.add_trace(go.Scatter(
        x=p0_low["x"], y=p0_low["y"],
        mode="markers+text",
        marker=dict(size=11, color="#ffa200", symbol="circle-open", line=dict(color="#ffa200", width=1.5)),
        text=p0_low["text"],
        textposition="top center",
        textfont=dict(color="#e2e8f0", size=8, family="monospace"),
        hovertext=p0_low["hovertext"],
        hoverinfo="text",
        name=f"Low Elevation (0° ≤ El < {mask_angle_deg:.0f}°)"
    ))

    # =========================================================================
    # BUILD FRAMES
    # =========================================================================
    num_steps = sim_data["num_steps"]
    frames = []

    for step in range(num_steps):
        el_step = sim_data["el"][:, step]
        a_mask = (el_step >= mask_angle_deg)
        l_mask = (el_step >= 0.0) & (el_step < mask_angle_deg)
        p_a = build_sky_payload(step, a_mask, True)
        p_l = build_sky_payload(step, l_mask, False)

        frame = go.Frame(
            data=[
                go.Scatter(
                    x=p_a["x"], y=p_a["y"],
                    text=p_a["text"], hovertext=p_a["hovertext"], hoverinfo="text"
                ),
                go.Scatter(
                    x=p_l["x"], y=p_l["y"],
                    text=p_l["text"], hovertext=p_l["hovertext"], hoverinfo="text"
                )
            ],
            traces=[idx_acq, idx_low],
            name=sim_data["time_labels"][step]
        )
        frames.append(frame)

    fig.frames = frames

    # =========================================================================
    # LAYOUT: Equal aspect ratio, hidden Cartesian axes, embedded controls
    # =========================================================================
    updatemenus, sliders = build_animation_controls(frames, frame_duration_ms=65)

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, b=30, t=20),
        uirevision="constant",
        xaxis=dict(
            range=[-104, 104],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            fixedrange=False
        ),
        yaxis=dict(
            range=[-104, 104],
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            scaleanchor="x",
            scaleratio=1,
            fixedrange=False
        ),
        updatemenus=updatemenus,
        sliders=sliders,
        legend=dict(
            x=0.02, y=0.98,
            bgcolor="rgba(13, 20, 36, 0.8)",
            bordercolor="rgba(56, 189, 248, 0.3)",
            borderwidth=1,
            font=dict(size=11, color="#e2e8f0")
        ),
        height=620
    )

    return fig
