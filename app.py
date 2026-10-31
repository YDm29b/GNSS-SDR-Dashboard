"""
app.py
======
Main application script for the GPS Constellation & Orbital Propagation Dashboard.
Physics Final Year Project (FYP) — Stages 1 & 2.

Features:
  - Stage 1: Current GPS constellation 3D globe, 2D ground track, and Multan sky-plot.
  - Stage 2: Time simulation / playback over a complete GPS orbital period (~12 hours).
  - Robust offline fallback using local CelesTrak TLE backup.
  - Detailed physical and mathematical annotations for supervisor project defense.
"""

import os
import time
from datetime import datetime, timezone, timedelta
import streamlit as st

# Configure page layout and title
st.set_page_config(
    page_title="GPS Constellation & Orbital Dashboard | FYP",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS styling for an aerospace dark aesthetic
st.markdown("""
<style>
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #94a3b8;
        margin-bottom: 1.2rem;
    }
    .status-badge {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 6px;
        padding: 6px 12px;
        display: inline-block;
        font-size: 0.85rem;
        color: #38bdf8;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        background-color: #0f172a;
        border-radius: 6px;
        color: #94a3b8;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1e293b !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #38bdf8 !important;
    }
</style>
""", unsafe_allow_html=True)

from core.tle_loader import fetch_or_load_tle, parse_gps_satellites
from core.orbit_engine import OrbitEngine, DEFAULT_OBSERVER_LAT, DEFAULT_OBSERVER_LON, DEFAULT_OBSERVER_ELEV_M
from views.globe_view_3d import create_globe_3d_figure
from views.ground_track_view import create_ground_track_figure
from views.skyplot_view import create_skyplot_figure
from views.telemetry_view import render_telemetry_metrics, render_telemetry_table


# ==============================================================================
# 1. State Management & Initialization
# ==============================================================================

if "sim_minutes" not in st.session_state:
    st.session_state.sim_minutes = 0.0

if "is_playing" not in st.session_state:
    st.session_state.is_playing = False

if "base_time" not in st.session_state:
    st.session_state.base_time = datetime.now(timezone.utc)


# ==============================================================================
# 2. Sidebar Controls
# ==============================================================================

with st.sidebar:
    st.markdown("### 🛰️ Constellation Controls")

    # Observer Presets
    st.markdown("#### 📍 Observer Location")
    OBSERVER_PRESETS = {
        "Multan, Pakistan (Default)": (30.1575, 71.5249, 122.0),
        "Islamabad, Pakistan": (33.6844, 73.0479, 540.0),
        "Karachi, Pakistan": (24.8607, 67.0011, 10.0),
        "Lahore, Pakistan": (31.5204, 74.3587, 217.0),
        "Greenwich, UK": (51.4769, -0.0005, 48.0),
        "Custom Location": None,
    }

    selected_preset = st.selectbox("Ground Station Preset", list(OBSERVER_PRESETS.keys()), index=0)

    if selected_preset == "Custom Location":
        obs_lat = st.number_input("Latitude (°)", value=30.1575, format="%.4f")
        obs_lon = st.number_input("Longitude (°)", value=71.5249, format="%.4f")
        obs_elev = st.number_input("Elevation (m)", value=122.0, format="%.1f")
        obs_name = f"Custom ({obs_lat:.2f}°, {obs_lon:.2f}°)"
    else:
        preset_coords = OBSERVER_PRESETS[selected_preset]
        obs_lat, obs_lon, obs_elev = preset_coords
        obs_name = selected_preset.split(" (")[0]

    mask_angle = st.slider(
        "Elevation Mask Angle (°)",
        min_value=0.0,
        max_value=25.0,
        value=5.0,
        step=1.0,
        help="Signals below this angle are excluded from acquisition due to tropospheric attenuation and multipath."
    )

    st.markdown("---")
    st.markdown("#### ⏱️ Stage 2: Time Simulation")

    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("▶️ Play" if not st.session_state.is_playing else "⏸️ Pause"):
            st.session_state.is_playing = not st.session_state.is_playing
            st.rerun()

    with col_btn2:
        if st.button("🔄 Reset"):
            st.session_state.sim_minutes = 0.0
            st.session_state.is_playing = False
            st.rerun()

    with col_btn3:
        if st.button("🕒 Now"):
            st.session_state.base_time = datetime.now(timezone.utc)
            st.session_state.sim_minutes = 0.0
            st.rerun()

    sim_slider = st.slider(
        "Simulated Time Offset",
        min_value=0.0,
        max_value=720.0,  # 12 hours = ~1 full GPS orbit (11h 58m)
        value=float(st.session_state.sim_minutes),
        step=5.0,
        format="%d min",
        help="Scrub forward in time up to 12 hours (covering a complete GPS orbital period)."
    )

    if sim_slider != st.session_state.sim_minutes and not st.session_state.is_playing:
        st.session_state.sim_minutes = sim_slider

    step_minutes = st.selectbox(
        "Animation Step Speed",
        options=[2.0, 5.0, 10.0, 15.0, 30.0],
        index=1,
        format_func=lambda x: f"{int(x)} min/frame"
    )

    st.markdown("---")
    st.markdown("#### ⚙️ Data & Display Options")
    force_offline = st.checkbox("Force Offline TLE Cache", value=False)
    show_orbit_trails = st.checkbox("Show 12h Ground Tracks", value=True)
    show_3d_rings = st.checkbox("Show 3D Orbital Plane Rings", value=True)


# ==============================================================================
# 3. Data Ingestion & Orbital Mechanics Engine
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_and_initialize_constellation(offline_mode: bool):
    """
    Caches TLE data fetch and SGP4 satellite object initialization.
    """
    tle_text, source_desc = fetch_or_load_tle(force_offline=offline_mode)
    from skyfield.api import load
    ts = load.timescale()
    satellites = parse_gps_satellites(tle_text, ts)
    return satellites, source_desc


try:
    with st.spinner("Initializing GPS Constellation SGP4 Engine..."):
        satellites, data_source = load_and_initialize_constellation(force_offline)
        engine = OrbitEngine(satellites)
except Exception as err:
    st.error(f"Error initializing orbital engine: {err}")
    st.stop()


# Calculate simulated timestamp
sim_current_time = st.session_state.base_time + timedelta(minutes=st.session_state.sim_minutes)
sim_skyfield_t = engine.ts.from_datetime(sim_current_time)

# Propagate constellation to simulated time
propagated_sats = engine.propagate_constellation(
    t=sim_skyfield_t,
    observer_lat=obs_lat,
    observer_lon=obs_lon,
    observer_elev_m=obs_elev,
    mask_angle_deg=mask_angle
)

# Precompute ground tracks if requested
ground_tracks = None
if show_orbit_trails:
    ground_tracks = engine.compute_ground_track_history(
        base_time=st.session_state.base_time,
        duration_hours=11.97,
        step_minutes=8.0
    )


# ==============================================================================
# 4. Main Dashboard Header & Metrics
# ==============================================================================

st.markdown('<div class="main-title">🛰️ GPS Constellation & Orbital Propagation Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Physics Final Year Project (FYP): GPS Software-Defined Receiver — Stages 1 & 2</div>',
    unsafe_allow_html=True
)

# Status & Time Banner
pkt_time = sim_current_time + timedelta(hours=5)  # UTC+5 for Pakistan Standard Time
st.markdown(
    f"""
    <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-bottom: 18px;">
        <span class="status-badge">📡 <b>Data Source:</b> {data_source}</span>
        <span class="status-badge">🌍 <b>Ground Station:</b> {obs_name} ({obs_lat:.2f}° N, {obs_lon:.2f}° E)</span>
        <span class="status-badge">⏱️ <b>Sim UTC:</b> {sim_current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC</span>
        <span class="status-badge">🇵🇰 <b>Local PKT:</b> {pkt_time.strftime('%Y-%m-%d %H:%M:%S')} PKT</span>
        <span class="status-badge">⏳ <b>Elapsed Orbit:</b> +{int(st.session_state.sim_minutes)} min ({st.session_state.sim_minutes / 60.0:.2f}h)</span>
    </div>
    """,
    unsafe_allow_html=True
)

# KPI Cards
render_telemetry_metrics(propagated_sats, mask_angle)
st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)


