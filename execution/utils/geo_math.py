"""
Geographic math utilities — ALL geo calculations live here.
No other file should implement haversine, bearing, or coordinate math.

Uses WGS84 with Earth radius 6371 km.
"""

import math

EARTH_RADIUS_KM = 6371.0

DIRECTION_BEARINGS: dict[str, float] = {
    "north": 0.0,
    "n": 0.0,
    "northeast": 45.0,
    "ne": 45.0,
    "east": 90.0,
    "e": 90.0,
    "southeast": 135.0,
    "se": 135.0,
    "south": 180.0,
    "s": 180.0,
    "southwest": 225.0,
    "sw": 225.0,
    "west": 270.0,
    "w": 270.0,
    "northwest": 315.0,
    "nw": 315.0,
}


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in kilometers between two points using the haversine formula."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing in degrees (0=North, 90=East) from point 1 to point 2."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlon_r = math.radians(lon2 - lon1)

    x = math.sin(dlon_r) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(
        lat2_r
    ) * math.cos(dlon_r)

    return normalize_bearing(math.degrees(math.atan2(x, y)))


def destination_point(
    lat: float, lon: float, bearing_deg: float, distance_km: float
) -> tuple[float, float]:
    """Given a start point, bearing, and distance, return the destination (lat, lon).

    Uses the proper spherical (inverse haversine) formula.
    Critical for waypoint placement at high latitudes like Denmark (56°N)
    where longitude degrees are compressed.
    """
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    brng_r = math.radians(bearing_deg)
    d_over_r = distance_km / EARTH_RADIUS_KM

    lat2_r = math.asin(
        math.sin(lat_r) * math.cos(d_over_r)
        + math.cos(lat_r) * math.sin(d_over_r) * math.cos(brng_r)
    )
    lon2_r = lon_r + math.atan2(
        math.sin(brng_r) * math.sin(d_over_r) * math.cos(lat_r),
        math.cos(d_over_r) - math.sin(lat_r) * math.sin(lat2_r),
    )

    return (math.degrees(lat2_r), math.degrees(lon2_r))


def direction_to_bearing(direction: str) -> float:
    """Map compass direction string to degrees.

    Accepts: 'north', 'northeast', 'east', etc. and abbreviations 'n', 'ne', 'e', etc.
    Raises ValueError for unknown directions.
    """
    key = direction.strip().lower()
    if key not in DIRECTION_BEARINGS:
        raise ValueError(
            f"Unknown direction '{direction}'. "
            f"Valid: {', '.join(sorted(DIRECTION_BEARINGS.keys()))}"
        )
    return DIRECTION_BEARINGS[key]


def normalize_bearing(b: float) -> float:
    """Normalize bearing to 0–360 range."""
    return b % 360.0


def bearing_difference(b1: float, b2: float) -> float:
    """Signed shortest angular difference between two bearings, in range -180 to 180."""
    diff = (b2 - b1 + 180) % 360 - 180
    return diff


def polyline_distance(coords: list[tuple[float, float]]) -> float:
    """Total distance in km along a polyline of (lat, lon) points."""
    total = 0.0
    for i in range(len(coords) - 1):
        total += haversine(coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1])
    return total


def is_in_direction(
    start_lat: float,
    start_lon: float,
    point_lat: float,
    point_lon: float,
    target_direction: str,
    tolerance_deg: float = 67.5,
) -> bool:
    """Check if point is within tolerance of the target direction from start."""
    actual = bearing(start_lat, start_lon, point_lat, point_lon)
    target = direction_to_bearing(target_direction)
    return abs(bearing_difference(target, actual)) <= tolerance_deg
