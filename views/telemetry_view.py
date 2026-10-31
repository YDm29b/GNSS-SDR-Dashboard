"""
views/telemetry_view.py
=======================
Renders Glassmorphism KPI metrics cards and the interactive constellation
telemetry table for GPS signal acquisition and navigation analysis.
Optimized to read directly from precomputed NumPy simulation arrays.
"""

from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import streamlit as st


def render_glass_metrics(sim_data: Dict, step_idx: int = 0):
    """
    Renders 4 high-contrast Glassmorphism KPI metric cards (Item 6).
    """
    mask_angle_deg = sim_data["mask_angle_deg"]
    num_sats = sim_data["num_sats"]
    el_vals = sim_data["el"][:, step_idx]
    sats_meta = sim_data["satellites"]

    vis_mask = el_vals >= mask_angle_deg
    num_visible = int(np.sum(vis_mask))

    # Identify zenith peak satellite
    zenith_sat_name = "None"
    zenith_el = 0.0
    if num_visible > 0:
        vis_indices = np.where(vis_mask)[0]
        best_i = vis_indices[np.argmax(el_vals[vis_indices])]
        zenith_sat_name = sats_meta[best_i]["display_name"]
        zenith_el = float(el_vals[best_i])

    time_label = sim_data["time_labels"][step_idx]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="glass-card">
            <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; letter-spacing: 0.05em;">
                Total Constellation
            </div>
            <div style="font-family: 'Orbitron', monospace; font-size: 1.8rem; font-weight: 700; color: #38bdf8; margin: 4px 0;">
                {num_sats} Sats
            </div>
            <div style="font-size: 0.8rem; color: #00ff88;">
                ● Active Operational MEO
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        pvt_color = "#00ff88" if num_visible >= 4 else "#f43f5e"
        pvt_text = f"+{num_visible - 4} above PVT min (4 required)" if num_visible >= 4 else "Insufficient for 3D fix (<4)"
        st.markdown(f"""
        <div class="glass-card">
            <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; letter-spacing: 0.05em;">
                Acquirable (El ≥ {mask_angle_deg:.0f}°)
            </div>
            <div style="font-family: 'Orbitron', monospace; font-size: 1.8rem; font-weight: 700; color: #00ff88; margin: 4px 0;">
                {num_visible} Visible
            </div>
            <div style="font-size: 0.8rem; color: {pvt_color};">
                {pvt_text}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="glass-card">
            <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; letter-spacing: 0.05em;">
                Zenith Peak Satellite
            </div>
            <div style="font-family: 'Orbitron', monospace; font-size: 1.8rem; font-weight: 700; color: #c084fc; margin: 4px 0;">
                {zenith_sat_name}
            </div>
            <div style="font-size: 0.8rem; color: #38bdf8;">
                Elevation: {zenith_el:.1f}°
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="glass-card">
            <div style="font-size: 0.78rem; text-transform: uppercase; color: #94a3b8; font-weight: 600; letter-spacing: 0.05em;">
                Orbit Shell / Altitude
            </div>
            <div style="font-family: 'Orbitron', monospace; font-size: 1.8rem; font-weight: 700; color: #f59e0b; margin: 4px 0;">
                ~20,200 km
            </div>
            <div style="font-size: 0.8rem; color: #94a3b8;">
                Period: 11h 58m (e &lt; 0.02)
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_telemetry_table_from_sim(sim_data: Dict, step_idx: int = 0):
    """
    Renders an interactive DataFrame from precomputed NumPy simulation arrays.
    Runs in < 1ms with zero propagation overhead (Item 7).
    """
    mask_angle_deg = sim_data["mask_angle_deg"]
    sats_meta = sim_data["satellites"]
    num_sats = sim_data["num_sats"]

    rows = []
    for i in range(num_sats):
        el_val = float(sim_data["el"][i, step_idx])
        is_acq = el_val >= mask_angle_deg
        status_label = "🟢 Visible / Acquirable" if is_acq else ("🟡 Low Elevation" if el_val >= 0 else "⚪ Below Horizon")

        rows.append({
            "PRN": sats_meta[i]["prn"] if sats_meta[i]["prn"] is not None else 999,
            "Identifier": sats_meta[i]["display_name"],
            "NORAD ID": sats_meta[i]["norad_id"],
            "Block Type": sats_meta[i]["block_type"],
            "Signal Status": status_label,
            "Elevation (°)": round(el_val, 1),
            "Azimuth (°)": round(float(sim_data["az"][i, step_idx]), 1),
            "Slant Range (km)": f"{float(sim_data['dist_km'][i, step_idx]):,.0f}",
            "Sub-Lat (°)": round(float(sim_data["lat"][i, step_idx]), 2),
            "Sub-Lon (°)": round(float(sim_data["lon"][i, step_idx]), 2),
            "Altitude (km)": f"{float(sim_data['alt_km'][i, step_idx]):,.0f}",
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["Elevation (°)"], ascending=False).reset_index(drop=True)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PRN": st.column_config.NumberColumn("PRN", format="%02d", width="small"),
            "Signal Status": st.column_config.TextColumn("Signal Status", width="medium"),
            "Elevation (°)": st.column_config.ProgressColumn(
                "Elevation (°)",
                min_value=-90,
                max_value=90,
                format="%.1f°"
            ),
        }
    )


def render_telemetry_metrics(satellites_data: List[Dict], mask_angle_deg: float):
    """
    Backwards compatibility helper for existing test suites.
    """
    total_sats = len(satellites_data)
    visible_sats = [s for s in satellites_data if s["elevation_deg"] >= mask_angle_deg]
    num_visible = len(visible_sats)
    highest_sat = max(visible_sats, key=lambda s: s["elevation_deg"]) if visible_sats else None

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="Total Constellation Satellites", value=f"{total_sats} Sats")
    with col2:
        st.metric(label=f"Acquirable (El ≥ {mask_angle_deg:.0f}°)", value=f"{num_visible} Visible")
    with col3:
        st.metric(label="Zenith Peak Satellite", value=f"{highest_sat['display_name']}" if highest_sat else "None")
    with col4:
        st.metric(label="Orbital Shell Altitude", value="~20,200 km")


def render_telemetry_table(satellites_data: List[Dict], mask_angle_deg: float):
    """
    Backwards compatibility helper for existing test suites.
    """
    rows = []
    for s in satellites_data:
        is_acq = s["elevation_deg"] >= mask_angle_deg
        status_label = "🟢 Visible / Acquirable" if is_acq else ("🟡 Low Elevation" if s["elevation_deg"] >= 0 else "⚪ Below Horizon")
        rows.append({
            "PRN": s["prn"] if s["prn"] is not None else 999,
            "Identifier": s["display_name"],
            "NORAD ID": s["norad_id"],
            "Block Type": s["block_type"],
            "Status": status_label,
            "Elevation (°)": round(s["elevation_deg"], 1),
            "Azimuth (°)": round(s["azimuth_deg"], 1),
            "Slant Range (km)": f"{s['slant_range_km']:,.0f}",
            "Sub-Lat (°)": round(s["latitude"], 2),
            "Sub-Lon (°)": round(s["longitude"], 2),
            "Altitude (km)": f"{s['altitude_km']:,.0f}",
        })
    df = pd.DataFrame(rows).sort_values(by=["Elevation (°)"], ascending=False).reset_index(drop=True)
    st.dataframe(df, use_container_width=True, hide_index=True)
