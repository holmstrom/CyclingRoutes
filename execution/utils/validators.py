"""
Route validation utilities.

Validates loop closure, distance accuracy, overlap, road breakdown, and quality scoring.
"""

import networkx as nx

from execution.utils.geo_math import bearing, bearing_difference, haversine, polyline_distance


def validate_loop_closure(
    coords: list[tuple[float, float]], max_gap_m: float = 100.0
) -> bool:
    """Check that first and last points are within max_gap_m meters."""
    if len(coords) < 2:
        return False
    gap_km = haversine(coords[0][0], coords[0][1], coords[-1][0], coords[-1][1])
    return gap_km * 1000 <= max_gap_m


def validate_distance(
    actual_km: float, target_km: float, tolerance: float = 0.15
) -> bool:
    """Check that actual distance is within ±tolerance of target."""
    if target_km <= 0:
        return False
    lower = target_km * (1 - tolerance)
    upper = target_km * (1 + tolerance)
    return lower <= actual_km <= upper


def calculate_overlap_percent(edge_sequence: list[tuple[int, int]]) -> float:
    """Calculate what percentage of edges appear more than once.

    Treats (u, v) and (v, u) as the same edge (undirected).
    Returns percentage 0–100.
    """
    if not edge_sequence:
        return 0.0

    # Normalize to sorted tuples for undirected comparison
    normalized = [tuple(sorted(e)) for e in edge_sequence]
    unique = set(normalized)
    total = len(normalized)

    if total == 0:
        return 0.0

    repeated = total - len(unique)
    return (repeated / total) * 100


def calculate_road_breakdown(
    G: nx.MultiDiGraph, edge_sequence: list[tuple[int, int]]
) -> dict[str, float]:
    """Calculate road type breakdown as percentage of total distance.

    Returns dict mapping road type to percentage, e.g.:
        {'residential': 35.2, 'tertiary': 28.1, 'secondary': 20.0, ...}
    """
    type_distance: dict[str, float] = {}
    total_distance = 0.0

    for u, v in edge_sequence:
        edge_data = G.get_edge_data(u, v)
        if edge_data is None:
            continue
        # MultiDiGraph: get first edge (key=0)
        data = edge_data.get(0, next(iter(edge_data.values()), {}))
        length = data.get("length", 0)
        highway = data.get("highway", "unknown")

        # Handle list values from simplified edges
        if isinstance(highway, list):
            highway = highway[0]

        type_distance[highway] = type_distance.get(highway, 0) + length
        total_distance += length

    if total_distance == 0:
        return {}

    return {
        road_type: round((dist / total_distance) * 100, 1)
        for road_type, dist in sorted(
            type_distance.items(), key=lambda x: x[1], reverse=True
        )
    }


def calculate_straightness(coords: list[tuple[float, float]]) -> float:
    """Calculate route straightness as ratio of direct distance to total distance.

    Returns 0.0–1.0 where lower = more winding (better for cycling).
    A perfectly straight out-and-back would be close to 0 (since it's a loop).
    For loops, we use the ratio of max distance from start to total distance.
    """
    if len(coords) < 3:
        return 1.0

    start = coords[0]
    max_distance = 0.0
    for lat, lon in coords:
        d = haversine(start[0], start[1], lat, lon)
        if d > max_distance:
            max_distance = d

    total = polyline_distance(coords)
    if total == 0:
        return 1.0

    # For a circle: max_dist/total ≈ 1/pi ≈ 0.32
    # For an elongated loop: ≈ 0.25–0.30
    # For a very straight out-and-back: ≈ 0.5
    return max_distance / total


def calculate_long_straight_segments(
    coords: list[tuple[float, float]], min_length_km: float = 2.0, max_bearing_change: float = 10.0
) -> int:
    """Count segments where bearing changes less than max_bearing_change degrees
    over more than min_length_km.

    Returns count of long straight segments.
    """
    if len(coords) < 3:
        return 0

    count = 0
    straight_distance = 0.0
    prev_bearing = None

    for i in range(len(coords) - 1):
        seg_bearing = bearing(
            coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
        )
        seg_dist = haversine(
            coords[i][0], coords[i][1], coords[i + 1][0], coords[i + 1][1]
        )

        if prev_bearing is not None:
            change = abs(bearing_difference(prev_bearing, seg_bearing))
            if change < max_bearing_change:
                straight_distance += seg_dist
                if straight_distance >= min_length_km:
                    count += 1
                    straight_distance = 0.0  # Reset after counting
            else:
                straight_distance = 0.0
        else:
            straight_distance = seg_dist

        prev_bearing = seg_bearing

    return count


def score_route_quality(
    road_breakdown: dict[str, float],
    overlap_percent: float,
    straightness: float,
    long_straight_count: int = 0,
) -> float:
    """Score route quality from 0.0 to 1.0.

    Higher score = better route:
    - More cycleway/residential/tertiary = better
    - Less overlap = better
    - Lower straightness ratio = better (more winding)
    - Fewer long straight segments = better
    """
    # Road quality score (0–1): prefer small roads
    preferred = {"cycleway", "living_street", "residential", "tertiary", "tertiary_link", "unclassified"}
    preferred_pct = sum(road_breakdown.get(r, 0) for r in preferred)
    road_score = min(preferred_pct / 100.0, 1.0)

    # Overlap penalty: 0% overlap = 1.0, 20% = 0.0
    overlap_score = max(0, 1.0 - overlap_percent / 20.0)

    # Straightness penalty: 0.3 (circular) = 1.0, 0.5 (straight) = 0.0
    straightness_score = max(0, min(1.0, (0.5 - straightness) / 0.2))

    # Long straight penalty
    straight_penalty = max(0, 1.0 - long_straight_count * 0.15)

    # Weighted combination
    score = (
        road_score * 0.35
        + overlap_score * 0.30
        + straightness_score * 0.20
        + straight_penalty * 0.15
    )

    return round(min(1.0, max(0.0, score)), 2)
