"""
verify_propagation.py
=====================
Direct entry point for verifying the GPS SGP4 orbital propagation suite.
Executes the comprehensive automated tests in tests/test_constellation.py.
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.test_constellation import (
    test_tle_parsing,
    test_sgp4_propagation_physics,
    test_observer_visibility_and_angles,
    test_orbital_motion_continuity,
    test_ground_track_history,
)

if __name__ == "__main__":
    print("=" * 60)
    print("RUNNING GPS CONSTELLATION SGP4 PROPAGATION VERIFICATION")
    print("=" * 60)
    sats = test_tle_parsing()
    eng, res = test_sgp4_propagation_physics(sats)
    test_observer_visibility_and_angles(res)
    test_orbital_motion_continuity(eng)
    test_ground_track_history(eng)
    print("=" * 60)
    print("ALL VERIFICATION CHECKS PASSED (100% OK)")
    print("=" * 60)
