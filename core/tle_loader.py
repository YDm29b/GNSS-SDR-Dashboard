"""
core/tle_loader.py
==================
Module for ingesting and parsing Two-Line Element (TLE) ephemeris data
for the operational GPS (Navstar) satellite constellation.

Data Source:
  CelesTrak (https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle)
  With automatic offline fallback to local cached copy: 'data/gps_operational.tle'.

Orbital Mechanics Context for Supervisor Defense:
  TLE data format encodes Keplerian orbital elements (inclination, RAAN,
  eccentricity, argument of perigee, mean anomaly, mean motion) plus SGP4
  ballistic drag coefficients (BSTAR). These are input parameters for the
  Simplified General Perturbations-4 (SGP4) analytic propagator.
"""

import os
import re
from typing import List, Dict, Tuple, Optional
import httpx
from skyfield.api import EarthSatellite, Timescale, load


CELESTRAK_GPS_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=gps-ops&FORMAT=tle"
DEFAULT_LOCAL_TLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "gps_operational.tle")


def fetch_or_load_tle(
    tle_url: str = CELESTRAK_GPS_URL,
    local_path: str = DEFAULT_LOCAL_TLE,
    force_offline: bool = False
) -> Tuple[str, str]:
    """
    Retrieves TLE text either by fetching live from CelesTrak or reading
    the local cached fallback file.

    Returns:
        tuple (tle_text: str, source_description: str)
    """
    os.makedirs(os.path.dirname(local_path), exist_ok=True)

    if not force_offline:
        try:
            # Attempt live fetch with a short timeout so user is not blocked
            response = httpx.get(tle_url, timeout=8.0, follow_redirects=True)
            if response.status_code == 200 and len(response.text.strip()) > 100:
                tle_text = response.text
                # Cache to local file for future offline usage
                try:
                    with open(local_path, "w", encoding="utf-8") as f:
                        f.write(tle_text)
                except Exception:
                    pass
                return tle_text, f"Live CelesTrak Feed ({tle_url})"
        except Exception as e:
            # Network failed; proceed to offline fallback
            pass

    # Offline fallback
    if os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            tle_text = f.read()
        return tle_text, f"Local TLE Cache ({os.path.basename(local_path)})"

    raise RuntimeError(
        f"Unable to fetch live TLE and local fallback file '{local_path}' does not exist."
    )


def extract_prn_and_block(satellite_name: str) -> Tuple[Optional[int], str]:
    """
    Extracts the PRN (Pseudo-Random Noise) identifier and GPS Block model
    from the standardized CelesTrak satellite title.
    
    Examples:
      'GPS BIIR-5  (PRN 22)'  -> PRN: 22, Block: 'BIIR-5'
      'GPS BIIF-1  (PRN 25)'  -> PRN: 25, Block: 'BIIF-1'
      'GPS BIII-3  (PRN 14)'  -> PRN: 14, Block: 'BIII-3'
    """
    prn = None
    prn_match = re.search(r"PRN\s*0?(\d+)", satellite_name, re.IGNORECASE)
    if prn_match:
        prn = int(prn_match.group(1))

    # Identify block generation (BIIR, BIIRM, BIIF, BIII)
    block_type = "GPS (Unknown)"
    if "BIII" in satellite_name:
        block_type = "Block III"
    elif "BIIRM" in satellite_name:
        block_type = "Block IIR-M"
    elif "BIIR" in satellite_name:
        block_type = "Block IIR"
    elif "BIIF" in satellite_name:
        block_type = "Block IIF"
    elif "NAVSTAR" in satellite_name:
        block_type = "NAVSTAR"

    return prn, block_type


def parse_gps_satellites(
    tle_text: str,
    ts: Timescale
) -> List[Dict]:
    """
    Parses raw 3-line or 2-line TLE blocks into Skyfield EarthSatellite objects
    and extracts metadata (PRN, NORAD ID, Block Type, Epoch).
    """
    lines = [line.strip() for line in tle_text.strip().splitlines() if line.strip()]
    satellites = []

    i = 0
    while i < len(lines):
        # Case A: 3-line format (Line 0 = Name, Line 1 = TLE 1, Line 2 = TLE 2)
        if lines[i].startswith("1 ") and i + 1 < len(lines) and lines[i + 1].startswith("2 "):
            sat_name = f"GPS-SAT-{lines[i][2:7].strip()}"
            line1 = lines[i]
            line2 = lines[i + 1]
            i += 2
        elif i + 2 < len(lines) and lines[i + 1].startswith("1 ") and lines[i + 2].startswith("2 "):
            sat_name = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]
            i += 3
        else:
            i += 1
            continue

        try:
            # Instantiate Skyfield EarthSatellite (wraps standard SGP4)
            sat_obj = EarthSatellite(line1, line2, sat_name, ts)
            norad_id = sat_obj.model.satnum
            prn, block_type = extract_prn_and_block(sat_name)
            
            # If PRN was not in title, use NORAD ID as reference
            prn_display = f"PRN {prn:02d}" if prn is not None else f"NORAD {norad_id}"

            satellites.append({
                "name": sat_name,
                "display_name": prn_display,
                "prn": prn,
                "norad_id": norad_id,
                "block_type": block_type,
                "epoch_year": sat_obj.epoch.utc_datetime().year,
                "epoch_str": sat_obj.epoch.utc_iso(),
                "skyfield_sat": sat_obj,
            })
        except Exception:
            continue

    # Sort primarily by PRN number if available, then by NORAD ID
    satellites.sort(key=lambda s: (s["prn"] if s["prn"] is not None else 999, s["norad_id"]))
    return satellites
