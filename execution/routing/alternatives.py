"""
Generate and rank multiple diverse route alternatives.
"""

import logging
import random

from execution.routing.loop_generator import generate_loop, prepare_graph

logger = logging.getLogger(__name__)


def _edge_overlap_between(
    edges_a: list[tuple[int, int]], edges_b: list[tuple[int, int]]
) -> float:
    """Calculate overlap percentage between two edge sequences.

    Treats (u,v) and (v,u) as the same edge.
    Returns percentage 0–100 of edges in A that also appear in B.
    """
    if not edges_a or not edges_b:
        return 0.0

    set_a = {tuple(sorted(e)) for e in edges_a}
    set_b = {tuple(sorted(e)) for e in edges_b}

    shared = set_a & set_b
    return (len(shared) / len(set_a)) * 100


def generate_alternatives(
    start_lat: float,
    start_lon: float,
    target_distance_km: float,
    direction: str | None = None,
    include_hill: dict | None = None,
    count: int = 3,
    max_attempts: int = 15,
) -> list[dict]:
    """Generate multiple diverse route alternatives.

    Args:
        start_lat: Start point latitude.
        start_lon: Start point longitude.
        target_distance_km: Target route distance in km.
        direction: Preferred direction or None.
        include_hill: Optional hill constraint.
        count: Number of alternatives to return.
        max_attempts: Maximum generation attempts.

    Returns:
        List of up to `count` route dicts, sorted by quality_score descending.
    """
    accepted: list[dict] = []
    base_seed = random.randint(0, 1_000_000)

    # Build graph once; reuse across all alternatives (major performance win)
    G, start_node = prepare_graph(start_lat, start_lon, target_distance_km)

    for attempt in range(max_attempts):
        if len(accepted) >= count:
            break

        seed = base_seed + attempt * 7919  # Large prime for maximum variety

        route = generate_loop(
            start_lat=start_lat,
            start_lon=start_lon,
            target_distance_km=target_distance_km,
            direction=direction,
            include_hill=include_hill,
            seed=seed,
            G=G,
            start_node=start_node,
        )

        if route is None:
            logger.info("Attempt %d: generation failed", attempt + 1)
            continue

        # Check diversity against already accepted routes
        is_diverse = True
        for existing in accepted:
            overlap = _edge_overlap_between(
                route["edge_sequence"], existing["edge_sequence"]
            )
            if overlap > 30:
                logger.info(
                    "Attempt %d: too similar to existing route (%.1f%% overlap)",
                    attempt + 1, overlap,
                )
                is_diverse = False
                break

        if is_diverse:
            accepted.append(route)
            logger.info(
                "Accepted route %d/%d: %.1fkm, quality=%.2f",
                len(accepted), count, route["distance_km"], route["quality_score"],
            )

    # Sort by quality score descending
    accepted.sort(key=lambda r: r["quality_score"], reverse=True)
    return accepted
