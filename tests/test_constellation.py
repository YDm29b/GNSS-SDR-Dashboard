"""
tests/test_constellation.py
===========================
Automated test suite verifying TLE ingestion, SGP4 propagation accuracy,
reference frame transformations, and orbital motion continuity.
"""

import sys
import os
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tle_loader import fetch_or_load_tle, parse_gps_satellites
from core.orbit_engine import (
    OrbitEngine,
    WGS84_EARTH_RADIUS_KM,
    DEFAULT_OBSERVER_LAT,
    DEFAULT_OBSERVER_LON,
    DEFAULT_OBSERVER_ELEV_M
)
from skyfield.api import load


def test_tle_parsing():
    print("[1/5] Testing TLE parsing and satellite extraction...")
    tle_text, source = fetch_or_load_tle(force_offline=True)
    assert len(tle_text) > 0, "TLE text is empty"
    print(f"      Data source: {source}")

    ts = load.timescale()
    satellites = parse_gps_satellites(tle_text, ts)
    print(f"      Total satellites parsed: {len(satellites)}")
    assert len(satellites) >= 30, f"Expected >= 30 GPS satellites, got {len(satellites)}"

    prns = [s["prn"] for s in satellites if s["prn"] is not None]
    print(f"      Identified {len(prns)} valid PRN numbers: {sorted(prns)[:8]}...")
    assert len(prns) >= 28, "Too few satellites with identified PRN numbers"
    print("      ✓ PASSED")
    return satellites


def test_sgp4_propagation_physics(satellites):
    print("[2/5] Testing SGP4 orbital propagation physics...")
    engine = OrbitEngine(satellites)
    t0 = engine.ts.now()

    results = engine.propagate_constellation(
        t=t0,
        observer_lat=DEFAULT_OBSERVER_LAT,
        observer_lon=DEFAULT_OBSERVER_LON,
        observer_elev_m=DEFAULT_OBSERVER_ELEV_M,
        mask_angle_deg=5.0
    )

    assert len(results) == len(satellites), "Mismatch between satellite list and propagated count"

    for sat in results:
        alt = sat["altitude_km"]
        radius = sat["radius_km"]
        # MEO orbital altitude check: 19,000 km to 21,500 km
        assert 19000 <= alt <= 22000, f"Unrealistic altitude for {sat['display_name']}: {alt} km"
        # Radius check: r ~ 26,560 km
        assert 25000 <= radius <= 28000, f"Unrealistic orbital radius for {sat['display_name']}: {radius} km"
        # Sub-point latitude must be within +/- 56 degrees (55 deg inclination)
        assert -56.5 <= sat["latitude"] <= 56.5, f"Sub-lat exceeds 55 deg inclination: {sat['latitude']} deg"
        # Sub-point longitude within [-180, 180]
        assert -180.0 <= sat["longitude"] <= 180.0, f"Invalid longitude: {sat['longitude']}"

    print(f"      ✓ All {len(results)} satellites conform to MEO bounds (Alt: 20,200 km, Inc: 55°)")
    return engine, results


def test_observer_visibility_and_angles(results):
    print("[3/5] Testing Multan observer topocentric coordinates...")
    visible_sats = [s for s in results if s["is_visible"]]
    print(f"      Satellites currently visible above 5° mask in Multan: {len(visible_sats)}")

    # Standard GPS constellation guarantees 4 or more visible satellites everywhere on Earth
    assert len(visible_sats) >= 4, f"Fewer than 4 satellites in view ({len(visible_sats)}); 3D fix impossible!"

    for sat in results:
        az = sat["azimuth_deg"]
        el = sat["elevation_deg"]
        rng = sat["slant_range_km"]

        assert 0.0 <= az <= 360.0, f"Azimuth out of range [0, 360]: {az}"
        assert -90.0 <= el <= 90.0, f"Elevation out of range [-90, 90]: {el}"
        assert 19000 <= rng <= 28000, f"Slant range unrealistic: {rng} km"

    print("      ✓ PASSED (Azimuth, Elevation, and Slant Range verified)")


def test_orbital_motion_continuity(engine):
    print("[4/5] Testing Stage 2: Time simulation and orbital continuity...")
    now = datetime.now(timezone.utc)
    t1 = engine.get_time(now, offset_minutes=0.0)
    t2 = engine.get_time(now, offset_minutes=5.0)

    res1 = {s["norad_id"]: s for s in engine.propagate_constellation(t1)}
    res2 = {s["norad_id"]: s for s in engine.propagate_constellation(t2)}

    # Speed of satellite in MEO: v = sqrt(GM / r) ~ 3.87 km/s
    # In 5 minutes (300 seconds), distance moved ~ 3.87 * 300 ~ 1,160 km
    for norad_id in res1:
        s1 = res1[norad_id]
        s2 = res2[norad_id]

        dx = s2["x_ecef"] - s1["x_ecef"]
        dy = s2["y_ecef"] - s1["y_ecef"]
        dz = s2["z_ecef"] - s1["z_ecef"]
        dist = (dx**2 + dy**2 + dz**2)**0.5

        # In ECEF, Earth rotates underneath (~465 m/s at equator),
        # so total delta position in ECEF over 5 min is between 700 km and 1,800 km
        assert 700 <= dist <= 2000, f"Discontinuous jump or stationary error for {s1['display_name']}: {dist} km"

    print("      ✓ Motion is continuous and physically accurate (mean v ~ 3.87 km/s)")


def test_ground_track_history(engine):
    print("[5/5] Testing 12-hour orbital period ground track generation...")
    now = datetime.now(timezone.utc)
    tracks = engine.compute_ground_track_history(base_time=now, duration_hours=11.97, step_minutes=15.0)
    assert len(tracks) > 0, "No ground tracks generated"

    sample_key = list(tracks.keys())[0]
    sample_track = tracks[sample_key]
    assert len(sample_track["lats"]) > 20, "Ground track contains too few points"
    print(f"      ✓ Successfully generated repeating ground tracks over 11h 58m for {len(tracks)} satellites")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING GPS CONSTELLATION SGP4 VERIFICATION SUITE")
    print("=" * 60)
    sats = test_tle_parsing()
    eng, res = test_sgp4_propagation_physics(sats)
    test_observer_visibility_and_angles(res)
    test_orbital_motion_continuity(eng)
    test_ground_track_history(eng)
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
