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

    def precompute_simulation(
        self,
        base_datetime: datetime,
        duration_hours: float = 12.0,
        step_minutes: float = 2.0,
        observer_lat: float = DEFAULT_OBSERVER_LAT,
        observer_lon: float = DEFAULT_OBSERVER_LON,
        observer_elev_m: float = DEFAULT_OBSERVER_ELEV_M,
        mask_angle_deg: float = DEFAULT_ELEVATION_MASK_DEG
    ) -> Dict:
        """
        Precomputes all orbital parameters for all satellites across the entire
        simulation window in a single vectorized Skyfield call per satellite.

        Stores results as plain NumPy arrays (pickle-serializable for st.cache_data):
          - ECEF Cartesian (x, y, z)
          - Geodetic subpoint (lat, lon, alt)
          - Topocentric receiver angles (azimuth, elevation, slant range)
          - Cartesian sky-plot projections (cart_x, cart_y)
          - Visibility masks and decimated 12h ground track trails
        """
        if base_datetime.tzinfo is None:
            base_datetime = base_datetime.replace(tzinfo=timezone.utc)

        offsets_min = np.arange(0, duration_hours * 60 + (step_minutes / 2.0), step_minutes)
        times = [base_datetime + timedelta(minutes=float(m)) for m in offsets_min]
        t_array = self.ts.from_datetimes(times)
        observer = self.create_observer(observer_lat, observer_lon, observer_elev_m)

        num_sats = len(self.satellites)
        num_steps = len(offsets_min)

        x_ecef = np.empty((num_sats, num_steps), dtype=np.float32)
        y_ecef = np.empty((num_sats, num_steps), dtype=np.float32)
        z_ecef = np.empty((num_sats, num_steps), dtype=np.float32)
        lat = np.empty((num_sats, num_steps), dtype=np.float32)
        lon = np.empty((num_sats, num_steps), dtype=np.float32)
        alt_km = np.empty((num_sats, num_steps), dtype=np.float32)
        az = np.empty((num_sats, num_steps), dtype=np.float32)
        el = np.empty((num_sats, num_steps), dtype=np.float32)
        dist_km = np.empty((num_sats, num_steps), dtype=np.float32)

        sat_meta_list = []
        for i, s_meta in enumerate(self.satellites):
            sat_obj = s_meta["skyfield_sat"]
            sat_meta_list.append({
                "prn": s_meta["prn"],
                "norad_id": s_meta["norad_id"],
                "name": s_meta["name"],
                "display_name": s_meta["display_name"],
                "block_type": s_meta["block_type"],
            })

            # Vectorized Skyfield call for this satellite across the entire time array
            geo = sat_obj.at(t_array)
            sub = wgs84.subpoint(geo)

            lat_vals = sub.latitude.degrees
            lon_vals = sub.longitude.degrees
            alt_vals = sub.elevation.km

            lat[i] = lat_vals
            lon[i] = lon_vals
            alt_km[i] = alt_vals

            # 3D Cartesian coordinates in ECEF frame (km)
            r_km = WGS84_EARTH_RADIUS_KM + alt_vals
            lat_rad = np.radians(lat_vals)
            lon_rad = np.radians(lon_vals)
            x_ecef[i] = r_km * np.cos(lat_rad) * np.cos(lon_rad)
            y_ecef[i] = r_km * np.cos(lat_rad) * np.sin(lon_rad)
            z_ecef[i] = r_km * np.sin(lat_rad)

            # Topocentric calculation relative to ground observer (Azimuth, Elevation, Range)
            diff = sat_obj - observer
            topoc = diff.at(t_array)
            alt_res, az_res, d_res = topoc.altaz()
            el[i] = alt_res.degrees
            az[i] = az_res.degrees
            dist_km[i] = d_res.km

        is_visible = (el >= mask_angle_deg)

        # Cartesian projection for Sky Plot (Item 5)
        # x = (90 - el) * sin(az), y = (90 - el) * cos(az)
        az_rad = np.radians(az)
        r_sky = 90.0 - el
        cart_x = r_sky * np.sin(az_rad)
        cart_y = r_sky * np.cos(az_rad)

        # Formatted step labels for Plotly animation slider
        time_labels = []
        slider_labels = []
        for m in offsets_min:
            h = int(m // 60)
            mins = int(m % 60)
            time_labels.append(f"+{h:02d}:{mins:02d}")
            slider_labels.append(f"+{h}h" if mins == 0 else f"+{h}h {mins:02d}m")

        # Decimated ground tracks (Item 4: roughly every 5th point)
        decimation_stride = max(1, int(round(5 * (2.0 / step_minutes))))
        ground_tracks = {}
        for i, s_meta in enumerate(self.satellites):
            s_lats = lat[i, ::decimation_stride]
            s_lons = lon[i, ::decimation_stride]

            clean_lats = []
            clean_lons = []
            for j in range(len(s_lons)):
                if j > 0 and abs(s_lons[j] - s_lons[j - 1]) > 180.0:
                    clean_lats.append(None)
                    clean_lons.append(None)
                clean_lats.append(float(s_lats[j]))
                clean_lons.append(float(s_lons[j]))

            ground_tracks[s_meta["display_name"]] = {
                "lats": clean_lats,
                "lons": clean_lons,
                "prn": s_meta["prn"]
            }

        return {
            "x_ecef": x_ecef,
            "y_ecef": y_ecef,
            "z_ecef": z_ecef,
            "lat": lat,
            "lon": lon,
            "alt_km": alt_km,
            "az": az,
            "el": el,
            "dist_km": dist_km,
            "is_visible": is_visible,
            "cart_x": cart_x,
            "cart_y": cart_y,
            "offsets_min": offsets_min,
            "time_labels": time_labels,
            "slider_labels": slider_labels,
            "ground_tracks": ground_tracks,
            "satellites": sat_meta_list,
            "num_sats": num_sats,
            "num_steps": num_steps,
            "base_datetime_iso": base_datetime.isoformat(),
            "observer_lat": observer_lat,
            "observer_lon": observer_lon,
            "observer_elev_m": observer_elev_m,
            "mask_angle_deg": mask_angle_deg,
            "step_minutes": step_minutes,
            "duration_hours": duration_hours,
        }

