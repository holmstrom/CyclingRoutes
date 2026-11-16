"""
Download OSM cycling graph via OSMnx and cache to disk.

Cache key = center point (rounded to 0.01°) + radius (rounded to 1000m).
Cache TTL = 30 days.
"""

import logging
import os
import pickle
import time

import networkx as nx
import osmnx as ox

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(".tmp", "graphs")
CACHE_TTL_DAYS = 30

# Overpass QL filter for cycling-appropriate roads
CYCLING_FILTER = (
    '["highway"~"cycleway|residential|living_street|tertiary|tertiary_link'
    "|secondary|secondary_link|unclassified|primary|primary_link|service"
    '"]["area"!~"yes"]'
)

MIN_EDGES_THRESHOLD = 100  # Fallback to all roads if fewer edges than this


def get_cycling_graph(
    center_lat: float, center_lon: float, radius_m: float
) -> nx.MultiDiGraph:
    """Download or load cached OSM graph for cycling.

    Args:
        center_lat: Center latitude.
        center_lon: Center longitude.
        radius_m: Radius in meters around the center point.

    Returns:
        NetworkX MultiDiGraph with OSM road network.
    """
    cache_key = _cache_key(center_lat, center_lon, radius_m)
    cache_path = _cache_path(cache_key)

    # Try fast pickle cache first, fall back to graphml
    pickle_path = cache_path.replace(".graphml", ".pkl")
    if _is_cache_valid(pickle_path):
        logger.info("Loading cached graph (pickle): %s", pickle_path)
        with open(pickle_path, "rb") as f:
            return pickle.load(f)
    if _is_cache_valid(cache_path):
        logger.info("Loading cached graph (graphml): %s", cache_path)
        G = ox.load_graphml(cache_path)
        # Migrate to pickle for future speed
        with open(pickle_path, "wb") as f:
            pickle.dump(G, f)
        return G

    logger.info(
        "Downloading OSM graph: center=(%.4f, %.4f), radius=%.0fm",
        center_lat,
        center_lon,
        radius_m,
    )

    try:
        G = ox.graph_from_point(
            center_point=(center_lat, center_lon),
            dist=radius_m,
            custom_filter=CYCLING_FILTER,
            simplify=True,
        )
    except Exception as e:
        logger.warning("Custom filter failed (%s), falling back to all roads", e)
        G = ox.graph_from_point(
            center_point=(center_lat, center_lon),
            dist=radius_m,
            network_type="all",
            simplify=True,
        )

    # If custom filter returned a very sparse graph, retry with all roads
    if G.number_of_edges() < MIN_EDGES_THRESHOLD:
        logger.warning(
            "Graph too sparse (%d edges), falling back to all roads",
            G.number_of_edges(),
        )
        G = ox.graph_from_point(
            center_point=(center_lat, center_lon),
            dist=radius_m,
            network_type="all",
            simplify=True,
        )

    _save_graph(G, cache_path)
    logger.info(
        "Graph downloaded: %d nodes, %d edges", G.number_of_nodes(), G.number_of_edges()
    )
    return G


def _cache_key(center_lat: float, center_lon: float, radius_m: float) -> str:
    """Deterministic cache key from rounded coordinates and radius.

    Uses 0.05° lat/lon steps (≈5km) and 5km radius buckets so nearby
    start points and similar distances share the same cached graph.
    This prevents redundant downloads (e.g. 28km and 30km radii use same graph).
    """
    lat_r = round(round(center_lat / 0.05) * 0.05, 2)
    lon_r = round(round(center_lon / 0.05) * 0.05, 2)
    rad_r = round(radius_m / 5000) * 5000  # Round to nearest 5000m
    return f"{lat_r}_{lon_r}_{int(rad_r)}"


def _cache_path(cache_key: str) -> str:
    return os.path.join(CACHE_DIR, f"{cache_key}.graphml")


def _is_cache_valid(cache_path: str) -> bool:
    """Check file exists and is within TTL."""
    if not os.path.exists(cache_path):
        return False
    mtime = os.path.getmtime(cache_path)
    age_days = (time.time() - mtime) / 86400
    return age_days < CACHE_TTL_DAYS


def _save_graph(G: nx.MultiDiGraph, cache_path: str) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    # Save both formats: graphml (portable) and pickle (fast loading)
    ox.save_graphml(G, cache_path)
    pickle_path = cache_path.replace(".graphml", ".pkl")
    with open(pickle_path, "wb") as f:
        pickle.dump(G, f)
    logger.info("Graph cached: %s (graphml + pickle)", cache_path)
