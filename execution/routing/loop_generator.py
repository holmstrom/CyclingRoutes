"""
Core loop route generation using hybrid waypoint + A* approach.

Generates cycling loop routes by:
1. Creating waypoints in an elongated teardrop pattern
2. Routing between consecutive waypoints using A* on a weighted OSM graph
3. Applying visited-edge penalties segment-by-segment to avoid road repetition
"""

import logging
import math
import os
import pickle
import random

import networkx as nx
import osmnx as ox

from execution.graph.downloader import CACHE_DIR, _cache_key, _is_cache_valid, get_cycling_graph
from execution.graph.weighter import WEIGHT_ATTR, apply_visited_penalty, apply_weights, reset_visited_penalties
from execution.gpx.learner import CACHE_PATH as GPX_CACHE_PATH
from execution.gpx.learner import apply_popularity_bonus, load_popularity_grid
from execution.utils.geo_math import (
    destination_point,
    direction_to_bearing,
    normalize_bearing,
    polyline_distance,
)
from execution.utils.validators import (
    calculate_long_straight_segments,
    calculate_overlap_percent,
    calculate_road_breakdown,
    calculate_straightness,
    score_route_quality,
    validate_distance,
    validate_loop_closure,
)

logger = logging.getLogger(__name__)

# Algorithm constants
GRAPH_RADIUS_FACTOR = 0.6  # radius = target_km * this * 1000
INITIAL_REACH_DIVISOR = 4.5  # reach = target_km / this
WAYPOINT_COUNT = 5
MAX_ROUTING_FAILURES = 4   # retries with new jitter when routing has no path
MAX_CALIBRATION_STEPS = 5  # retries with same jitter but adjusted reach_divisor
DISTANCE_TOLERANCE = 0.15
MAX_OVERLAP_PERCENT = 20.0
VISITED_PENALTY = 10.0


