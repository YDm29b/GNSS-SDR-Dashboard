"""
views/telemetry_view.py
=======================
Renders KPI metrics cards and the interactive constellation telemetry
table for GPS signal acquisition and navigation analysis.
"""

from typing import List, Dict
import pandas as pd
import streamlit as st


def render_telemetry_metrics(satellites_data: List[Dict], mask_angle_deg: float):
    """
    Renders key performance indicators (KPIs) for the constellation state.
    """
    total_sats = len(satellites_data)
    visible_sats = [s for s in satellites_data if s["elevation_deg"] >= mask_angle_deg]
    num_visible = len(visible_sats)

    highest_sat = None
    if visible_sats:
        highest_sat = max(visible_sats, key=lambda s: s["elevation_deg"])

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Total Constellation Satellites",
            value=f"{total_sats} Sats",
            help="Active operational GPS space vehicles currently tracked in CelesTrak TLE."
        )

    with col2:
        st.metric(
            label=f"Acquirable (El ≥ {mask_angle_deg:.0f}°)",
            value=f"{num_visible} Visible",
            delta=f"{num_visible - 4} above PVT min (4 required)" if num_visible >= 4 else "Insufficient for 3D fix (<4)",
            delta_color="normal" if num_visible >= 4 else "inverse",
            help="Minimum 4 satellites needed to solve for 3D position (X, Y, Z) and receiver clock bias (dt)."
        )

    with col3:
        if highest_sat:
            st.metric(
                label="Zenith Peak Satellite",
                value=f"{highest_sat['display_name']}",
                delta=f"El: {highest_sat['elevation_deg']:.1f}°",
                help="Satellite nearest to zenith provides the strongest signal and minimal atmospheric delay."
            )
        else:
            st.metric(label="Zenith Peak Satellite", value="None")

    with col4:
        st.metric(
            label="Orbital Shell Altitude",
            value="~20,200 km",
            delta="MEO Circular (e < 0.02)",
            delta_color="off",
            help="Semi-major axis ~26,560 km; orbital period ~11h 58m (half a sidereal day)."
        )


def render_telemetry_table(satellites_data: List[Dict], mask_angle_deg: float):
    """
    Renders an interactive DataFrame containing real-time ephemeris metrics.
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

    df = pd.DataFrame(rows)
    # Sort with visible satellites at the top, ordered descending by elevation
    df = df.sort_values(by=["Elevation (°)"], ascending=False).reset_index(drop=True)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "PRN": st.column_config.NumberColumn("PRN", format="%02d", width="small"),
            "Status": st.column_config.TextColumn("Signal Status", width="medium"),
            "Elevation (°)": st.column_config.ProgressColumn(
                "Elevation (°)",
                min_value=-90,
                max_value=90,
                format="%.1f°"
            ),
        }
    )
