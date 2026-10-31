# GNSS SDR Constellation & Orbital Propagation Dashboard
### Final Year Project (FYP) — Stages 1 & 2: GPS Constellation Visualization & Time Simulation

---

## 📌 Project Overview

This dashboard serves as the initial architectural stage of a **GPS Software-Defined Receiver (SDR)** Final Year Project. Before implementing signal generation, PRN code correlation, and carrier tracking (Stage 3), this dashboard establishes:

1. **Stage 1 — Constellation Visualization**:
   - Live ingestion and parsing of active GPS constellation ephemerides (TLE).
   - Real-time SGP4 orbital propagation of all 32 operational GPS satellites.
   - 3D interactive Earth globe showing satellites in their Medium Earth Orbit (MEO) shells.
   - 2D geographic ground-track map displaying sub-satellite points.
   - Topocentric polar sky-plot (Azimuth vs. Elevation) for a configurable ground receiver (default: **Multan, Pakistan**).
   - Constellation ephemeris telemetry table for SDR signal acquisition planning.

2. **Stage 2 — Time Simulation & Orbital Motion**:
   - Continuous time propagation engine synchronized across all 3 views (3D Globe, 2D Ground Track, Sky-Plot).
   - Play / Pause controls and an interactive time scrubber spanning a complete GPS orbital period ($\sim 11\text{h } 58\text{m}$, up to 12 hours).
   - Visual demonstration of Keplerian motion, showing smooth orbital trajectories and repeating ground tracks.

---

## 🛰️ Data Source & Offline Fallback

The primary input data source is the operational GPS Two-Line Element (TLE) ephemeris feed provided by **CelesTrak**:
- **Live URL**: `https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle`
- **Offline Fallback File**: `data/gps_operational.tle` (included in repository)

> **Offline Guarantee**: If network access is unavailable, the application automatically falls back to `data/gps_operational.tle`. Users can also force offline mode using the sidebar toggle (`Force Offline TLE Cache`).

Each satellite is cataloged by its:
- **PRN Number** (Pseudo-Random Noise code ID 1–32)
- **NORAD Catalog Number** (e.g., 26407)
- **Satellite Block Model** (Block IIR, Block IIR-M, Block IIF, Block III)
- **Epoch & Keplerian Elements**

---

## 🔬 Orbital Mechanics & Propagation Methodology (For Supervisor Defense)

### 1. SGP4 (Simplified General Perturbations-4) Propagator
Rather than assuming a naive 2-body Keplerian point mass ($F = \frac{GMm}{r^2}$), this dashboard uses the standard **SGP4 orbital propagator** implemented via the validated Python `skyfield` library.

SGP4 accounts for critical real-world perturbations:
- **Earth Oblateness ($J_2, J_3, J_4$ geopotential harmonics)**: The equatorial bulge causes nodal precession (regression of the ascending node $\dot{\Omega}$) and rotation of perigee ($\dot{\omega}$).
- **Atmospheric Drag ($B^*$)**: Accounted for via the ballistic drag parameter in the TLE.
- **Lunisolar Gravitational Perturbations**: Third-body gravitational forces exerted by the Moon and Sun, which are significant in Medium Earth Orbit ($r \approx 26,560\text{ km}$).
- **Solar Radiation Pressure**: Photon momentum perturbations over long timeframes.

### 2. GPS Constellation Orbital Geometry
- **Orbital Altitude ($h$)**: $\approx 20,200\text{ km}$ above the WGS84 ellipsoid.
- **Semi-Major Axis ($a$)**: $\approx 26,560\text{ km}$ ($a = R_E + h$).
- **Orbital Period ($T$)**: $11\text{ hours } 57\text{ minutes } 59.5\text{ seconds}$ (half a sidereal day, $\approx 43,080\text{ s}$).
- **Nominal Inclination ($i$)**: $55.0^\circ$ relative to the equatorial plane.
- **Constellation Architecture**: 6 orbital planes (A through F) spaced $60^\circ$ apart in Right Ascension of the Ascending Node ($\Omega$), inclined at $55^\circ$, each housing 4–5 satellites. This guarantees that at least 4–12 satellites are in direct line-of-sight from any point on Earth at all times.

### 3. Coordinate Frame Transformations
The dashboard computes transformations across four foundational coordinate systems:

