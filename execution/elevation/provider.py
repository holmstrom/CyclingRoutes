"""
Fetch elevation data from Open-Meteo (fast, free, no API key required).

Open-Meteo elevation API: GET https://api.open-meteo.com/v1/elevation
Accepts up to 100 lat/lon pairs per request, returns meters above sea level.
"""

import logging

import requests

from execution.utils.geo_math import haversine

logger = logging.getLogger(__name__)

API_URL = "https://api.open-meteo.com/v1/elevation"
BATCH_SIZE = 100
TIMEOUT = 10          # Open-Meteo is fast; fail quickly if unavailable
MAX_SAMPLE_POINTS = 200


def get_elevation_batch(coords: list[tuple[float, float]]) -> list[float]:
    """Fetch elevation in meters for each coordinate via Open-Meteo.

    Batches into groups of BATCH_SIZE (max 100 per request).
    Returns 0.0 for any failed lookups.
    """
    if not coords:
        return []

    elevations: list[float] = []

    for i in range(0, len(coords), BATCH_SIZE):
        batch = coords[i : i + BATCH_SIZE]
        lats = ",".join(str(lat) for lat, lon in batch)
        lons = ",".join(str(lon) for lat, lon in batch)

        try:
            response = requests.get(
                API_URL,
                params={"latitude": lats, "longitude": lons},
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            results = response.json().get("elevation", [])
            # Open-Meteo may return None for ocean/no-data points
            elevations.extend(float(e) if e is not None else 0.0 for e in results)
        except Exception as e:
            logger.warning("Elevation API failed for batch %d: %s", i // BATCH_SIZE, e)
            elevations.extend([0.0] * len(batch))

    return elevations


def get_elevation_profile(
    coords: list[tuple[float, float]],
) -> dict:
    """Get full elevation profile for a route.

    Samples every Nth point (max MAX_SAMPLE_POINTS API calls) and
    interpolates back to the full coordinate list.

    Returns:
        {
            'elevations': [float, ...],  # one per input coord
            'elevation_gain': float,
            'elevation_loss': float,
            'min_elevation': float,
            'max_elevation': float,
            'profile': [{'lat', 'lon', 'elevation', 'distance_km'}, ...],
        }
    """
    if not coords:
        return _empty_profile()

    n = len(coords)
    if n > MAX_SAMPLE_POINTS:
        step = max(1, n // MAX_SAMPLE_POINTS)
        sample_indices = list(range(0, n, step))
        if sample_indices[-1] != n - 1:
            sample_indices.append(n - 1)
        sampled_coords = [coords[i] for i in sample_indices]
    else:
        sample_indices = list(range(n))
        sampled_coords = list(coords)

    sampled_elevations = get_elevation_batch(sampled_coords)
    elevations = _interpolate_elevations(n, sample_indices, sampled_elevations)

    # Cumulative distances
    cum_distances = [0.0]
    for i in range(1, n):
        d = haversine(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
        cum_distances.append(cum_distances[-1] + d)

    # Gain / loss
    gain = loss = 0.0
    for i in range(1, len(elevations)):
        diff = elevations[i] - elevations[i - 1]
        if diff > 0:
            gain += diff
        else:
            loss += abs(diff)

    # Sampled profile for chart display
    profile_step = max(1, n // MAX_SAMPLE_POINTS)
    profile = [
        {
            "lat": coords[i][0],
            "lon": coords[i][1],
            "elevation": round(elevations[i], 1),
            "distance_km": round(cum_distances[i], 2),
        }
        for i in range(0, n, profile_step)
    ]
    if profile[-1]["distance_km"] != round(cum_distances[-1], 2):
        profile.append({
            "lat": coords[-1][0],
            "lon": coords[-1][1],
            "elevation": round(elevations[-1], 1),
            "distance_km": round(cum_distances[-1], 2),
        })

    valid_elevations = [e for e in elevations if e != 0]
    return {
        "elevations": elevations,
        "elevation_gain": round(gain, 1),
        "elevation_loss": round(loss, 1),
        "min_elevation": round(min(valid_elevations), 1) if valid_elevations else 0.0,
        "max_elevation": round(max(valid_elevations), 1) if valid_elevations else 0.0,
        "profile": profile,
    }


def _interpolate_elevations(
    n: int,
    sample_indices: list[int],
    sampled_elevations: list[float],
) -> list[float]:
    """Linearly interpolate elevations for non-sampled points."""
    if n == len(sample_indices):
        return sampled_elevations

    elevations = [0.0] * n
    for idx, elev in zip(sample_indices, sampled_elevations):
        elevations[idx] = elev

    for k in range(len(sample_indices) - 1):
        i_start = sample_indices[k]
        i_end = sample_indices[k + 1]
        e_start = sampled_elevations[k]
        e_end = sampled_elevations[k + 1]
        for i in range(i_start + 1, i_end):
            frac = (i - i_start) / (i_end - i_start)
            elevations[i] = e_start + frac * (e_end - e_start)

    return elevations


def _empty_profile() -> dict:
    return {
        "elevations": [],
        "elevation_gain": 0.0,
        "elevation_loss": 0.0,
        "min_elevation": 0.0,
        "max_elevation": 0.0,
        "profile": [],
    }
