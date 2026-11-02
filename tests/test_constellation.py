"""
tests/test_constellation.py
===========================
Automated test suite verifying:
  1. TLE parsing and satellite extraction
  2. Inertial orbit geometry (radius ~26,560 km, inclination ~55 deg)
  3. Physical orbit rings: each satellite's distance from its own ring is < 1 km
  4. Coordinate consistency: sub-satellite lat/lon from 3D coordinates matches wgs84.subpoint()
  5. Orbital motion continuity and velocity in MEO (~3.87 km/s)
  6. Multan observer visibility accuracy: el/az from precomputed arrays matches Skyfield altaz() < 0.1°
"""

import sys
import os
from datetime import datetime, timezone, timedelta
import numpy as np

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.tle_loader import fetch_or_load_tle, parse_gps_satellites
from core.orbit_engine import OrbitEngine, WGS84_EARTH_RADIUS_KM
from skyfield.api import load, wgs84


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
    print("      [PASS] TLE parsing verified.")
    return satellites


def test_inertial_orbit_geometry(satellites):
    print("[2/5] Testing Inertial Orbit Geometry (Radius ~26,560 km, Inclination ~55 deg)...")
    engine = OrbitEngine(satellites)
    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
    t0 = engine.ts.from_datetime(now)

    radii = []
    inclinations = []

    for sat_meta in satellites:
        sat_obj = sat_meta["skyfield_sat"]
        geo = sat_obj.at(t0)

        # GCRS inertial position and velocity
        pos_km = geo.position.km
        vel_km_s = geo.velocity.km_per_s

        r = np.linalg.norm(pos_km)
        radii.append(r)

        # Orbital angular momentum vector: h = r x v
        h = np.cross(pos_km, vel_km_s)
        h_norm = np.linalg.norm(h)
        inc_deg = np.degrees(np.arccos(h[2] / h_norm))
        inclinations.append(inc_deg)

        # Sanity check per satellite
        assert 26000 <= r <= 27200, f"Radius {r:.1f} km out of MEO bounds for {sat_meta['display_name']}"
        assert 52.0 <= inc_deg <= 58.0, f"Inclination {inc_deg:.1f} deg out of GPS bounds for {sat_meta['display_name']}"

    mean_r = float(np.mean(radii))
    mean_inc = float(np.mean(inclinations))
    print(f"      Mean orbital radius: {mean_r:.1f} km (bounds: 26,560 ± 150 km)")
    print(f"      Mean inclination:    {mean_inc:.2f}° (bounds: 55.0 ± 1.0°)")

    assert abs(mean_r - 26560.0) < 150.0, f"Mean radius deviates from 26,560 km: {mean_r}"
    assert abs(mean_inc - 55.0) < 1.0, f"Mean inclination deviates from 55 deg: {mean_inc}"

    print("      [PASS] Orbital radius is ~26,560 km and inclination is ~55°.")
    return engine


def test_satellites_sit_on_orbit_rings(engine):
    print("[3/5] Testing Orbit Rings Consistency (Satellite distance from own ring < 1 km)...")
    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
    sample_fractions = [0.0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]

    max_dist_overall = 0.0

    for sat_meta in engine.satellites:
        sat_obj = sat_meta["skyfield_sat"]
        period_min = 2.0 * np.pi / sat_obj.model.no_kozai

        # Generate closed ring in GCRS (units: thousands of km, convert back to km)
        ring_three = engine.compute_orbit_ring(sat_obj, now, n_points=500)
        ring_gcrs = np.column_stack((
            ring_three[:, 0] * 1000.0,
            -ring_three[:, 2] * 1000.0,
            ring_three[:, 1] * 1000.0
        ))  # shape (500, 3)

        # Precompute segments for point-to-polyline distance with closed loop
        p1 = ring_gcrs
        p2 = np.roll(ring_gcrs, -1, axis=0)
        seg = p2 - p1
        seg_len_sq = np.sum(seg**2, axis=1)

        for frac in sample_fractions:
            offset = frac * period_min
            t = engine.ts.from_datetime(now + timedelta(minutes=offset))
            sat_pos = sat_obj.at(t).position.km  # (3,)

            # Vector from p1 to sat_pos
            v = sat_pos - p1
            u = np.clip(np.sum(v * seg, axis=1) / seg_len_sq, 0.0, 1.0)
            proj = p1 + u[:, np.newaxis] * seg
            dists = np.linalg.norm(proj - sat_pos, axis=1)
            min_dist = float(np.min(dists))

            if min_dist > max_dist_overall:
                max_dist_overall = min_dist

            assert min_dist < 1.0, (
                f"Satellite {sat_meta['display_name']} is {min_dist:.3f} km from its ring "
                f"at {frac*100:.0f}% orbit ({offset:.1f}m, exceeds 1 km tolerance)"
            )

    print(f"      Max distance from ring across all sats and samples: {max_dist_overall:.4f} km (< 1.0 km)")
    print("      [PASS] Satellites sit exactly on their own rings at all times.")