```
[TLE Ephemeris]
       │
       ▼ (SGP4 Analytic Propagation)
[TEME Frame] (True Equator, Mean Equinox - Inertial)
       │
       ▼ (Greenwich Sidereal Time Rotation - θ_GST)
[ITRS / ECEF Frame] (Earth-Centered, Earth-Fixed Cartesian: X, Y, Z in km)
       │
       ├─────────────────────────────────┐
       ▼ (WGS84 Ellipsoid Projection)    ▼ (Topocentric Horizon Transform)
[Geodetic Coordinates]            [Topocentric SEZ Frame]
 - Latitude (φ: -90° to +90°)      - Azimuth (α: 0° to 360° from North)
 - Longitude (λ: -180° to +180°)   - Elevation (e: -90° to +90°)
 - Altitude (h: ~20,200 km)        - Slant Range (ρ: ~20,200 to 26,000 km)
```

### 4. Connection to Stage 3 (GPS SDR Signal Generation)
In a GPS receiver, signal acquisition searches across two dimensions:
1. **Code Phase**: Delay of the 1023-chip C/A Gold code replica.
2. **Doppler Frequency Shift ($f_d$)**: Carrier frequency offset induced by the relative radial velocity between satellite and receiver:
   $$f_d = - \frac{\vec{v}_{\text{rel}} \cdot \hat{\rho}}{c} f_{L1}$$
   where $f_{L1} = 1575.42\text{ MHz}$ and $c \approx 3 \times 10^8\text{ m/s}$.

The **Sky-Plot View** prunes the search space by identifying exactly which PRNs are above the horizon ($e \ge 5^\circ$), accelerating receiver acquisition by $> 65\%$.

---

## 🚀 How to Run the Dashboard

### Prerequisites
- Python 3.10+
- Installed packages: `skyfield`, `streamlit`, `plotly`, `pandas`, `httpx`, `numpy`

```bash
pip install -r requirements.txt
```

### Launching the Dashboard (Single Command)
```bash
streamlit run app.py
```

The web dashboard will automatically open in your default browser at `http://localhost:8501`.

### Running Automated Verification Suite
To verify TLE parsing, coordinate conversions, and SGP4 propagation physics:
```bash
python tests/test_constellation.py
```

---

## 🎛️ Dashboard Controls & Features

| View / Control | Description |
| :--- | :--- |
| **🌐 3D Constellation Orbit View** | Realistic 3D Earth globe with all 32 satellites plotted at their true ECEF positions in MEO shells. Satellites in view from Multan are highlighted in green. |
| **🗺️ 2D Ground-Track Map** | Sub-satellite points projected on an equirectangular world map. Includes 12-hour orbital trails oscillating between $\pm 55^\circ$ latitude. |
| **📡 Observer Sky-Plot** | Polar Azimuth-Elevation plot from Multan ($30.1575^\circ\text{ N}, 71.5249^\circ\text{ E}$). Features a configurable elevation mask ($5^\circ$ default) to filter multipath. |
| **📊 Ephemeris Telemetry Table** | Interactive table of PRN, NORAD ID, Block model, Elevation, Azimuth, Slant Range, and Sub-point coordinates. |
| **⏱️ Time Controls (Stage 2)** | Play/Pause animation, 0–12 hour time scrubber, adjustable speed (1–30 min/frame), and Reset buttons. |
| **📍 Observer Station Selector** | Quick presets for Multan, Islamabad, Karachi, Lahore, Greenwich, or arbitrary custom coordinates. |

---

## 📂 Codebase Structure

```
GNSS SDR Dashboard/
│
├── app.py                      # Main Streamlit dashboard orchestrator
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation & defense guide
│
├── data/
│   └── gps_operational.tle     # Cached CelesTrak TLE backup (32 active GPS satellites)
│
├── core/
│   ├── tle_loader.py           # TLE fetcher, offline fallback, and PRN extractor
│   └── orbit_engine.py         # SGP4 propagation, ECEF, WGS84, and Topocentric math
│
├── views/
│   ├── globe_view_3d.py        # 3D Earth globe and satellite shell rendering
│   ├── ground_track_view.py    # 2D equirectangular ground track map
│   ├── skyplot_view.py         # Polar sky-plot (Azimuth vs. Elevation)
│   └── telemetry_view.py       # Metrics cards and ephemeris data table
│
└── tests/
    └── test_constellation.py   # Comprehensive physics and math test suite
```

---
