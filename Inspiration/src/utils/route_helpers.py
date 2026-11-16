"""
Helper funktioner til rute generering og filtrering.
"""

import math
from typing import List, Tuple, Optional, Dict, Any
import logging


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Beregner bearing (retning) mellem to punkter i grader.
    0 = Nord, 90 = Øst, 180 = Syd, 270 = Vest
    
    Args:
        lat1, lon1: Første punkt
        lat2, lon2: Andet punkt
        
    Returns:
        Bearing i grader (0-360)
    """
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    bearing_deg = math.degrees(bearing)
    bearing_deg = (bearing_deg + 360) % 360
    
    return bearing_deg


def get_direction_name(bearing: float) -> str:
    """
    Konverterer bearing til retningsnavn.
    
    Args:
        bearing: Bearing i grader (0-360)
        
    Returns:
        Retningsnavn (nord, nordøst, øst, etc.)
    """
    directions = [
        "nord", "nordøst", "øst", "sydøst",
        "syd", "sydvest", "vest", "nordvest"
    ]
    index = round(bearing / 45) % 8
    return directions[index]


def is_in_direction(
    start_lat: float,
    start_lon: float,
    point_lat: float,
    point_lon: float,
    target_direction: str
) -> bool:
    """
    Tjekker om et punkt er i en bestemt retning fra startpunktet.
    
    Args:
        start_lat, start_lon: Startpunkt
        point_lat, point_lon: Punkt at tjekke
        target_direction: Retning (nord, syd, vest, øst, nordøst, etc.)
        
    Returns:
        True hvis punktet er i den ønskede retning
    """
    bearing = calculate_bearing(start_lat, start_lon, point_lat, point_lon)
    direction = get_direction_name(bearing)
    
    # Normaliser retninger
    target_direction = target_direction.lower()
    
    # Tjek om retningen matcher
    if target_direction == "nord":
        return 315 <= bearing or bearing <= 45
    elif target_direction == "syd":
        return 135 <= bearing <= 225
    elif target_direction == "vest":
        return 225 <= bearing <= 315
    elif target_direction == "øst":
        return 45 <= bearing <= 135
    elif target_direction == "nordøst":
        return 0 <= bearing <= 90
    elif target_direction == "sydøst":
        return 90 <= bearing <= 180
    elif target_direction == "sydvest":
        return 180 <= bearing <= 270
    elif target_direction == "nordvest":
        return 270 <= bearing <= 360
    else:
        # Hvis retning ikke er specificeret, accepter alle
        return True


def generate_loop_waypoints(
    start_lat: float,
    start_lon: float,
    target_distance_km: float,
    direction: Optional[str] = None,
    num_waypoints: int = 5
) -> List[Tuple[float, float]]:
    """
    Genererer waypoints for en rigtig loop rute med flere waypoints.
    Baseret på eksempler fra RideWithGPS - loops har mange waypoints der danner en cirkulær rute.
    
    Args:
        start_lat, start_lon: Startpunkt (og slutpunkt for loop)
        target_distance_km: Mål distance for hele loop ruten
        direction: Retning (nord, syd, vest, øst) eller None for alle retninger
        num_waypoints: Antal waypoints at generere (standard 5 for god variation)
        
    Returns:
        Liste af (lat, lon) waypoints (inkluder start/slut som første og sidste)
    """
    # For en rigtig loop: start -> waypoint1 -> waypoint2 -> ... -> waypointN -> start
    # Vi genererer waypoints i en cirkel omkring startpunktet
    # Radius beregnes baseret på target distance og antal waypoints
    
    # Estimer radius: for en cirkulær rute med N waypoints
    # Circumference ≈ 2 * π * radius
    # Hvis vi har N waypoints, er distance mellem waypoints ≈ circumference / N
    # Total distance ≈ N * (distance mellem waypoints)
    # Så radius ≈ target_distance_km / (2 * π)
    radius_km = target_distance_km / (2 * math.pi)
    radius_deg = radius_km / 111.0  # Konverter til grader
    
    waypoints = []
    
    # Generer waypoints i en cirkel omkring startpunktet
    for i in range(num_waypoints):
        # Vinkel i radianer - fordelt jævnt rundt
        angle = (2 * math.pi * i) / num_waypoints
        
        # Juster vinkel baseret på retning hvis specificeret
        if direction:
            direction_angles = {
                "nord": math.pi / 2,      # 90 grader
                "syd": -math.pi / 2,      # -90 grader
                "vest": math.pi,           # 180 grader
                "øst": 0,                 # 0 grader
                "nordøst": math.pi / 4,   # 45 grader
                "sydøst": -math.pi / 4,   # -45 grader
                "sydvest": -3 * math.pi / 4,  # -135 grader
                "nordvest": 3 * math.pi / 4   # 135 grader
            }
            base_angle = direction_angles.get(direction.lower(), 0)
            # Roter hele cirklen baseret på retning
            angle += base_angle
        
        # Beregn waypoint koordinater
        waypoint_lat = start_lat + radius_deg * math.sin(angle)
        waypoint_lon = start_lon + radius_deg * math.cos(angle)
        
        waypoints.append((waypoint_lat, waypoint_lon))
    
    return waypoints


def filter_route_by_distance(
    route: Dict[str, Any],
    min_distance_km: Optional[float] = None,
    max_distance_km: Optional[float] = None,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Filtrerer rute baseret på distance.
    
    Args:
        route: Rute data dict
        min_distance_km: Minimum distance (None = ingen minimum)
        max_distance_km: Maksimum distance (None = ingen maksimum)
        logger: Optional logger
        
    Returns:
        True hvis ruten opfylder kriterierne
    """
    distance = route.get('distance', 0)
    
    if min_distance_km is not None and distance < min_distance_km:
        if logger:
            logger.debug(f"Rute filtreret: {distance:.2f} km < {min_distance_km} km (minimum)")
        return False
    
    if max_distance_km is not None and distance > max_distance_km:
        if logger:
            logger.debug(f"Rute filtreret: {distance:.2f} km > {max_distance_km} km (maksimum)")
        return False
    
    return True


def filter_route_by_elevation(
    route: Dict[str, Any],
    min_elevation_gain_m: Optional[float] = None,
    max_elevation_gain_m: Optional[float] = None,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Filtrerer rute baseret på højdemeter.
    
    Args:
        route: Rute data dict
        min_elevation_gain_m: Minimum højdemeter (None = ingen minimum)
        max_elevation_gain_m: Maksimum højdemeter (None = ingen maksimum)
        logger: Optional logger
        
    Returns:
        True hvis ruten opfylder kriterierne
    """
    elevation_gain = route.get('elevation_gain')
    
    if elevation_gain is None:
        # Hvis elevation data ikke er tilgængelig, accepter ruten
        # (da ikke alle routing providers understøtter elevation)
        return True
    
    if min_elevation_gain_m is not None and elevation_gain < min_elevation_gain_m:
        if logger:
            logger.debug(f"Rute filtreret: {elevation_gain:.0f} m < {min_elevation_gain_m} m (minimum)")
        return False
    
    if max_elevation_gain_m is not None and elevation_gain > max_elevation_gain_m:
        if logger:
            logger.debug(f"Rute filtreret: {elevation_gain:.0f} m > {max_elevation_gain_m} m (maksimum)")
        return False
    
    return True

