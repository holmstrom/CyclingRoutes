"""
Assign cycling weights to graph edges based on OSM road type and surface.

Lower weight = more preferred road. Weight = road_type_factor * length_meters.
Edges with excluded surfaces or highway types get weight=inf (impassable).
"""

import logging
import math

import networkx as nx

logger = logging.getLogger(__name__)

ROAD_TYPE_WEIGHTS: dict[str, float] = {
    "cycleway": 1.0,
    "living_street": 1.0,
    "residential": 1.2,
    "tertiary": 1.5,
    "tertiary_link": 1.5,
    "unclassified": 1.5,
    "path": 1.8,
    "service": 2.0,
    "secondary": 3.0,
    "secondary_link": 3.0,
    "primary": 8.0,
    "primary_link": 8.0,
    "trunk": math.inf,
    "trunk_link": math.inf,
    "motorway": math.inf,
    "motorway_link": math.inf,
}

EXCLUDED_SURFACES: set[str] = {
    "gravel",
    "dirt",
    "unpaved",
    "ground",
    "grass",
    "sand",
    "mud",
    "compacted",
    "fine_gravel",
    "earth",
    "woodchips",
}

DEFAULT_ROAD_WEIGHT = 5.0  # Unknown road types get moderate penalty
WEIGHT_ATTR = "cycling_weight"


def _get_worst_highway_weight(highway_val) -> float:
    """Extract the worst (highest) weight from a highway attribute.

    OSMnx simplified edges may have highway as a list (e.g., ['residential', 'tertiary']).
    We take the worst (highest) weight to be conservative.
    """
    if isinstance(highway_val, list):
        return max(
            ROAD_TYPE_WEIGHTS.get(h, DEFAULT_ROAD_WEIGHT) for h in highway_val
        )
    return ROAD_TYPE_WEIGHTS.get(highway_val, DEFAULT_ROAD_WEIGHT)


def _has_excluded_surface(surface_val) -> bool:
    """Check if any surface value is in the excluded set."""
    if surface_val is None:
        return False
    if isinstance(surface_val, list):
        return any(s in EXCLUDED_SURFACES for s in surface_val)
    return surface_val in EXCLUDED_SURFACES


def apply_weights(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Apply cycling weights to all edges in the graph. Modifies in-place.

    For each edge:
      cycling_weight = road_type_factor * length_meters
      If surface is excluded or highway is trunk/motorway: cycling_weight = inf
    """
    for u, v, data in G.edges(data=True):
        length = data.get("length", 0)
        highway = data.get("highway")
        surface = data.get("surface")

        if highway is None:
            data[WEIGHT_ATTR] = DEFAULT_ROAD_WEIGHT * length
            continue

        road_weight = _get_worst_highway_weight(highway)

        if math.isinf(road_weight) or _has_excluded_surface(surface):
            data[WEIGHT_ATTR] = math.inf
        else:
            data[WEIGHT_ATTR] = road_weight * length

    return G


def apply_visited_penalty(
    G: nx.MultiDiGraph,
    visited_edges: set[tuple[int, int]],
    penalty_factor: float = 10.0,
) -> None:
    """Multiply cycling_weight by penalty_factor for already-visited edges.

    Used during route generation to discourage the return leg from
    using the same roads as the outbound leg.

    Args:
        G: The graph (modified in-place).
        visited_edges: Set of (u, v) node pairs that have been traversed.
        penalty_factor: Multiplier for visited edges.
    """
    for u, v, data in G.edges(data=True):
        if (u, v) in visited_edges or (v, u) in visited_edges:
            current = data.get(WEIGHT_ATTR, 0)
            if not math.isinf(current):
                data[WEIGHT_ATTR] = current * penalty_factor


def reset_visited_penalties(
    G: nx.MultiDiGraph,
    visited_edges: set[tuple[int, int]],
    penalty_factor: float = 10.0,
) -> None:
    """Undo visited penalties (divide by penalty_factor) for a set of edges.

    Useful when generating multiple alternatives on the same graph.
    """
    for u, v, data in G.edges(data=True):
        if (u, v) in visited_edges or (v, u) in visited_edges:
            current = data.get(WEIGHT_ATTR, 0)
            if not math.isinf(current) and current > 0:
                data[WEIGHT_ATTR] = current / penalty_factor