def prepare_graph(
    start_lat: float,
    start_lon: float,
    target_distance_km: float,
) -> tuple[nx.MultiDiGraph, int]:
    """Download, weight, SCC-filter, and apply learned bonuses to cycling graph.

    Separated so callers (e.g. generate_alternatives) can build the graph
    once and reuse it across multiple generate_loop calls.

    Returns:
        (G, start_node) — weighted SCC graph and nearest node to start.
    """
    radius_m = max(target_distance_km * GRAPH_RADIUS_FACTOR * 1000, 5000)
    logger.info(
        "Preparing graph: center=(%.4f, %.4f), target=%.1fkm, radius=%.0fm",
        start_lat, start_lon, target_distance_km, radius_m,
    )

    # Prepared graph = raw graph + weights + SCC + popularity bonus.
    # Cached separately from the raw graph so subsequent requests skip
    # the expensive largest_component (7s) and apply_popularity_bonus (3.6s) steps.
    # City-exit penalty is NOT cached (it depends on start location).
    ck = _cache_key(start_lat, start_lon, radius_m)
    prepared_path = os.path.join(CACHE_DIR, f"{ck}.prepared.pkl")

    # Prepared cache is stale if the GPX popularity pkl is newer (new rides added)
    prepared_valid = _is_cache_valid(prepared_path)
    if prepared_valid and os.path.exists(GPX_CACHE_PATH):
        if os.path.getmtime(prepared_path) < os.path.getmtime(GPX_CACHE_PATH):
            prepared_valid = False

    if prepared_valid:
        logger.info("Loading prepared graph from cache: %s", prepared_path)
        with open(prepared_path, "rb") as f:
            G = pickle.load(f)
    else:
        G = get_cycling_graph(start_lat, start_lon, radius_m)
        apply_weights(G)
        G = ox.truncate.largest_component(G, strongly=True)
        try:
            popularity = load_popularity_grid()
            apply_popularity_bonus(G, popularity)
        except Exception as e:
            logger.warning("GPX popularity bonus skipped: %s", e)
        # Cache the prepared graph for future requests
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(prepared_path, "wb") as f:
                pickle.dump(G, f)
            logger.info("Prepared graph cached: %s", prepared_path)
        except Exception as e:
            logger.warning("Could not cache prepared graph: %s", e)

    logger.info("Graph ready: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges())

    # City-exit penalty (location-specific — always fresh, not cached)
    _apply_city_exit_penalty(G, start_lat, start_lon, radius_km=2.5, penalty=2.5)

    start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
    return G, start_node


def _apply_city_exit_penalty(
    G: nx.MultiDiGraph,
    start_lat: float,
    start_lon: float,
    radius_km: float = 2.5,
    penalty: float = 2.5,
) -> None:
    """Penalise non-cycleway roads near the start to force quick city exit.

    Within radius_km of start, roads that aren't dedicated cycling
    infrastructure get their weight multiplied by penalty. This steers the
    algorithm onto bike paths/cycleways for departure and arrival, avoiding
    busy city streets.
    """
    R = 6371.0  # Earth radius km
    lat1 = math.radians(start_lat)
    lon1 = math.radians(start_lon)
    penalised = 0

    for u, v, data in G.edges(data=True):
        current = data.get(WEIGHT_ATTR)
        if current is None or math.isinf(current):
            continue

        # Midpoint of edge
        mid_lat = math.radians((G.nodes[u]["y"] + G.nodes[v]["y"]) / 2)
        mid_lon = math.radians((G.nodes[u]["x"] + G.nodes[v]["x"]) / 2)

        # Haversine distance
        dlat = mid_lat - lat1
        dlon = mid_lon - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(mid_lat) * math.sin(dlon / 2) ** 2
        dist_km = 2 * R * math.asin(math.sqrt(a))

        if dist_km < radius_km:
            highway = data.get("highway", "")
            if isinstance(highway, list):
                highway = highway[0] if highway else ""
            # Only penalise non-cycling-specific infrastructure
            if highway not in ("cycleway", "path", "living_street"):
                data[WEIGHT_ATTR] = current * penalty
                penalised += 1

    logger.info(
        "City-exit penalty (×%.1f within %.1fkm): %d edges penalised",
        penalty, radius_km, penalised,
    )


def generate_loop(
    start_lat: float,
    start_lon: float,
    target_distance_km: float,
    direction: str | None = None,
    include_hill: dict | None = None,
    seed: int | None = None,
    G: nx.MultiDiGraph | None = None,
    start_node: int | None = None,
) -> dict | None:
    """Generate a single loop route.

    Args:
        start_lat: Start point latitude.
        start_lon: Start point longitude.
        target_distance_km: Target route distance in km (10–100).
        direction: Preferred direction ('north', 'south', etc.) or None for any.
        include_hill: Optional dict with 'min_elevation_gain' key.
        seed: Random seed for reproducibility.
        G: Pre-built weighted SCC graph (from prepare_graph). Built here if None.
        start_node: Pre-snapped start node. Snapped here if None.

    Returns:
        Route dict with keys: coordinates, distance_km, edge_sequence,
        waypoints, road_breakdown, overlap_percent, quality_score.
        Returns None if generation fails after all retries.
    """
    rng = random.Random(seed)

    # Build graph only if not provided (standalone call)
    if G is None or start_node is None:
        G, start_node = prepare_graph(start_lat, start_lon, target_distance_km)

    logger.info(
        "Generating loop: start=(%.4f, %.4f), target=%.1fkm, direction=%s",
        start_lat, start_lon, target_distance_km, direction,
    )

    reach_divisor = INITIAL_REACH_DIVISOR
    routing_failures = 0
    calibration_steps = 0

    # Pre-fetch hills ONCE before retry loop — find_hills makes an elevation API call
    # and must NOT be called on every retry attempt (would multiply latency by 10–50×).
    preloaded_hills: list[dict] | None = None
    if include_hill and include_hill.get("min_elevation_gain"):
        try:
            from execution.routing.hill_finder import find_hills
            radius_km = target_distance_km * GRAPH_RADIUS_FACTOR
            preloaded_hills = find_hills(
                start_lat, start_lon, radius_km, include_hill["min_elevation_gain"]
            )
            logger.info("Pre-fetched %d hill candidates", len(preloaded_hills))
        except Exception as e:
            logger.warning("Hill pre-fetch failed: %s", e)
            preloaded_hills = []

    # Save initial rng state — restored when only calibrating (same jitter, new divisor)
    rng_state = rng.getstate()

    while routing_failures < MAX_ROUTING_FAILURES and calibration_steps < MAX_CALIBRATION_STEPS:
        attempt = routing_failures + calibration_steps + 1
        logger.info(
            "Attempt %d (routing_fails=%d, calib=%d, reach_divisor=%.2f)",
            attempt, routing_failures, calibration_steps, reach_divisor,
        )

        # Restore same rng state for calibration retries → consistent jitter
        rng.setstate(rng_state)

        # Step 2: Generate waypoints
        waypoints = _generate_waypoints(
            start_lat, start_lon, target_distance_km, direction, rng,
            reach_divisor=reach_divisor,
        )

        # Step 3: If hill candidates were pre-fetched, adjust apex waypoint toward best hill
        if preloaded_hills:
            waypoints = _adjust_for_hill(waypoints, preloaded_hills)

        # Step 3b: Reject waypoint configurations that cross to opposite side of start
        if _waypoints_cross_start(start_lat, start_lon, waypoints, direction):
            logger.warning("Waypoints cross start — retrying with new jitter")
            routing_failures += 1
            rng_state = rng.getstate()
            continue

        # Step 4: Route through waypoints (graph modified in-place, tracked for restoration)
        result, visited_edges = _route_through_waypoints(G, start_node, waypoints)

        if result is None:
            # Routing failure: advance rng for different jitter next time
            routing_failures += 1
            rng_state = rng.getstate()
            logger.warning("Routing failed on attempt %d", attempt)
            continue

        coords, edge_sequence = result
        distance_km = polyline_distance(coords)

        # Restore graph for next attempt (undo visited penalties)
        reset_visited_penalties(G, visited_edges, VISITED_PENALTY)

        # Step 5a: Validate loop closure
        if not validate_loop_closure(coords):
            logger.warning("Loop closure failed: gap too large")
            routing_failures += 1
            rng_state = rng.getstate()
            continue

        # Step 5b: Validate distance — if off, calibrate reach_divisor
        if not validate_distance(distance_km, target_distance_km, DISTANCE_TOLERANCE):
            ratio = distance_km / target_distance_km
            # Clamp correction to ±20% per step to prevent oscillation
            correction = max(0.80, min(1.20, ratio))
            reach_divisor *= correction
            calibration_steps += 1
            logger.warning(
                "Distance mismatch: %.1fkm vs target %.1fkm (±%.0f%%), "
                "adjusted reach_divisor to %.2f",
                distance_km, target_distance_km,
                DISTANCE_TOLERANCE * 100, reach_divisor,
            )
            # Don't advance rng_state → same waypoint jitter with new divisor
            continue

        # Step 5c: Validate overlap
        overlap = calculate_overlap_percent(edge_sequence)
        if overlap > MAX_OVERLAP_PERCENT:
            logger.warning("Overlap too high: %.1f%%", overlap)
            routing_failures += 1
            rng_state = rng.getstate()
            continue

        # Step 6: Score
        road_breakdown = calculate_road_breakdown(G, edge_sequence)
        straightness = calculate_straightness(coords)
        long_straights = calculate_long_straight_segments(coords)
        quality = score_route_quality(
            road_breakdown, overlap, straightness, long_straights
        )

        logger.info(
            "Route generated: %.1fkm, overlap=%.1f%%, quality=%.2f",
            distance_km, overlap, quality,
        )

        return {
            "coordinates": coords,
            "distance_km": round(distance_km, 2),
            "edge_sequence": edge_sequence,
            "waypoints": [(lat, lon) for lat, lon in waypoints],
            "road_breakdown": road_breakdown,
            "overlap_percent": round(overlap, 1),
            "quality_score": quality,
        }

    logger.error(
        "Failed to generate loop after %d routing failures + %d calibration steps",
        routing_failures, calibration_steps,
    )
    return None


def _generate_waypoints(
    start_lat: float,
    start_lon: float,
    target_km: float,
    direction: str | None,
    rng: random.Random,
    reach_divisor: float = INITIAL_REACH_DIVISOR,
) -> list[tuple[float, float]]:
    """Generate 5 waypoints forming an elongated teardrop loop.

    The loop goes out in the preferred direction, curves around,
    and comes back on a different path.
    """
    # Determine outbound bearing
    if direction:
        out_bearing = direction_to_bearing(direction)
    else:
        out_bearing = rng.uniform(0, 360)

    reach = target_km / reach_divisor  # Distance to farthest waypoint in km

    # Waypoint definitions: (distance_fraction, bearing_offset_range)
    # Creates a petal-shaped loop that stays on one side of the start point.
    # Tighter ranges on WP4/WP5 prevent "figure-8" routes that loop back
    # through start before heading in the opposite direction.
    wp_specs = [
        (0.50, (-10, 10)),     # WP1: early outbound
        (0.85, (-5, 15)),      # WP2: far outbound
        (1.00, (20, 50)),      # WP3: apex, slightly rotated to create loop
        (0.70, (55, 95)),      # WP4: return side (was 70-110, tightened to stay same-side)
        (0.45, (150, 180)),    # WP5: approaching start (was 130-170, tightened to avoid crossover)
    ]

    waypoints = []
    for dist_frac, (offset_min, offset_max) in wp_specs:
        offset = rng.uniform(offset_min, offset_max)
        wp_bearing = normalize_bearing(out_bearing + offset)
        wp_dist = reach * dist_frac

        # Add jitter: ±10% of reach in a random direction (smaller = more stable calibration)
        jitter_dist = rng.uniform(0, 0.10 * reach)
        jitter_bearing = rng.uniform(0, 360)

        base_lat, base_lon = destination_point(
            start_lat, start_lon, wp_bearing, wp_dist
        )
        wp_lat, wp_lon = destination_point(
            base_lat, base_lon, jitter_bearing, jitter_dist
        )
        waypoints.append((wp_lat, wp_lon))

    return waypoints


def _waypoints_cross_start(
    start_lat: float,
    start_lon: float,
    waypoints: list[tuple[float, float]],
    direction: str | None,
) -> bool:
    """Check if any waypoint crosses to the opposite side of start.

    Draws an imaginary line perpendicular to the outbound direction through
    the start point. If WP4 or WP5 (return waypoints) end up on the
    opposite side of this line from WP1, the route would form a figure-8.
    """
    if direction is None:
        return False  # No direction constraint → can't determine "opposite side"

    out_bearing_rad = math.radians(direction_to_bearing(direction))

    # Perpendicular unit vector (rotated 90° clockwise from outbound)
    perp_x = math.cos(out_bearing_rad)  # points right of outbound
    perp_y = math.sin(out_bearing_rad)

    # Project each waypoint onto the outbound direction axis
    # Positive = in the outbound direction, negative = behind start
    for idx in (3, 4):  # WP4 and WP5 (0-indexed)
        wp_lat, wp_lon = waypoints[idx]
        # Approximate flat-earth delta (good enough for <50km)
        dy = (wp_lat - start_lat) * 111.32  # km
        dx = (wp_lon - start_lon) * 111.32 * math.cos(math.radians(start_lat))
        # Project onto outbound axis: positive = forward, negative = behind
        proj = dx * math.sin(out_bearing_rad) + dy * math.cos(out_bearing_rad)
        if proj < -0.5:  # >500m behind start in the outbound direction
            logger.info("Waypoint %d is %.1fkm behind start — crossover detected", idx + 1, abs(proj))
            return True

    return False


def _adjust_for_hill(
    waypoints: list[tuple[float, float]],
    hills: list[dict],
) -> list[tuple[float, float]]:
    """Replace the apex waypoint (WP3) with the best preloaded hill location."""
    if not hills:
        return waypoints
    hill = hills[0]
    waypoints = list(waypoints)
    waypoints[2] = (hill["lat"], hill["lon"])
    logger.info(
        "Adjusted waypoint for hill at (%.4f, %.4f), gain=%.0fm",
        hill["lat"], hill["lon"], hill["estimated_gain"],
    )
    return waypoints


def _astar_heuristic(G: nx.MultiDiGraph, target: int):
    """Return an admissible A* heuristic for the given target node.

    Uses great-circle distance × 1.0 (the minimum cycling_weight factor),
    which never overestimates the true path cost.  On a 250k-edge graph
    this reduces routing time from ~0.8s (Dijkstra) to <0.01s per segment.
    """
    t_y = math.radians(G.nodes[target]["y"])
    t_x = math.radians(G.nodes[target]["x"])

    def h(u: int, _v: int) -> float:
        u_y = math.radians(G.nodes[u]["y"])
        u_x = math.radians(G.nodes[u]["x"])
        dlat = t_y - u_y
        dlon = t_x - u_x
        a = math.sin(dlat / 2) ** 2 + math.cos(u_y) * math.cos(t_y) * math.sin(dlon / 2) ** 2
        return 2 * 6_371_000 * math.asin(math.sqrt(a))  # metres × 1.0

    return h


def _route_through_waypoints(
    G: nx.MultiDiGraph,
    start_node: int,
    waypoints: list[tuple[float, float]],
) -> tuple[tuple[list[tuple[float, float]], list[tuple[int, int]]] | None, set[tuple[int, int]]]:
    """Route from start through all waypoints and back to start.

    Applies visited-edge penalty after each segment so later segments
    prefer different roads. The graph is modified in-place; caller must
    call reset_visited_penalties() with the returned visited_edges.

    The graph must be the largest SCC (via ox.truncate.largest_component),
    guaranteeing that shortest_path will always find a path.

    Returns:
        (result, visited_edges) where result is (coordinates, edge_sequence)
        or None if routing fails. visited_edges is always returned so caller
        can clean up graph modifications.
    """
    visited_edges: set[tuple[int, int]] = set()

    # Snap waypoints to nearest graph nodes (fast kd-tree lookup via osmnx)
    wp_nodes = []
    for lat, lon in waypoints:
        node = ox.distance.nearest_nodes(G, lon, lat)
        wp_nodes.append(node)

    # Full node sequence: start → wp1 → … → wpN → start
    node_sequence = [start_node] + wp_nodes + [start_node]

    all_coords: list[tuple[float, float]] = []
    all_edges: list[tuple[int, int]] = []

    prev_node = node_sequence[0]
    for i in range(1, len(node_sequence)):
        target = node_sequence[i]

        if prev_node == target:
            continue

        try:
            path = nx.astar_path(
                G, prev_node, target,
                heuristic=_astar_heuristic(G, target),
                weight=WEIGHT_ATTR,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            logger.warning("No path for segment %d: %s", i, exc)
            return None, visited_edges

        # Extract coordinates and edges
        segment_coords = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in path]
        segment_edges = [(path[j - 1], path[j]) for j in range(1, len(path))]

        if all_coords:
            all_coords.extend(segment_coords[1:])
        else:
            all_coords.extend(segment_coords)
        all_edges.extend(segment_edges)

        # Apply visited penalty so next segments prefer different roads
        new_edges = set(segment_edges)
        visited_edges.update(new_edges)
        apply_visited_penalty(G, new_edges, VISITED_PENALTY)

        prev_node = target

    if len(all_coords) < 3:
        logger.warning("Route too short: only %d coordinates", len(all_coords))
        return None, visited_edges

    return (all_coords, all_edges), visited_edges
