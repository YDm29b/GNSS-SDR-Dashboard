"""
verify_propagation.py
=====================
Direct entry point for verifying the GPS SGP4 orbital propagation suite.
Executes the comprehensive automated tests in tests/test_constellation.py:
  1. TLE Parsing and extraction
  2. Inertial orbit geometry (radius ~26,560 km, inclination ~55 deg)
  3. Orbit rings: distance from each satellite to its own ring < 1 km
  4. Coordinate consistency: 3D rotated coordinates match Skyfield wgs84.subpoint()
  5. Orbital motion continuity and velocity (~3.87 km/s in MEO)
  6. Multan observer: precomputed el/az matches Skyfield altaz() < 0.1°, visible 6–14
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_constellation import (
    test_tle_parsing,
    test_inertial_orbit_geometry,
    test_satellites_sit_on_orbit_rings,
    test_subpoint_coordinate_consistency,
    test_orbital_motion_continuity,
    test_multan_visibility_accuracy,
)

if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING GPS CONSTELLATION SGP4 PROPAGATION VERIFICATION")
    print("=" * 60)
    sats = test_tle_parsing()
    eng = test_inertial_orbit_geometry(sats)
    test_satellites_sit_on_orbit_rings(eng)
    test_subpoint_coordinate_consistency(eng)
    test_orbital_motion_continuity(eng)
    test_multan_visibility_accuracy(eng)
    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED (100% OK)")
    print("=" * 60)