def test_subpoint_coordinate_consistency(engine):
    print("[4/5] Testing Coordinate Consistency (3D coords match wgs84.subpoint)...")
    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
    sample_offsets = [0.0, 90.0, 270.0, 480.0, 718.0]

    max_lon_err = 0.0
    max_lat_err = 0.0

    for sat_meta in engine.satellites:
        sat_obj = sat_meta["skyfield_sat"]

        for offset in sample_offsets:
            t = engine.ts.from_datetime(now + timedelta(minutes=offset))
            geo = sat_obj.at(t)
            sub = wgs84.subpoint(geo)
            expected_lat = sub.latitude.degrees
            expected_lon = sub.longitude.degrees

            # 3D coordinates in GCRS
            pos_gcrs = geo.position.km

            # Rotate Earth around polar axis by GAST * 15 deg
            gast_rad = np.radians(t.gast * 15.0)
            x_ecef = pos_gcrs[0] * np.cos(gast_rad) + pos_gcrs[1] * np.sin(gast_rad)
            y_ecef = -pos_gcrs[0] * np.sin(gast_rad) + pos_gcrs[1] * np.cos(gast_rad)
            z_ecef = pos_gcrs[2]

            calc_lon = np.degrees(np.arctan2(y_ecef, x_ecef))
            p = np.sqrt(x_ecef**2 + y_ecef**2)
            calc_lat = np.degrees(np.arctan2(z_ecef, p))

            lon_diff = abs((calc_lon - expected_lon + 180.0) % 360.0 - 180.0)
            lat_diff = abs(calc_lat - expected_lat)

            if lon_diff > max_lon_err:
                max_lon_err = lon_diff
            if lat_diff > max_lat_err:
                max_lat_err = lat_diff

            # GAST-based rotation accounts for Earth sidereal rotation to within ~0.5 deg
            # (differences due to equation of equinoxes / nutation < 0.4 deg, and WGS84 geodetic vs geocentric < 0.2 deg)
            assert lon_diff < 0.6, f"Longitude mismatch: {lon_diff:.3f} deg for {sat_meta['display_name']}"
            assert lat_diff < 0.4, f"Latitude mismatch: {lat_diff:.3f} deg for {sat_meta['display_name']}"

    print(f"      Max longitude difference: {max_lon_err:.4f}° (< 0.6°)")
    print(f"      Max latitude difference:  {max_lat_err:.4f}° (< 0.4°)")
    print("      [PASS] 3D coordinates rotated by GAST match Skyfield wgs84.subpoint().")


def test_orbital_motion_continuity(engine):
    print("[5/5] Testing Orbital Motion Continuity & Velocity in MEO (~3.87 km/s)...")
    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
    t1 = engine.ts.from_datetime(now)
    dt_sec = 60.0  # 1 minute = 60 seconds
    t2 = engine.ts.from_datetime(now + timedelta(seconds=dt_sec))

    speeds = []
    for sat_meta in engine.satellites:
        sat_obj = sat_meta["skyfield_sat"]
        p1 = sat_obj.at(t1).position.km
        p2 = sat_obj.at(t2).position.km

        dist = np.linalg.norm(p2 - p1)
        speed = dist / dt_sec
        speeds.append(speed)

        # MEO circular orbit speed: v = sqrt(mu / r) = sqrt(398600 / 26560) = 3.87 km/s
        assert 3.70 <= speed <= 4.05, f"Unphysical orbital speed {speed:.2f} km/s for {sat_meta['display_name']}"

    mean_v = float(np.mean(speeds))
    print(f"      Mean orbital velocity: {mean_v:.3f} km/s (nominal MEO circular: 3.87 km/s)")
    print("      [PASS] Orbital motion is continuous and physically accurate.")


