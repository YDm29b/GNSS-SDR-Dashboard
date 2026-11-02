# NCGSA GNSS SDR — GPS Constellation Dashboard
### by YDM — A project of NCGSA, IST, Islamabad.

A high-performance 3D visualization and orbital simulation of the operational GPS constellation, built for Stage 1 and Stage 2 of a GPS Software-Defined Receiver final-year physics project.

---

## Capabilities & Architecture

1. **GCRS Inertial Frame Consistency**:
   - All 32 operational GPS satellites are propagated using Skyfield SGP4 in the True Geocentric Celestial Reference System (GCRS/ICRF inertial frame).
   - Orbit rings are closed stationary 3D ellipses in space (~11h 58m period, 500 vertices per ring).
   - Satellites sit exactly on their own rings at all times (max distance < 0.54 km across the entire constellation).
2. **Sidereal Earth Alignment**:
   - Earth mesh rotates around its polar axis by Greenwich Apparent Sidereal Time (GAST $\times$ 15°).
   - Textured with a 2K NASA Blue Marble equirectangular map embedded as a base64 data URI with a soft atmospheric glow.
   - Continents align with true sub-satellite geodetic positions.
3. **Orbital Plane Clustering**:
   - Satellites and rings are clustered into 6 orbital planes (A through F) by Right Ascension of the Ascending Node (RAAN) spaced ~60° apart.
   - Plane color coding:
     - **Plane A**: `#38bdf8` (Cyan)
     - **Plane B**: `#a855f7` (Purple)
     - **Plane C**: `#00ff88` (Mint Green)
     - **Plane D**: `#f59e0b` (Amber)
     - **Plane E**: `#ec4899` (Pink)
     - **Plane F**: `#818cf8` (Indigo)
4. **Three.js Client-Side Engine**:
   - 60 FPS continuous animation via `requestAnimationFrame` with smooth interpolation between 1-minute precomputed steps.
   - Zero Streamlit reruns during playback.
   - OrbitControls with damping for smooth rotate, pan, and zoom. Camera position never resets on play/pause/scrub.
   - PRN labels offset up and to the right, fading out when zooming far away, with an on-screen toggle.
   - Hover / click info card showing PRN, NORAD ID, Plane, Altitude, and Sub-lat/lon.
5. **Integrated Slim Control Bar**:
   - Play/Pause, 0h Reset, Now, speed selector (1×, 5× default, 15×, 30×, 60× sim-minutes per real second), time scrubber (12h range), UTC timestamp display, and Labels toggle.

---

## Verification Suite

Run the automated physics validation suite:

```bash
python verify_propagation.py
```

Checks:
1. **TLE Parsing**: Validates parsing of active GPS satellites from Celestrak or local cache.
2. **Inertial Orbit Geometry**: Verifies mean orbital radius is 26,560 km ± 150 km and mean inclination is 55.0° ± 1.0°.
3. **Orbit Rings Consistency**: Confirms each satellite's 3D distance to its own closed orbit ring is < 1.0 km across all sampled times.
4. **Coordinate Consistency**: Verifies 3D coordinates rotated by Earth GAST match Skyfield `wgs84.subpoint()`.
5. **Orbital Motion Continuity**: Confirms MEO circular orbital velocity of ~3.87 km/s without discontinuous jumps.

---

## Running the Dashboard

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`. Works fully offline with local Three.js, OrbitControls, and cached TLE data.
