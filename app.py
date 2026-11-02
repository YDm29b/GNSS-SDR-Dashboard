"""
app.py
======
NCGSA GNSS SDR — GPS Constellation & Orbital Motion Simulation
by YDM
A project of NCGSA, IST, Islamabad.

Strict Rebuild:
  1. VISUALIZE the GPS constellation in the INERTIAL frame (GCRS).
  2. SIMULATE the GPS constellation's motion over time in Three.js (60 FPS, client-side).
  - No tabs, no extraneous UI.
  - SGP4 propagation via Skyfield with GCRS inertial coordinates.
  - Earth rotation aligned with Greenwich Apparent Sidereal Time (GAST).
  - High-performance, zero Streamlit reruns during playback.
"""

from datetime import datetime, timezone, timedelta
import streamlit as st
import streamlit.components.v1 as components

# Configure page metadata
st.set_page_config(
    page_title="NCGSA GNSS SDR | by YDM",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Dark Space Theme & Streamlit Chrome Removal (Step 5)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Orbitron:wght@700;800;900&family=Space+Grotesk:wght@500;700&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText, p, span {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    h1, h2, h3, h4, .hero-title, .hero-subtitle {
        font-family: 'Orbitron', 'Space Grotesk', sans-serif !important;
    }

    /* Space Background */
    .stApp {
        background-color: #060913;
        background-image: 
            radial-gradient(1px 1px at 30px 40px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 150px 180px, #38bdf8, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 280px 100px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 400px 300px, #a855f7, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 550px 150px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 700px 240px, #38bdf8, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 850px 80px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(2px 2px at 1000px 260px, #818cf8, rgba(0,0,0,0)),
            radial-gradient(1px 1px at 1150px 120px, #ffffff, rgba(0,0,0,0)),
            radial-gradient(1.5px 1.5px at 1300px 320px, #c084fc, rgba(0,0,0,0));
        background-repeat: repeat;
        background-size: 800px 600px;
    }

    /* Hide Streamlit Deploy, Hamburger Menu, Footer, and Header */
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    header[data-testid="stHeader"] { visibility: hidden !important; height: 0 !important; }
    .stDeployButton, [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {
        display: none !important;
    }

    /* Container Spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0.5rem !important;
        max-width: 100% !important;
    }

    /* Hero Typography */
    .hero-container {
        padding: 0 0 0.5rem 0;
    }
    .hero-title {
        font-size: 2.5rem;
        font-weight: 900;
        margin-bottom: 0.15rem;
        background: linear-gradient(135deg, #00f2fe 0%, #38bdf8 45%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 35px rgba(56, 189, 248, 0.35);
        letter-spacing: 0.05em;
    }
    .hero-subtitle {
        font-size: 1.1rem;
        font-weight: 700;
        color: #38bdf8;
        letter-spacing: 0.12em;
        margin-bottom: 0.25rem;
    }
    .hero-desc {
        font-size: 0.95rem;
        color: #94a3b8;
        margin-bottom: 0.8rem;
        font-weight: 400;
    }

    /* Minimal Status Badges */
    .status-pill {
        background: rgba(15, 23, 42, 0.72);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(56, 189, 248, 0.25);
        border-radius: 20px;
        padding: 4px 12px;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

from core.tle_loader import fetch_or_load_tle, parse_gps_satellites
from core.orbit_engine import OrbitEngine
from views.three_globe_view import render_three_globe


@st.cache_resource(ttl=3600, show_spinner=False)
def get_cached_constellation(offline_mode: bool = False):
    """
    Caches TLE data fetch and SGP4 satellite object initialization.
    """
    tle_text, source_desc = fetch_or_load_tle(force_offline=offline_mode)
    from skyfield.api import load
    ts = load.timescale()
    satellites = parse_gps_satellites(tle_text, ts)
    return satellites, source_desc


@st.cache_data(show_spinner=False)
def get_precomputed_inertial_simulation(base_date_str: str, offline_mode: bool = False):
    """
    Precomputes the 12-hour simulation in the GCRS inertial frame.
    Cached as a dictionary with satellite positions, rings, and GAST rotation.
    """
    satellites, _ = get_cached_constellation(offline_mode)
    engine = OrbitEngine(satellites)
    base_dt = datetime.fromisoformat(base_date_str)
    return engine.precompute_inertial_simulation(
        base_datetime=base_dt,
        duration_hours=12.0,
        step_minutes=1.0,
        ring_points=360
    )


# Anchor simulation base time to the nearest 5-minute mark
if "sim_base_dt" not in st.session_state:
    now_utc = datetime.now(timezone.utc)
    st.session_state.sim_base_dt = now_utc.replace(
        minute=(now_utc.minute // 5) * 5, second=0, microsecond=0
    )

with st.spinner("Initializing GPS Constellation in Inertial Frame..."):
    satellites_raw, data_source = get_cached_constellation(offline_mode=False)
    sim_data = get_precomputed_inertial_simulation(
        base_date_str=st.session_state.sim_base_dt.isoformat(),
        offline_mode=False
    )

# --- HERO SECTION (Step 5) ---
st.markdown("""
<div class="hero-container">
    <div class="hero-title">NCGSA GNSS SDR</div>
    <div class="hero-subtitle">by YDM</div>
    <p class="hero-desc">A project of NCGSA, IST, Islamabad.</p>
</div>
""", unsafe_allow_html=True)

# Minimal status indicator row (Item 4: TLE Live/Cache badge with epoch date)
base_dt = st.session_state.sim_base_dt
tle_epoch_str = satellites_raw[0]["skyfield_sat"].epoch.utc_strftime("%Y-%m-%d %H:%M UTC")
is_live = "CelesTrak" in data_source or "Live" in data_source
tle_badge = "Live Celestrak" if is_live else "Local Cache"

st.markdown(f"""
<div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px;">
    <span class="status-pill">📡 <b>TLE:</b> {tle_badge} (Epoch: {tle_epoch_str})</span>
    <span class="status-pill">🛰️ <b>Constellation:</b> {len(sim_data['satellites'])} Active MEO Satellites</span>
    <span class="status-pill">🌐 <b>Frame:</b> GCRS Inertial + Sidereal Earth Rotation</span>
    <span class="status-pill">⏱️ <b>Sim Base:</b> {base_dt.strftime('%Y-%m-%d %H:%M')} UTC</span>
</div>
""", unsafe_allow_html=True)

# --- FULL-WIDTH THREE.JS 3D GLOBE + CONTROLS (Steps 1, 3, 4) ---
globe_html = render_three_globe(sim_data)
components.html(globe_html, height=680, scrolling=False)