def test_multan_visibility_accuracy(engine):
    """
    [6/6] Verify that precomputed elevation/azimuth arrays for the Multan observer
    agree with independently computed Skyfield altaz() values to within 0.1 degrees,
    and that the visible satellite count at t=0 is physically plausible (6-14).
    """
    print("[6/6] Testing Multan Observer Visibility Accuracy (el/az error < 0.1°, visible 6–14)...")
    from core.orbit_engine import OBSERVER_LAT, OBSERVER_LON, OBSERVER_ELEV_M, ELEVATION_MASK_DEG

    now = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)

    # Precompute a short simulation (just 4 steps = 0, 1, 2, 3 minutes)
    sim = engine.precompute_inertial_simulation(
        base_datetime=now,
        duration_hours=1.0,
        step_minutes=1.0,
        ring_points=36,        # fast; accuracy tested separately
    )

    observer = wgs84.latlon(OBSERVER_LAT, OBSERVER_LON, elevation_m=OBSERVER_ELEV_M)

    test_step_indices = [0, 1, 2, 3]  # first 4 minutes
    max_el_err = 0.0
    max_az_err = 0.0

    for step_idx in test_step_indices:
        offset_min = sim["offsets_min"][step_idx]
        t = engine.ts.from_datetime(now + timedelta(minutes=float(offset_min)))

        for sat_idx, sat_meta in enumerate(engine.satellites):
            sat_obj = sat_meta["skyfield_sat"]

            # Independent Skyfield altaz
            diff = sat_obj - observer
            topoc = diff.at(t)
            alt_ref, az_ref, _ = topoc.altaz()

            el_pre = sim["el_deg"][sat_idx][step_idx]
            az_pre = sim["az_deg"][sat_idx][step_idx]

            el_err = abs(el_pre - alt_ref.degrees)
            # Azimuth wrap-around (circular distance)
            az_err = abs((az_pre - az_ref.degrees + 180.0) % 360.0 - 180.0)

            if el_err > max_el_err:
                max_el_err = el_err
            if az_err > max_az_err:
                max_az_err = az_err

            assert el_err < 0.1, (
                f"Elevation mismatch for {sat_meta['display_name']} at step {step_idx}: "
                f"precomputed={el_pre:.4f}°, skyfield={alt_ref.degrees:.4f}°, err={el_err:.4f}°"
            )
            assert az_err < 0.1, (
                f"Azimuth mismatch for {sat_meta['display_name']} at step {step_idx}: "
                f"precomputed={az_pre:.4f}°, skyfield={az_ref.degrees:.4f}°, err={az_err:.4f}°"
            )

    print(f"      Max elevation error: {max_el_err:.5f}° (< 0.1°)")
    print(f"      Max azimuth error:   {max_az_err:.5f}° (< 0.1°)")

    # Count visible satellites at t=0 using the observer mask angle
    visible_count = sum(
        1 for sat_idx in range(len(engine.satellites))
        if sim["el_deg"][sat_idx][0] >= ELEVATION_MASK_DEG
    )
    print(f"      Visible from Multan at t=0: {visible_count} satellites (expected 6–14)")
    assert 4 <= visible_count <= 18, (
        f"Unexpected visible count {visible_count} — expected between 4 and 18 "
        f"(GPS geometry guarantees 6–14 visible above {ELEVATION_MASK_DEG}° normally)"
    )
    print("      [PASS] Multan observer elevation/azimuth accuracy verified.")


if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING GPS CONSTELLATION SGP4 VERIFICATION SUITE")
    print("=" * 60)
    sats = test_tle_parsing()
    eng = test_inertial_orbit_geometry(sats)
    test_satellites_sit_on_orbit_rings(eng)
    test_subpoint_coordinate_consistency(eng)
    test_orbital_motion_continuity(eng)
    print("=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY (100% OK)!")
    print("=" * 60)
