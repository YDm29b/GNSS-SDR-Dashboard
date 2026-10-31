"""
core/orbit_engine.py
====================
Core orbital mechanics engine executing SGP4 propagation via Skyfield.
Transforms satellite positions across reference frames:
  TEME (True Equator, Mean Equinox) -> ITRS / ECEF (Earth-Centered Earth-Fixed)
  -> WGS84 Geodetic (Lat, Lon, Alt)
  -> Topocentric SEZ / Horizon (Azimuth, Elevation, Slant Range)

Physics Context:
  - Constellation: 31-32 operational satellites in Medium Earth Orbit (MEO).
  - Semi-major axis (a) ~ 26,560 km (orbital radius from Earth's center).
  - Nominal orbital altitude (h) ~ 20,180 - 20,200 km above WGS84 ellipsoid.
  - Orbital period (T) ~ 11 hours 58 minutes (half a sidereal day, repeating ground track).
  - Nominal inclination (i) ~ 55 degrees across 6 orbital planes (A through F).
"""

from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np
from skyfield.api import load, wgs84, EarthSatellite, Time, Timescale


# Mean equatorial radius of Earth (WGS-84 reference)
WGS84_EARTH_RADIUS_KM = 6378.137

# Default observer: Multan, Punjab, Pakistan
DEFAULT_OBSERVER_LAT = 30.1575
DEFAULT_OBSERVER_LON = 71.5249
DEFAULT_OBSERVER_ELEV_M = 122.0
DEFAULT_ELEVATION_MASK_DEG = 5.0


class OrbitEngine:
    """
    Manages time progression and multi-frame coordinate transformations
    for the GPS constellation.
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

    def create_observer(
        self,
        lat_deg: float = DEFAULT_OBSERVER_LAT,
        lon_deg: float = DEFAULT_OBSERVER_LON,
        elev_m: float = DEFAULT_OBSERVER_ELEV_M
    ):
        """
        Constructs a WGS84 geographic observer location.
        """
        return wgs84.latlon(lat_deg, lon_deg, elevation_m=elev_m)

    def propagate_constellation(
        self,
        t: Time,
        observer_lat: float = DEFAULT_OBSERVER_LAT,
        observer_lon: float = DEFAULT_OBSERVER_LON,
        observer_elev_m: float = DEFAULT_OBSERVER_ELEV_M,
        mask_angle_deg: float = DEFAULT_ELEVATION_MASK_DEG
    ) -> List[Dict]:
        """
        Propagates all satellites in the constellation to time t.
        Computes 3D Cartesian ECEF, 2D Geodetic Sub-satellite points,
        and Observer Topocentric coordinates (Azimuth, Elevation, Range).
        """
        observer = self.create_observer(observer_lat, observer_lon, observer_elev_m)
        results = []

        for sat_meta in self.satellites:
            sat_obj: EarthSatellite = sat_meta["skyfield_sat"]

            try:
                # 1. Geocentric position at time t
                geocentric = sat_obj.at(t)

                # 2. Sub-satellite point on WGS84 Ellipsoid (Latitude, Longitude, Altitude)
                subpoint = wgs84.subpoint(geocentric)
                lat = subpoint.latitude.degrees
                lon = subpoint.longitude.degrees
                alt_km = subpoint.elevation.km

                # 3. 3D Cartesian coordinates in ECEF (Earth-Centered Earth-Fixed) frame
                # Radius from Earth center: r = R_E + altitude
                r_km = WGS84_EARTH_RADIUS_KM + alt_km
                lat_rad = np.radians(lat)
                lon_rad = np.radians(lon)

                x_ecef = r_km * np.cos(lat_rad) * np.cos(lon_rad)
                y_ecef = r_km * np.cos(lat_rad) * np.sin(lon_rad)
                z_ecef = r_km * np.sin(lat_rad)

                # 4. Topocentric calculation relative to ground observer (Azimuth, Elevation, Distance)
                difference = sat_obj - observer
                topocentric = difference.at(t)
                alt, az, distance = topocentric.altaz()

                elevation_deg = alt.degrees
                azimuth_deg = az.degrees
                slant_range_km = distance.km
                is_visible = elevation_deg >= mask_angle_deg

                results.append({
                    "name": sat_meta["name"],
                    "display_name": sat_meta["display_name"],
                    "prn": sat_meta["prn"],
                    "norad_id": sat_meta["norad_id"],
                    "block_type": sat_meta["block_type"],
                    # 3D ECEF position in km
                    "x_ecef": float(x_ecef),
                    "y_ecef": float(y_ecef),
                    "z_ecef": float(z_ecef),
                    "radius_km": float(r_km),
                    # 2D Sub-satellite geodetic coordinates
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "altitude_km": float(alt_km),
                    # Topocentric coordinates (Observer)
                    "azimuth_deg": float(azimuth_deg),
                    "elevation_deg": float(elevation_deg),
                    "slant_range_km": float(slant_range_km),
                    "is_visible": bool(is_visible),
                })
            except Exception:
                continue

        return results

    def compute_ground_track_history(
        self,
        base_time: datetime,
        duration_hours: float = 11.97,  # ~1 GPS orbital period (11h 58m)
        step_minutes: float = 8.0,
        selected_prns: Optional[List[int]] = None
    ) -> Dict[str, Dict[str, List[float]]]:
        """
        Computes ground track points (lat, lon) over an entire orbital period
        for plotting orbital ground tracks on the 2D world map.
        
        Splits paths across the +/-180 meridian to prevent horizontal line artifacts.
        """
        n_steps = int((duration_hours * 60) / step_minutes) + 1
        time_offsets = np.linspace(0, duration_hours * 60, n_steps)

        tracks = {}
        for sat_meta in self.satellites:
            prn = sat_meta["prn"]
            if selected_prns is not None and prn not in selected_prns:
                continue

            sat_obj = sat_meta["skyfield_sat"]
            display_name = sat_meta["display_name"]

            lats = []
            lons = []

            for offset in time_offsets:
                t = self.get_time(base_time, offset)
                try:
                    geo = sat_obj.at(t)
                    sub = wgs84.subpoint(geo)
                    lats.append(float(sub.latitude.degrees))
                    lons.append(float(sub.longitude.degrees))
                except Exception:
                    pass

            # Insert None values when crossing antimeridian (-180 / +180)
            clean_lats = []
            clean_lons = []
            for j in range(len(lons)):
                if j > 0 and abs(lons[j] - lons[j - 1]) > 180:
                    clean_lats.append(None)
                    clean_lons.append(None)
                clean_lats.append(lats[j])
                clean_lons.append(lons[j])

            tracks[display_name] = {
                "lats": clean_lats,
                "lons": clean_lons,
                "prn": prn
            }

        return tracks