# ==============================================================================
# 5. Visual Dashboard Tabs
# ==============================================================================

tab_3d, tab_2d, tab_sky, tab_telemetry, tab_theory = st.tabs([
    "🌐 3D Constellation Orbit View",
    "🗺️ 2D Ground-Track Map",
    "📡 Observer Sky-Plot (Acquisition View)",
    "📊 Ephemeris Telemetry Table",
    "📖 Orbital Mechanics & SGP4 Guide"
])

with tab_3d:
    st.markdown("#### 3D Earth & GPS Constellation Orbital Shell")
    st.caption("32 operational satellites in Medium Earth Orbit (~20,200 km altitude, 55° inclination). Green diamonds indicate satellites currently in line-of-sight from the selected ground station.")
    fig_3d = create_globe_3d_figure(
        satellites_data=propagated_sats,
        observer_lat=obs_lat,
        observer_lon=obs_lon,
        observer_name=obs_name,
        show_orbital_rings=show_3d_rings
    )
    st.plotly_chart(fig_3d, use_container_width=True)

with tab_2d:
    st.markdown("#### 2D Sub-Satellite Ground-Track Projection (WGS84)")
    st.caption("Sub-satellite coordinates projected onto the equirectangular world map. Blue curves depict the sinusoidal repeating ground tracks bounded between ±55° latitude over 1 orbital period (~11h 58m).")
    fig_2d = create_ground_track_figure(
        satellites_data=propagated_sats,
        observer_lat=obs_lat,
        observer_lon=obs_lon,
        observer_name=obs_name,
        ground_tracks=ground_tracks,
        show_tracks=show_orbit_trails
    )
    st.plotly_chart(fig_2d, use_container_width=True)

