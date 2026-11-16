"""
Parse GPX routes from Inspiration/ridewithgps/ and build a popularity grid.

The grid maps (lat, lon) cells → count of how many GPX track/route points
fall in that cell. Used to give lower cycling_weight to roads that real
cyclists have repeatedly chosen.
"""

import logging
import math
import os
import pickle
from collections import defaultdict
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

GPX_DIR = os.path.join("Inspiration", "ridewithgps")
CACHE_PATH = os.path.join(".tmp", "gpx_popularity.pkl")
CELL_SIZE = 0.002  # degrees ≈ 200m per cell
SAMPLE_EVERY = 5   # sample every 5th trackpoint to keep it fast


def _parse_gpx_points(path: str) -> list[tuple[float, float]]:
    """Return (lat, lon) pairs from a GPX file's track or route points."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"g": "http://www.topografix.com/GPX/1/1"}

        # Prefer trkpt (recorded ride), fall back to rtept (planned route)
        pts = root.findall(".//g:trkpt", ns) or root.findall(".//g:rtept", ns)
        points = []
        for i, pt in enumerate(pts):
            if i % SAMPLE_EVERY == 0:
                try:
                    points.append((float(pt.get("lat")), float(pt.get("lon"))))
                except (TypeError, ValueError):
                    pass
        return points
    except Exception as e:
        logger.debug("Failed to parse %s: %s", path, e)
        return []


def _snap_to_grid(lat: float, lon: float, cell: float = CELL_SIZE) -> tuple[float, float]:
    """Snap a coordinate to the nearest grid cell centre."""
    return (round(round(lat / cell) * cell, 5), round(round(lon / cell) * cell, 5))


def build_popularity_grid(gpx_dir: str = GPX_DIR) -> dict[tuple[float, float], int]:
    """Parse all GPX files and return a {(lat_r, lon_r): count} dict."""
    grid: dict[tuple[float, float], int] = defaultdict(int)

    if not os.path.isdir(gpx_dir):
        logger.warning("GPX directory not found: %s", gpx_dir)
        return dict(grid)

    files = [f for f in os.listdir(gpx_dir) if f.lower().endswith(".gpx")]
    logger.info("Building popularity grid from %d GPX files in %s", len(files), gpx_dir)

    for fname in files:
        points = _parse_gpx_points(os.path.join(gpx_dir, fname))
        for lat, lon in points:
            cell = _snap_to_grid(lat, lon)
            grid[cell] += 1

    logger.info(
        "Popularity grid: %d non-empty cells from %d files",
        len(grid), len(files),
    )
    return dict(grid)


def load_popularity_grid(
    gpx_dir: str = GPX_DIR,
    cache_path: str = CACHE_PATH,
) -> dict[tuple[float, float], int]:
    """Load popularity grid from cache, rebuilding if stale or missing."""
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    # Rebuild if cache missing or older than any GPX file
    if os.path.exists(cache_path):
        cache_mtime = os.path.getmtime(cache_path)
        stale = False
        if os.path.isdir(gpx_dir):
            for f in os.listdir(gpx_dir):
                if f.lower().endswith(".gpx"):
                    fmtime = os.path.getmtime(os.path.join(gpx_dir, f))
                    if fmtime > cache_mtime:
                        stale = True
                        break
        if not stale:
            try:
                with open(cache_path, "rb") as f:
                    grid = pickle.load(f)
                logger.info("Loaded popularity grid from cache (%d cells)", len(grid))
                return grid
            except Exception:
                pass

    grid = build_popularity_grid(gpx_dir)

    try:
        with open(cache_path, "wb") as f:
            pickle.dump(grid, f)
        logger.info("Popularity grid cached: %s", cache_path)
    except Exception as e:
        logger.warning("Could not cache popularity grid: %s", e)

    return grid


def apply_popularity_bonus(
    G,
    popularity_grid: dict[tuple[float, float], int],
    cell_size: float = CELL_SIZE,
    max_reduction: float = 0.45,
    min_count_threshold: int = 3,
) -> None:
    """Reduce cycling_weight for edges that appear in popular GPX routes.

    Roads with many GPS tracks passing nearby get up to max_reduction (45%)
    lower weight, making the algorithm naturally prefer well-ridden routes.

    Args:
        G: Weighted OSMnx graph (modified in-place).
        popularity_grid: Cell → count dict from load_popularity_grid().
        cell_size: Grid cell size in degrees.
        max_reduction: Maximum weight reduction factor (0–1).
        min_count_threshold: Minimum count before any bonus is applied.
    """
    if not popularity_grid:
        return

    boosted = 0
    for u, v, data in G.edges(data=True):
        current = data.get("cycling_weight")
        if current is None or math.isinf(current):
            continue

        mid_lat = (G.nodes[u]["y"] + G.nodes[v]["y"]) / 2
        mid_lon = (G.nodes[u]["x"] + G.nodes[v]["x"]) / 2

        # Check this cell and 8 neighbours (effectively 3×3 search ≈ 600m radius)
        best_count = 0
        base_lat = round(round(mid_lat / cell_size) * cell_size, 5)
        base_lon = round(round(mid_lon / cell_size) * cell_size, 5)
        for dlat in (-1, 0, 1):
            for dlon in (-1, 0, 1):
                c = (
                    round(base_lat + dlat * cell_size, 5),
                    round(base_lon + dlon * cell_size, 5),
                )
                cnt = popularity_grid.get(c, 0)
                if cnt > best_count:
                    best_count = cnt

        if best_count >= min_count_threshold:
            # Scale reduction: count=3 → 15% reduction, count=20+ → 45% reduction
            reduction = max_reduction * min(best_count / 20.0, 1.0)
            data["cycling_weight"] = current * (1.0 - reduction)
            boosted += 1

    logger.info(
        "GPX popularity bonus applied to %d / %d edges",
        boosted, G.number_of_edges(),
    )
