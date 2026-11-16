"""
Route generation orchestration service.

Ties execution modules together: generate routes, fetch elevations, build responses.
"""

import logging
import uuid
from concurrent.futures import ThreadPoolExecutor

from backend.models.route import (
    Coordinate,
    ElevationPoint,
    RouteAlternative,
    RouteRequest,
    RouteResponse,
)
from execution.elevation.provider import get_elevation_profile
from execution.export.gpx_builder import build_gpx
from execution.routing.alternatives import generate_alternatives

logger = logging.getLogger(__name__)

# In-memory store for generated routes (for GPX download)
_route_store: dict[str, dict] = {}

# Average cycling speed for duration estimation (km/h)
AVG_SPEED_FLAT = 25.0
AVG_SPEED_ROLLING = 22.0
AVG_SPEED_HILLY = 20.0


def generate_route(request: RouteRequest) -> RouteResponse:
    """Generate route alternatives based on the request.

    1. Generate routes via constrained waypoint routing
    2. Fetch elevation profiles
    3. Build response models
    4. Store routes for GPX download
    """
    # Prepare hill constraint if specified
    include_hill = None
    if request.include_hill_min_m:
        include_hill = {"min_elevation_gain": request.include_hill_min_m}

    # Generate alternatives
    routes = generate_alternatives(
        start_lat=request.start_lat,
        start_lon=request.start_lon,
        target_distance_km=request.target_distance_km,
        direction=request.direction,
        include_hill=include_hill,
        count=request.num_alternatives,
    )

    if not routes:
        raise ValueError("No routes could be generated. Try different parameters.")

    # Fetch elevation profiles for all routes in parallel (major speedup vs sequential)
    all_coords = [route["coordinates"] for route in routes]
    with ThreadPoolExecutor(max_workers=len(routes)) as executor:
        elev_results = list(executor.map(get_elevation_profile, all_coords))

    # Build response alternatives
    alternatives = []
    for route, elev_data in zip(routes, elev_results):
        route_id = f"r_{uuid.uuid4().hex[:8]}"

        coords = route["coordinates"]

        # Estimate duration
        avg_speed = _estimate_speed(
            request.elevation_preference, elev_data["elevation_gain"]
        )
        duration_min = int((route["distance_km"] / avg_speed) * 60)

        # Build coordinate list with elevation
        coord_models = []
        for i, (lat, lon) in enumerate(coords):
            ele = elev_data["elevations"][i] if i < len(elev_data["elevations"]) else None
            coord_models.append(Coordinate(lat=lat, lon=lon, ele=ele))

        # Build elevation profile
        profile_models = [
            ElevationPoint(
                distance_km=p["distance_km"],
                elevation_m=p["elevation"],
            )
            for p in elev_data["profile"]
        ]

        alternative = RouteAlternative(
            id=route_id,
            distance_km=route["distance_km"],
            elevation_gain_m=elev_data["elevation_gain"],
            elevation_loss_m=elev_data["elevation_loss"],
            estimated_duration_min=duration_min,
            quality_score=route["quality_score"],
            road_breakdown=route["road_breakdown"],
            coordinates=coord_models,
            elevation_profile=profile_models,
        )
        alternatives.append(alternative)

        # Store for GPX download
        _route_store[route_id] = {
            "coordinates": coords,
            "elevations": elev_data["elevations"],
            "distance_km": route["distance_km"],
            "elevation_gain": elev_data["elevation_gain"],
        }

    return RouteResponse(routes=alternatives)


def get_gpx(route_id: str) -> str | None:
    """Retrieve a generated route and return GPX XML.

    Returns None if route_id not found.
    """
    route_data = _route_store.get(route_id)
    if not route_data:
        return None

    name = f"RouteFinder Route ({route_data['distance_km']:.1f} km)"
    description = (
        f"Distance: {route_data['distance_km']:.1f} km, "
        f"Elevation gain: {route_data['elevation_gain']:.0f} m"
    )

    return build_gpx(
        coordinates=route_data["coordinates"],
        elevations=route_data["elevations"],
        name=name,
        description=description,
    )


def _estimate_speed(
    elevation_preference: str | None, elevation_gain: float
) -> float:
    """Estimate average cycling speed based on elevation."""
    if elevation_preference == "hilly" or elevation_gain > 500:
        return AVG_SPEED_HILLY
    if elevation_preference == "rolling" or elevation_gain > 200:
        return AVG_SPEED_ROLLING
    return AVG_SPEED_FLAT