with tab_sky:
    st.markdown(f"#### Topocentric Sky-Plot for {obs_name}")
    st.caption("Polar Azimuth-Elevation plot from the antenna frame. Satellites inside the dashed elevation mask circle (green) are eligible for receiver PRN code correlation and carrier tracking.")
    fig_sky = create_skyplot_figure(
        satellites_data=propagated_sats,
        observer_name=obs_name,
        mask_angle_deg=mask_angle
    )
    st.plotly_chart(fig_sky, use_container_width=True)

with tab_telemetry:
    st.markdown("#### Live Constellation Ephemeris & Acquisition Telemetry")
    st.caption("Detailed coordinates and topocentric angles sorted by elevation. Used to seed SDR Doppler frequency and code-delay acquisition search.")
    render_telemetry_table(propagated_sats, mask_angle)

with tab_theory:
    st.markdown("""
    ### 📖 Physics & Engineering Documentation for Supervisor Defense

    #### 1. Constellation Architecture (Navstar GPS)
    - **Orbital Regime**: Medium Earth Orbit (MEO) semi-synchronous circular orbits.
    - **Semi-major Axis ($a$)**: $\\approx 26,560\\text{ km}$ ($r = R_E + h \\approx 6378 + 20182\\text{ km}$).
    - **Orbital Period ($T$)**: 11 hours 57 minutes 59.5 seconds (half a sidereal day, $43079.5\\text{ s}$).
    - **Inclination ($i$)**: $55.0^\\circ$ relative to the equatorial plane.
    - **Constellation Geometry**: 6 orbital planes (A, B, C, D, E, F) spaced $60^\\circ$ apart in Right Ascension of the Ascending Node ($\\Omega$), each containing 4–5 satellites, ensuring at least 4–8 satellites are visible simultaneously from any point on Earth.

    #### 2. SGP4 Orbital Propagator Formulation
    - **Two-Line Elements (TLE)** provide Keplerian mean orbital elements at an epoch ($t_0$).
    - Standard Keplerian propagation ($r = \\frac{a(1-e^2)}{1 + e\\cos\\nu}$) assumes a point-mass spherical Earth.
    - **SGP4 (Simplified General Perturbations-4)** integrates critical perturbation physics:
      1. **Earth Oblateness ($J_2, J_3, J_4$ zonal harmonics)**: Non-spherical geopotential causes nodal regression (precession of $\\Omega$) and rotation of the line of apsides (argument of perigee $\\omega$).
      2. **Atmospheric Drag**: Modeled via the ballistic drag term $B^*$.
      3. **Lunisolar Third-Body Gravitation**: Gravitational perturbations from the Moon and Sun, which are significant in MEO.
      4. **Earth Radiation Pressure & Solar Radiation Pressure**.

    #### 3. Coordinate Frame Transformations
    1. **TEME $\\to$ ITRS / ECEF**: SGP4 produces output in the True Equator, Mean Equinox (TEME) inertial frame. Skyfield converts this into the International Terrestrial Reference System (ITRS) / Earth-Centered Earth-Fixed (ECEF) frame by applying Greenwich Sidereal Time (Earth's diurnal rotation $\\theta_{GST}$).
    2. **ECEF $\\to$ WGS84 Geodetic**: Cartesian coordinates $(X, Y, Z)$ are mapped to geodetic Latitude ($\\phi$), Longitude ($\\lambda$), and Ellipsoidal Altitude ($h$) using the WGS84 reference ellipsoid ($a = 6378.137\\text{ km}, f = 1/298.257223563$).
    3. **ECEF $\\to$ Topocentric SEZ / Horizon**: Given the receiver station coordinates $(\\phi_{obs}, \\lambda_{obs}, h_{obs})$, the line-of-sight vector $\\vec{\\rho} = \\vec{r}_{sat} - \\vec{r}_{obs}$ is rotated into local South-East-Zenith (SEZ) coordinates to derive:
       - **Azimuth ($\\alpha$)**: $\\tan^{-1}(E / -S)$ ($0^\\circ$ to $360^\\circ$ from North)
       - **Elevation ($e$)**: $\\sin^{-1}(Z / |\\vec{\\rho}|)$ ($-90^\\circ$ to $+90^\\circ$)
       - **Geometric Slant Range ($\\rho$)**: $|\\vec{\\rho}|$ in km.

    #### 4. Relevance to Stage 3 (GPS SDR Signal Generation & Acquisition)
    - In a GPS SDR, the receiver searches a 2-dimensional space: **Code Phase** (0 to 1022 chips) $\\times$ **Carrier Doppler Frequency** ($f_d \\in [-5\\text{ kHz}, +5\\text{ kHz}]$).
    - Knowing the visible PRNs from this sky-plot eliminates unneeded search channels.
    - Calculating relative velocity allows predicting the nominal Doppler frequency shift:
      $$f_d = - \\frac{\\vec{v}_{rel} \\cdot \\hat{\\rho}}{c} f_{L1}$$
      where $f_{L1} = 1575.42\\text{ MHz}$ and $c \\approx 3 \\times 10^8\\text{ m/s}$.
    """)


# ==============================================================================
# 6. Playback Engine Loop (Stage 2)
# ==============================================================================

if st.session_state.is_playing:
    new_sim = st.session_state.sim_minutes + step_minutes
    if new_sim > 720.0:  # Loop back after 12 hours (1 full orbit)
        new_sim = 0.0
    st.session_state.sim_minutes = new_sim
    time.sleep(0.35)
    st.rerun()
