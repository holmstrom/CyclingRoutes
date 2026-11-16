"""
GraphHopper routing connector.
GraphHopper er en kommerciel routing service med gratis tier.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from ..utils.http import HTTPClient


def get_route_graphhopper(
    base_url: str,
    api_key: str,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    vehicle: str = "bike",
    elevation: bool = True,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter en cykelrute fra GraphHopper.
    
    Args:
        base_url: GraphHopper base URL
        api_key: GraphHopper API key
        start_lat: Start latitude
        start_lon: Start longitude
        end_lat: Slut latitude
        end_lon: Slut longitude
        vehicle: Vehicle type (bike, car, foot)
        elevation: Inkluder elevation data
        logger: Optional logger
        
    Returns:
        Rute dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger, timeout=30)
    
    # GraphHopper route endpoint
    endpoint = f"{base_url}/route"
    
    try:
        # GraphHopper bruger GET med flere point parametre
        # requests library understøtter ikke automatisk flere værdier for samme key
        # Vi skal bygge URL manuelt eller bruge en workaround
        from urllib.parse import urlencode
        
        # Byg query string manuelt for at understøtte flere "point" parametre
        # Prioriter små landeveje: undgå motorveje og store veje
        query_parts = [
            f"point={start_lat},{start_lon}",
            f"point={end_lat},{end_lon}",
            f"vehicle={vehicle}",
            f"elevation={str(elevation).lower()}",
            "points_encoded=false",
            "instructions=false",
            # Brug standard CH (ikke disable) for gratis tier
            # "ch.disable=true",  # fjernet
            f"key={api_key}"
        ]
        query_string = "&".join(query_parts)
        full_url = f"{endpoint}?{query_string}"
        
        response = client.get(full_url, timeout=30)
        
        # Tjek HTTP status
        if response.status_code != 200:
            logger.error(f"GraphHopper HTTP fejl: {response.status_code} - {response.text[:200]}")
            return None
        
        data = response.json()
        
        # Tjek for fejl i response
        if "message" in data:
            logger.error(f"GraphHopper fejl: {data.get('message')}")
            return None
        
        paths = data.get("paths", [])
        if not paths:
            logger.warning("Ingen ruter fundet i GraphHopper response")
            return None
        
        # Hent første rute
        route_data = paths[0]
        
        # Hent koordinater fra points objekt
        points = route_data.get("points") or {}
        coordinates = []
        
        if points and isinstance(points, dict):
            if "coordinates" in points:
                # GraphHopper returnerer [lon, lat] arrays når points_encoded=false
                for coord in points["coordinates"]:
                    coordinates.append((coord[1], coord[0]))  # Konverter til (lat, lon)
            elif "type" in points and points["type"] == "LineString":
                # Alternativ format
                coords = points.get("coordinates", [])
                for coord in coords:
                    coordinates.append((coord[1], coord[0]))
        
        # Hvis ingen koordinater fundet, prøv alternativ struktur
        if not coordinates:
            # GraphHopper kan også returnere koordinater direkte i response
            if "geometry" in route_data:
                geometry = route_data.get("geometry")
                if isinstance(geometry, dict) and "coordinates" in geometry:
                    for coord in geometry["coordinates"]:
                        coordinates.append((coord[1], coord[0]))
        
        # Hvis stadig ingen koordinater fundet, returner None
        if not coordinates:
            logger.warning("Ingen koordinater fundet i GraphHopper response")
            return None
        
        distance_m = route_data.get("distance", 0)
        time_ms = route_data.get("time", 0)
        
        result = {
            "distance": distance_m / 1000,  # Konverter til km
            "duration": time_ms / 60000,  # Konverter til minutter (ms -> min)
            "coordinates": coordinates,
        }
        
        # Tilføj elevation data hvis tilgængelig
        if elevation:
            ascend = route_data.get("ascend", 0)
            descend = route_data.get("descend", 0)
            result["elevation_gain"] = ascend
            result["elevation_loss"] = descend
            
            # Hent elevation points hvis tilgængelig (til elevation profile)
            points_for_elevation = route_data.get("points") or {}
            elevation_points = points_for_elevation.get("elevation", []) if isinstance(points_for_elevation, dict) else []
            if elevation_points and len(elevation_points) == len(coordinates):
                # Kombiner koordinater med elevation
                elevation_data = []
                cum_distance = 0
                for i, (coord, elev) in enumerate(zip(coordinates, elevation_points)):
                    if i > 0:
                        # Beregn distance mellem punkter (simplificeret)
                        from math import radians, cos, sin, asin, sqrt
                        lat1, lon1 = coordinates[i-1]
                        lat2, lon2 = coord
                        # Haversine distance
                        dlat = radians(lat2 - lat1)
                        dlon = radians(lon2 - lon1)
                        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                        c = 2 * asin(sqrt(a))
                        cum_distance += c * 6371  # Radius of Earth in km
                    
                    elevation_data.append({
                        'lat': coord[0],
                        'lon': coord[1],
                        'elevation': elev,
                        'distance': cum_distance
                    })
                result["elevation"] = elevation_data
            
            # Estimer gradient (simplificeret)
            if distance_m > 0:
                # Estimer max gradient baseret på ascend og distance
                max_gradient = (ascend / distance_m) * 100 if distance_m > 0 else 0
                result["max_gradient"] = max_gradient
                result["avg_gradient"] = (ascend / distance_m) * 100 if distance_m > 0 else 0
        
        return result
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af rute fra GraphHopper: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def get_route_with_waypoints_graphhopper(
    base_url: str,
    api_key: str,
    coordinates: List[Tuple[float, float]],
    vehicle: str = "bike",
    elevation: bool = True,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter en cykelrute med flere waypoints fra GraphHopper (til loop ruter).
    
    Args:
        base_url: GraphHopper base URL
        api_key: GraphHopper API key
        coordinates: Liste af (lat, lon) tuples (start + waypoints + slut)
        vehicle: Vehicle type (bike, car, foot)
        elevation: Inkluder elevation data
        logger: Optional logger
        
    Returns:
        Rute dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if len(coordinates) < 2:
        logger.error("Mindst 2 koordinater påkrævet")
        return None
    
    client = HTTPClient(logger=logger, timeout=60)  # Længere timeout for waypoint ruter
    
    endpoint = f"{base_url}/route"
    
    try:
        from urllib.parse import urlencode
        
        # Byg query string med flere waypoints
        query_parts = []
        for lat, lon in coordinates:
            query_parts.append(f"point={lat},{lon}")
        
        query_parts.extend([
            f"vehicle={vehicle}",
            f"elevation={str(elevation).lower()}",
            "points_encoded=false",
            "instructions=true",  # Aktiver instructions for at få vejnavne til filtering
            # Brug standard CH (ikke disable) for gratis tier
            # "ch.disable=true",  # fjernet
            # Fjernet paid params
            f"key={api_key}"
        ])
        
        query_string = "&".join(query_parts)
        full_url = f"{endpoint}?{query_string}"
        
        response = client.get(full_url, timeout=60)
        
        if response.status_code != 200:
            logger.error(f"GraphHopper HTTP fejl: {response.status_code} - {response.text[:200]}")
            return None
        
        try:
            data = response.json()
        except Exception as e:
            logger.error(f"GraphHopper JSON parse fejl: {e} - Response: {response.text[:500]}")
            return None
        
        if not data or not isinstance(data, dict):
            logger.error(f"GraphHopper returnerede ugyldig data: {type(data)}")
            return None
        
        if "message" in data:
            logger.error(f"GraphHopper fejl: {data.get('message')}")
            return None
        
        paths = data.get("paths", [])
        if not paths or not isinstance(paths, list):
            logger.warning(f"Ingen ruter fundet i GraphHopper response. Paths type: {type(paths)}, value: {paths}")
            return None
        
        if len(paths) == 0:
            logger.warning("GraphHopper returnerede tom paths liste")
            return None
        
        route_data = paths[0]
        if not route_data or not isinstance(route_data, dict):
            logger.error(f"GraphHopper route_data er ikke en dict: {type(route_data)}")
            return None
        
        # Hent koordinater
        points = route_data.get("points") or {}
        route_coordinates = []
        
        if points and isinstance(points, dict):
            if "coordinates" in points:
                for coord in points["coordinates"]:
                    route_coordinates.append((coord[1], coord[0]))  # Konverter til (lat, lon)
            elif "type" in points and points["type"] == "LineString":
                coords = points.get("coordinates", [])
                for coord in coords:
                    route_coordinates.append((coord[1], coord[0]))
        
        # Hvis ingen koordinater fundet, prøv alternativ struktur
        if not route_coordinates:
            # GraphHopper kan også returnere koordinater direkte i response
            if "geometry" in route_data:
                geometry = route_data.get("geometry")
                if isinstance(geometry, dict) and "coordinates" in geometry:
                    for coord in geometry["coordinates"]:
                        route_coordinates.append((coord[1], coord[0]))
        
        # Hvis ingen koordinater fundet, returner None
        if not route_coordinates:
            logger.warning("Ingen koordinater fundet i GraphHopper response")
            return None
        
        distance_m = route_data.get("distance", 0)
        time_ms = route_data.get("time", 0)
        
        # Parse instructions for vejnavne (til filtering)
        steps = []
        instructions = route_data.get("instructions", [])
        if instructions and isinstance(instructions, list):
            for instr in instructions:
                if isinstance(instr, dict):
                    # GraphHopper instruction format: {"text": "...", "distance": ..., "time": ..., "interval": [...]}
                    step_text = instr.get("text", "")
                    step_dist = instr.get("distance", 0)  # i meter
                    # Ekstraher vejnavn fra instruction text
                    # GraphHopper format: "Continue onto Viborgvej", "Turn left onto Randersvej", "Keep left", etc.
                    road_name = ""
                    text_lower = step_text.lower()
                    if "onto" in text_lower:
                        # "Continue onto Viborgvej" eller "Turn left onto Randersvej"
                        parts = text_lower.split("onto")
                        if len(parts) > 1:
                            road_name = parts[1].strip()
                    elif "on " in text_lower:
                        # "Turn left on Randersvej" (uden "onto")
                        # Men skip "continue on" (ingen vejnavn)
                        if "continue" not in text_lower:
                            parts = text_lower.split("on ")
                            if len(parts) > 1:
                                road_name = parts[1].strip()
                    
                    if step_dist > 0:  # Kun tilføj steps med distance
                        steps.append({
                            "name": road_name,
                            "distance": step_dist,
                            "text": step_text
                        })
        
        result = {
            "distance": distance_m / 1000,
            "duration": time_ms / 60000,
            "coordinates": route_coordinates,
            "steps": steps,  # Tilføj steps med vejnavne
        }
        
        # Tilføj elevation data hvis tilgængelig
        if elevation:
            ascend = route_data.get("ascend", 0)
            descend = route_data.get("descend", 0)
            result["elevation_gain"] = ascend
            result["elevation_loss"] = descend
            
            # Hent elevation points
            points_for_elevation = route_data.get("points") or {}
            elevation_points = points_for_elevation.get("elevation", []) if isinstance(points_for_elevation, dict) else []
            if elevation_points and len(elevation_points) == len(route_coordinates):
                elevation_data = []
                cum_distance = 0
                for i, (coord, elev) in enumerate(zip(route_coordinates, elevation_points)):
                    if i > 0:
                        from math import radians, cos, sin, asin, sqrt
                        lat1, lon1 = route_coordinates[i-1]
                        lat2, lon2 = coord
                        dlat = radians(lat2 - lat1)
                        dlon = radians(lon2 - lon1)
                        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                        c = 2 * asin(sqrt(a))
                        cum_distance += c * 6371
                    
                    elevation_data.append({
                        'lat': coord[0],
                        'lon': coord[1],
                        'elevation': elev,
                        'distance': cum_distance
                    })
                result["elevation"] = elevation_data
            
            if distance_m > 0:
                max_gradient = (ascend / distance_m) * 100 if distance_m > 0 else 0
                result["max_gradient"] = max_gradient
                result["avg_gradient"] = (ascend / distance_m) * 100 if distance_m > 0 else 0
        
        return result
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af waypoint rute fra GraphHopper: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

