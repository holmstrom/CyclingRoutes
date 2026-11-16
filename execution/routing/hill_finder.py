"""
Find hills/climbs in an area matching minimum elevation criteria.

Samples a grid of points, fetches elevations, and identifies local maxima.
"""

import logging

from execution.elevation.provider import get_elevation_batch
from execution.utils.geo_math import destination_point, haversine

logger = logging.getLogger(__name__)


def find_hills(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    min_elevation_gain: float = 50.0,
    sample_points: int = 50,
) -> list[dict]:
    """Find hills in the area by sampling elevations on a grid.

    Args:
        center_lat: Center of search area.
        center_lon: Center of search area.
        radius_km: Radius to search within.
        min_elevation_gain: Minimum elevation difference to qualify as a hill.
        sample_points: Number of grid points to sample.

    Returns:
        List of hill candidates sorted by estimated_gain descending:
        [{'lat': float, 'lon': float, 'elevation': float, 'estimated_gain': float}]
    """
    # Generate grid of sample points
    grid_size = int(sample_points**0.5)
    if grid_size < 3:
        grid_size = 3

    coords = []
    step_km = (radius_km * 2) / (grid_size - 1)

    for i in range(grid_size):
        for j in range(grid_size):
            # Calculate offset from center
            ns_offset = (i - grid_size / 2) * step_km
            ew_offset = (j - grid_size / 2) * step_km

            # Move north/south then east/west
            lat, lon = destination_point(center_lat, center_lon, 0, ns_offset)
            lat, lon = destination_point(lat, lon, 90, ew_offset)

            # Only include points within the radius
            if haversine(center_lat, center_lon, lat, lon) <= radius_km:
                coords.append((lat, lon))

    if not coords:
        return []

    # Fetch elevations
    try:
        elevations = get_elevation_batch(coords)
    except Exception as e:
        logger.warning("Failed to fetch elevations for hill finding: %s", e)
        return []

    if not elevations or all(e == 0 for e in elevations):
        return []

    # Build coordinate-elevation pairs
    points = list(zip(coords, elevations))
    mean_elevation = sum(elevations) / len(elevations)

    # Find local maxima: points higher than their neighbors
    hills = []
    for idx, ((lat, lon), elev) in enumerate(points):
        # Find nearest neighbors (within 2 * step_km)
        neighbor_elevs = []
        for other_idx, ((olat, olon), oelev) in enumerate(points):
            if other_idx == idx:
                continue
            dist = haversine(lat, lon, olat, olon)
            if dist <= step_km * 2.5:
                neighbor_elevs.append(oelev)

        if not neighbor_elevs:
            continue

        neighbor_mean = sum(neighbor_elevs) / len(neighbor_elevs)
        gain = elev - neighbor_mean

        if gain >= min_elevation_gain * 0.5:
            hills.append({
                "lat": lat,
                "lon": lon,
                "elevation": elev,
                "estimated_gain": round(gain, 1),
            })

    # Sort by estimated gain descending
    hills.sort(key=lambda h: h["estimated_gain"], reverse=True)
    return hills
