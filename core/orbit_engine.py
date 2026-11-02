"""
core/orbit_engine.py
====================
Core orbital mechanics engine executing SGP4 propagation via Skyfield.
Computes satellite motion strictly in the INERTIAL reference frame (GCRS/ICRF)
for physical consistency with stationary orbital rings and Earth sidereal rotation.

Physics Context:
  - Constellation: 31-32 operational satellites in Medium Earth Orbit (MEO).
  - Semi-major axis (a) ~ 26,560 km (orbital radius from Earth's center).
  - Nominal orbital altitude (h) ~ 20,180 - 20,200 km above WGS84 ellipsoid.
  - Orbital period (T) ~ 11 hours 58 minutes (half a sidereal day, repeating ground track).
  - Nominal inclination (i) ~ 55 degrees across 6 orbital planes (A through F spaced ~60 deg).
  - Earth rotation: Greenwich Apparent Sidereal Time (GAST * 15 degrees).

Observer Configuration (easy to change here):
  - Name: Multan, Pakistan
  - Latitude:  30.1575 deg N
  - Longitude: 71.5249 deg E
  - Elevation: 122 m above WGS84 ellipsoid
  - Elevation mask: 5 deg (satellites below this are "not visible")
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from skyfield.api import load, wgs84, EarthSatellite, Time, Timescale
from skyfield.framelib import itrs


# Mean equatorial radius of Earth (WGS-84 reference, km)
WGS84_EARTH_RADIUS_KM = 6378.137

# -------------------------------------------------------------------------
# Observer Configuration — Multan, Pakistan
# Change these four constants to repoint the observer for any location.
# -------------------------------------------------------------------------
OBSERVER_NAME        = "Multan, Pakistan"
OBSERVER_LAT         = 30.1575    # degrees North
OBSERVER_LON         = 71.5249    # degrees East
OBSERVER_ELEV_M      = 122.0      # metres above WGS84 ellipsoid
ELEVATION_MASK_DEG   = 5.0        # minimum elevation for "visible"

# Nominal RAAN centers for the 6 GPS orbital planes (A through F)
PLANE_RAAN_CENTERS = [25.0, 85.0, 145.0, 205.0, 265.0, 325.0]
PLANE_NAMES = ["Plane A", "Plane B", "Plane C", "Plane D", "Plane E", "Plane F"]
PLANE_COLORS = [
    "#38bdf8",  # Plane A: Cyan / Sky Blue
    "#a855f7",  # Plane B: Neon Purple
    "#00ff88",  # Plane C: Emerald Mint
    "#f59e0b",  # Plane D: Warm Amber
    "#ec4899",  # Plane E: Radiant Pink
    "#818cf8",  # Plane F: Electric Indigo
]


class OrbitEngine:
    """
    Manages time progression, inertial coordinate transformations,
    and orbit ring precomputation for the GPS constellation.
    """

    def __init__(self, satellites: List[Dict]):
        """
        Initializes the engine with parsed GPS satellites.
        """
        self.satellites = satellites
        self.ts: Timescale = load.timescale()

    def get_time(self, base_datetime: datetime, offset_minutes: float = 0.0) -> Time:
        """
        Creates a Skyfield Time object from a UTC base datetime plus an offset.
        """
        sim_dt = base_datetime + timedelta(minutes=offset_minutes)
        if sim_dt.tzinfo is None:
            sim_dt = sim_dt.replace(tzinfo=timezone.utc)
        return self.ts.from_datetime(sim_dt)

    @staticmethod
    def assign_orbital_plane(raan_deg: float) -> Tuple[int, str, str]:
        """
        Clusters a satellite into one of the 6 GPS orbital planes (A-F)
        by its Right Ascension of Ascending Node (RAAN).
        """
        raan = raan_deg % 360.0
        angular_diffs = [
            min(abs(raan - c), 360.0 - abs(raan - c))
            for c in PLANE_RAAN_CENTERS
        ]
        plane_idx = int(np.argmin(angular_diffs))
        return plane_idx, PLANE_NAMES[plane_idx], PLANE_COLORS[plane_idx]

    def compute_orbit_ring(
        self,
        sat_obj: EarthSatellite,
        base_datetime: datetime,
        n_points: int = 360
    ) -> np.ndarray:
        """
        Computes one full closed orbital ring (~11h 58m) for a satellite
        in the GCRS INERTIAL frame.
        
        Returns:
            np.ndarray: shape (n_points, 3) coordinates in Three.js units (thousands of km).
        """
        if base_datetime.tzinfo is None:
            base_datetime = base_datetime.replace(tzinfo=timezone.utc)

        # Exact period from SGP4 mean motion (n in rad/min)
        period_min = 2.0 * np.pi / sat_obj.model.no_kozai
        offsets = np.linspace(0.0, period_min, n_points, endpoint=True)
        times = [base_datetime + timedelta(minutes=float(m)) for m in offsets]
        t_arr = self.ts.from_datetimes(times)

        # Inertial GCRS position: (3, n_points) in km
        gcrs_pos = sat_obj.at(t_arr).position.km

        # Convert to Three.js coordinates (units of 1,000 km):
        # Three.js +X = GCRS +X
        # Three.js +Y = GCRS +Z (North Celestial Pole is UP)
        # Three.js +Z = -GCRS +Y
        scale = 1.0 / 1000.0
        x_three = gcrs_pos[0] * scale
        y_three = gcrs_pos[2] * scale
        z_three = -gcrs_pos[1] * scale

        # Return (n_points, 3)
        return np.column_stack((x_three, y_three, z_three)).astype(np.float32)

    def precompute_inertial_simulation(
        self,
        base_datetime: datetime,
        duration_hours: float = 12.0,
        step_minutes: float = 1.0,
        ring_points: int = 360
    ) -> Dict:
        """
        Precomputes the entire 12-hour simulation in the GCRS INERTIAL frame
        in a single vectorized Skyfield call per satellite.
        
        Returns a JSON-serializable dictionary containing:
          - Earth rotation angles (GAST radians) per timestep
          - Satellite positions in Three.js coordinates (units = 1,000 km)
          - Closed orbit ring vertices per satellite
          - Sub-satellite geodetic coordinates (lat, lon, alt)
          - Orbital plane clustering and color coding
        """
        if base_datetime.tzinfo is None:
            base_datetime = base_datetime.replace(tzinfo=timezone.utc)

        offsets_min = np.arange(0, duration_hours * 60 + (step_minutes / 2.0), step_minutes)
        times = [base_datetime + timedelta(minutes=float(m)) for m in offsets_min]
        t_array = self.ts.from_datetimes(times)

        # Greenwich Apparent Sidereal Time (GAST) in radians for Earth mesh rotation
        gast_hours = t_array.gast
        gast_rad = (gast_hours * (np.pi / 12.0)).astype(np.float32)

        utc_labels = [
            (base_datetime + timedelta(minutes=float(m))).strftime("%Y-%m-%d %H:%M UTC")
            for m in offsets_min
        ]
        sim_labels = [f"+{int(m // 60):02d}:{int(m % 60):02d}" for m in offsets_min]

        num_sats = len(self.satellites)
        num_steps = len(offsets_min)
        scale = 1.0 / 1000.0

        satellites_data = []
        # Pre-allocate topocentric arrays: shape (num_sats, num_steps)
        el_deg_all = np.zeros((num_sats, num_steps), dtype=np.float32)
        az_deg_all = np.zeros((num_sats, num_steps), dtype=np.float32)

        # Skyfield observer object for Multan (vectorized altaz per satellite)
        observer = wgs84.latlon(OBSERVER_LAT, OBSERVER_LON, elevation_m=OBSERVER_ELEV_M)

        for sat_idx, s_meta in enumerate(self.satellites):
            sat_obj: EarthSatellite = s_meta["skyfield_sat"]
            raan_deg = float(np.degrees(sat_obj.model.nodeo) % 360.0)
            plane_idx, plane_name, plane_color = self.assign_orbital_plane(raan_deg)

            # 1. Closed orbit ring in GCRS
            ring_coords = self.compute_orbit_ring(sat_obj, base_datetime, n_points=ring_points)

            # 2. Vectorized 12-hour propagation in GCRS
            geo = sat_obj.at(t_array)
            gcrs_pos = geo.position.km  # (3, num_steps)

            # Three.js coordinates: (num_steps, 3)
            x_three = (gcrs_pos[0] * scale).astype(np.float32)
            y_three = (gcrs_pos[2] * scale).astype(np.float32)
            z_three = (-gcrs_pos[1] * scale).astype(np.float32)
            positions = np.column_stack((x_three, y_three, z_three)).round(4).tolist()

            # 3. Exact Sub-satellite coordinates from WGS84 ellipsoid
            sub = wgs84.subpoint(geo)
            sub_lats = np.round(sub.latitude.degrees, 2)
            sub_lons = np.round(sub.longitude.degrees, 2)
            sub_alts = np.round(sub.elevation.km, 1)
            subpoints = np.column_stack((sub_lats, sub_lons, sub_alts)).tolist()

            # 4. Topocentric elevation and azimuth from Multan observer (vectorized)
            diff = sat_obj - observer
            topoc = diff.at(t_array)
            alt_res, az_res, _ = topoc.altaz()
            el_deg_all[sat_idx] = alt_res.degrees.astype(np.float32)
            az_deg_all[sat_idx] = az_res.degrees.astype(np.float32)

            satellites_data.append({
                "prn": s_meta["prn"],
                "norad_id": s_meta["norad_id"],
                "name": s_meta["name"],
                "display_name": s_meta["display_name"],
                "block_type": s_meta["block_type"],
                "plane_index": plane_idx,
                "plane_name": plane_name,
                "color": plane_color,
                "ring_points": ring_coords.round(4).tolist(),
                "positions": positions,
                "subpoints": subpoints,
            })

        return {
            "base_datetime_iso": base_datetime.isoformat(),
            "num_steps": num_steps,
            "step_minutes": float(step_minutes),
            "duration_hours": float(duration_hours),
            "offsets_min": offsets_min.tolist(),
            "gast_rad": np.round(gast_rad, 5).tolist(),
            "utc_labels": utc_labels,
            "sim_labels": sim_labels,
            "satellites": satellites_data,
            "earth_radius_three": round(WGS84_EARTH_RADIUS_KM * scale, 4),  # ~6.3781
            "observer": {
                "name": OBSERVER_NAME,
                "lat": OBSERVER_LAT,
                "lon": OBSERVER_LON,
                "elevation_m": OBSERVER_ELEV_M,
                "elevation_mask_deg": ELEVATION_MASK_DEG,
            },
            # (num_sats, num_steps) — topocentric elevation and azimuth from Multan
            "el_deg": np.round(el_deg_all, 2).tolist(),
            "az_deg": np.round(az_deg_all, 2).tolist(),
        }

    def propagate_constellation(
        self,
        t: Time,
        observer_lat: float = 30.1575,
        observer_lon: float = 71.5249,
        observer_elev_m: float = 122.0,
        mask_angle_deg: float = 5.0
    ) -> List[Dict]:
        """
        Backwards-compatible propagation helper.
        """
        observer = wgs84.latlon(observer_lat, observer_lon, elevation_m=observer_elev_m)
        results = []

        for sat_meta in self.satellites:
            sat_obj: EarthSatellite = sat_meta["skyfield_sat"]
            try:
                geocentric = sat_obj.at(t)
                subpoint = wgs84.subpoint(geocentric)
                lat = subpoint.latitude.degrees
                lon = subpoint.longitude.degrees
                alt_km = subpoint.elevation.km

                r_km = WGS84_EARTH_RADIUS_KM + alt_km
                lat_rad = np.radians(lat)
                lon_rad = np.radians(lon)

                x_ecef = r_km * np.cos(lat_rad) * np.cos(lon_rad)
                y_ecef = r_km * np.cos(lat_rad) * np.sin(lon_rad)
                z_ecef = r_km * np.sin(lat_rad)

                difference = sat_obj - observer
                topocentric = difference.at(t)
                alt, az, distance = topocentric.altaz()

                results.append({
                    "name": sat_meta["name"],
                    "display_name": sat_meta["display_name"],
                    "prn": sat_meta["prn"],
                    "norad_id": sat_meta["norad_id"],
                    "block_type": sat_meta["block_type"],
                    "x_ecef": float(x_ecef),
                    "y_ecef": float(y_ecef),
                    "z_ecef": float(z_ecef),
                    "radius_km": float(r_km),
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "altitude_km": float(alt_km),
                    "azimuth_deg": float(az.degrees),
                    "elevation_deg": float(alt.degrees),
                    "slant_range_km": float(distance.km),
                    "is_visible": bool(alt.degrees >= mask_angle_deg),
                })
            except Exception:
                continue

        return results
