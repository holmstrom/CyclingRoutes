"""
Route optimizer til at forbedre waypoint generering baseret på eksisterende gode ruter.
Undgår lange lige stykker og veje der afviger fra ruten.
"""

import math
import logging
from typing import List, Tuple, Optional, Dict, Any
from .route_cache import RouteCache
from .route_analyzer import extract_waypoint_patterns, learn_from_patterns


def optimize_waypoints_for_variation(
    waypoints: List[Tuple[float, float]],
    min_angle_change: float = 35.0,  # Strammere for at undgå lange lige stykker
    logger: Optional[logging.Logger] = None
) -> List[Tuple[float, float]]:
    """
    Optimerer waypoints for at undgå lange lige stykker.
    Fjerner waypoints der skaber for lige stykker.
    
    Args:
        waypoints: Liste af waypoint koordinater
        min_angle_change: Minimum vinkelændring mellem waypoints (grader)
        logger: Optional logger
        
    Returns:
        Optimerede waypoints
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if len(waypoints) < 3:
        return waypoints
    
    optimized = [waypoints[0]]  # Behold første
    
    for i in range(1, len(waypoints) - 1):
        prev_wp = waypoints[i - 1]
        current_wp = waypoints[i]
        next_wp = waypoints[i + 1]
        
        # Beregn vinkler
        angle1 = calculate_bearing(prev_wp[0], prev_wp[1], current_wp[0], current_wp[1])
        angle2 = calculate_bearing(current_wp[0], current_wp[1], next_wp[0], next_wp[1])
        
        # Beregn vinkelændring
        angle_change = abs(angle2 - angle1)
        if angle_change > 180:
            angle_change = 360 - angle_change
        
        # Behold waypoint hvis vinkelændring er stor nok
        if angle_change >= min_angle_change:
            optimized.append(current_wp)
        else:
            logger.debug(f"Fjerner waypoint {i} - for lille vinkelændring: {angle_change:.1f}°")
    
    optimized.append(waypoints[-1])  # Behold sidste
    
    return optimized


def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Beregner bearing mellem to punkter i grader."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) - 
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))
    
    bearing = math.atan2(y, x)
    bearing_deg = math.degrees(bearing)
    return (bearing_deg + 360) % 360


def generate_smart_waypoints(
    start_lat: float,
    start_lon: float,
    target_distance_km: float,
    direction: Optional[str] = None,
    num_waypoints: int = 5,
    route_cache: Optional[RouteCache] = None,
    gpx_routes_dir: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> List[Tuple[float, float]]:
    """
    Genererer smarte waypoints der undgår lange lige stykker.
    Lærer fra eksisterende gode ruter hvis cache er tilgængelig.
    
    Args:
        start_lat, start_lon: Startpunkt
        target_distance_km: Mål distance for loop
        direction: Retning (nord, syd, vest, øst)
        num_waypoints: Antal waypoints
        route_cache: RouteCache instance (hvis tilgængelig)
        gpx_routes_dir: Mappe med GPX ruter at lære fra (hvis tilgængelig)
        logger: Optional logger
        
    Returns:
        Liste af waypoints
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # PRIORITET 1: Lær fra eksisterende GPX ruter (bedste kvalitet)
    if gpx_routes_dir:
        try:
            logger.info(f"Lærer fra GPX ruter i: {gpx_routes_dir}")
            patterns = extract_waypoint_patterns(gpx_routes_dir, logger)
            if patterns:
                logger.info(f"Analyseret {len(patterns)} GPX ruter, søger efter match...")
                learned_waypoints = learn_from_patterns(
                    patterns,
                    target_distance_km,
                    direction,
                    logger
                )
                if learned_waypoints:
                    logger.info(f"✅ Lært waypoint pattern fra eksisterende ruter ({len(learned_waypoints)} waypoints)")
                    # learned_waypoints er allerede relativt til pattern start
                    # Vi skal finde pattern start og justere waypoints til vores start
                    if patterns:
                        # Find pattern start fra det bedste match (samme som i learn_from_patterns)
                        similar_patterns = [
                            p for p in patterns
                            if 0.7 * target_distance_km <= p['total_distance_km'] <= 1.3 * target_distance_km
                        ]
                        if not similar_patterns:
                            similar_patterns = patterns
                        
                        # Filtrer på retning hvis specificeret
                        if direction:
                            direction_filtered = [
                                p for p in similar_patterns
                                if p.get('directions') and p['directions'][0].lower() == direction.lower()
                            ]
                            if direction_filtered:
                                similar_patterns = direction_filtered
                        
                        best_pattern = min(similar_patterns, key=lambda p: abs(p['total_distance_km'] - target_distance_km))
                        pattern_start = best_pattern['start_coord']
                        
                        # Beregn offset og juster waypoints til vores start koordinater
                        offset_lat = start_lat - pattern_start[0]
                        offset_lon = start_lon - pattern_start[1]
                        
                        adjusted_waypoints = [
                            (wp[0] + offset_lat, wp[1] + offset_lon)
                            for wp in learned_waypoints
                        ]
                        
                        # Reducer til max num_waypoints hvis nødvendigt
                        # GraphHopper gratis tier: max 5 points total (start + waypoints + slut)
                        # Så max waypoints = 3 (start + 3 waypoints + slut = 5)
                        max_allowed_waypoints = min(num_waypoints, 3)  # GraphHopper limit
                        if len(adjusted_waypoints) > max_allowed_waypoints:
                            # Vælg waypoints jævnt fordelt
                            step = len(adjusted_waypoints) / max_allowed_waypoints
                            adjusted_waypoints = [
                                adjusted_waypoints[int(i * step)]
                                for i in range(max_allowed_waypoints)
                            ]
                        
                        logger.info(f"Bruger {len(adjusted_waypoints)} waypoints fra eksisterende ruter (justeret til start: {start_lat:.4f}, {start_lon:.4f})")
                        return adjusted_waypoints
                else:
                    logger.debug(f"Kunne ikke finde match blandt {len(patterns)} ruter for distance {target_distance_km:.1f} km, retning {direction}")
            else:
                logger.debug(f"Ingen GPX ruter fundet i {gpx_routes_dir}")
        except Exception as e:
            logger.warning(f"Kunne ikke lære fra GPX ruter: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    # PRIORITET 2: Prøv at hente lignende waypoints fra cache
    if route_cache:
        start_coords = (start_lat, start_lon)
        similar_waypoints = route_cache.get_similar_waypoints(
            start_coords,
            target_distance_km,
            direction,
            num_suggestions=1
        )
        
        if similar_waypoints:
            logger.debug("Bruger waypoints fra cache")
            # Skalere waypoints til target distance
            cached_waypoints = similar_waypoints[0]
            cached_distance = _estimate_route_distance(start_coords, cached_waypoints)
            
            if cached_distance > 0:
                scale_factor = target_distance_km / cached_distance
                scaled_waypoints = _scale_waypoints(start_coords, cached_waypoints, scale_factor)
                return scaled_waypoints
    
    # Generer simple waypoints for en simpel loop
    # Strategi: Færre waypoints, mere direkte loop i den ønskede retning
    # For en loop: start -> waypoint1 (i retning) -> waypoint2 (perpendikulær) -> waypoint3 (tilbage) -> start
    
    # Reducer antal waypoints for simplere loop (3-4 waypoints er nok)
    num_waypoints = min(num_waypoints, 4)
    
    # Beregn radius baseret på target distance
    # For en simpel loop med få waypoints: radius ≈ distance / (2 * num_waypoints)
    radius_km = target_distance_km / (2 * num_waypoints * 1.5)  # Faktor 1.5 for at kompensere for kurver
    radius_deg = radius_km / 111.0
    
    waypoints = []
    
    # Generer waypoints i en simpel form baseret på retning
    if direction:
        direction_angles = {
            "nord": math.pi / 2,
            "syd": -math.pi / 2,
            "vest": math.pi,
            "øst": 0,
            "nordøst": math.pi / 4,
            "sydøst": -math.pi / 4,
            "sydvest": -3 * math.pi / 4,
            "nordvest": 3 * math.pi / 4
        }
        primary_angle = direction_angles.get(direction.lower(), 0)
        
        # Generer waypoints i en simpel form:
        # 1. Første waypoint: Primær retning
        # 2. Anden waypoint: Perpendikulær til højre
        # 3. Tredje waypoint: Modsat retning
        # 4. Fjerde waypoint: Perpendikulær til venstre (hvis 4 waypoints)
        
        for i in range(num_waypoints):
            if i == 0:
                # Første waypoint: Primær retning
                angle = primary_angle + (0.05 * math.sin(i))  # lille jitter
                current_radius = radius_deg * 1.1
            elif i == 1:
                # Anden waypoint: Perpendikulær til højre (90 grader)
                angle = primary_angle + math.pi / 2 + (0.05 * math.cos(i))
                current_radius = radius_deg * 0.9
            elif i == 2:
                # Tredje waypoint: Modsat retning
                angle = primary_angle + math.pi + (0.05 * math.sin(i + 1))
                current_radius = radius_deg * 1.0
            else:  # i == 3
                # Fjerde waypoint: Perpendikulær til venstre
                angle = primary_angle - math.pi / 2 + (0.05 * math.cos(i + 1))
                current_radius = radius_deg * 0.9
            
            waypoint_lat = start_lat + current_radius * math.sin(angle)
            waypoint_lon = start_lon + current_radius * math.cos(angle)
            waypoints.append((waypoint_lat, waypoint_lon))
    else:
        # Ingen retning: Generer simpel cirkulær loop
        for i in range(num_waypoints):
            angle = (2 * math.pi * i) / num_waypoints
            # Varier radius lidt for at undgå perfekt cirkel
            radius_variation = 0.9 + (i % 2) * 0.1
            current_radius = radius_deg * radius_variation
            
            waypoint_lat = start_lat + current_radius * math.sin(angle)
            waypoint_lon = start_lon + current_radius * math.cos(angle)
            waypoints.append((waypoint_lat, waypoint_lon))
    
    return waypoints


def _estimate_route_distance(
    start_coords: Tuple[float, float],
    waypoints: List[Tuple[float, float]]
) -> float:
    """Estimerer distance for en rute baseret på waypoints."""
    if not waypoints:
        return 0.0
    
    total_distance = 0.0
    prev_coord = start_coords
    
    for wp in waypoints:
        # Haversine distance
        from math import radians, cos, sin, asin, sqrt
        lat1, lon1 = prev_coord
        lat2, lon2 = wp
        
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        total_distance += c * 6371  # Earth radius in km
        
        prev_coord = wp
    
    return total_distance


def _scale_waypoints(
    start_coords: Tuple[float, float],
    waypoints: List[Tuple[float, float]],
    scale_factor: float
) -> List[Tuple[float, float]]:
    """Skalerer waypoints relativt til startpunktet."""
    scaled = []
    start_lat, start_lon = start_coords
    
    for wp_lat, wp_lon in waypoints:
        # Beregn offset fra start
        lat_offset = (wp_lat - start_lat) * scale_factor
        lon_offset = (wp_lon - start_lon) * scale_factor
        
        # Tilføj skaleret offset
        scaled_lat = start_lat + lat_offset
        scaled_lon = start_lon + lon_offset
        
        scaled.append((scaled_lat, scaled_lon))
    
    return scaled


def evaluate_route_quality(
    route_coordinates: List[Tuple[float, float]],
    waypoints: List[Tuple[float, float]],
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Evaluerer kvaliteten af en rute.
    Tjekker for lange lige stykker og veje der afviger fra waypoints.
    
    Args:
        route_coordinates: Liste af koordinater i ruten
        waypoints: Liste af waypoint koordinater
        logger: Optional logger
        
    Returns:
        Dict med kvalitets score og detaljer
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if len(route_coordinates) < 3:
        return {'score': 0.5, 'has_straight_sections': False, 'deviates_from_waypoints': False}
    
    # Tjek for lange lige stykker (skærpet)
    max_straight_distance = 0
    straight_sections = 0
    
    # Analyser ruten i segmenter
    segment_size = max(10, len(route_coordinates) // 20)  # 20 segmenter
    
    for i in range(0, len(route_coordinates) - segment_size, segment_size):
        segment = route_coordinates[i:i + segment_size]
        if len(segment) < 3:
            continue
        
        # Beregn gennemsnitlig vinkelændring i segmentet
        angle_changes = []
        for j in range(1, len(segment) - 1):
            prev = segment[j - 1]
            curr = segment[j]
            next_p = segment[j + 1]
            
            angle1 = calculate_bearing(prev[0], prev[1], curr[0], curr[1])
            angle2 = calculate_bearing(curr[0], curr[1], next_p[0], next_p[1])
            
            angle_change = abs(angle2 - angle1)
            if angle_change > 180:
                angle_change = 360 - angle_change
            
            angle_changes.append(angle_change)
        
        if angle_changes:
            avg_angle_change = sum(angle_changes) / len(angle_changes)
            # Hvis gennemsnitlig vinkelændring er meget lille, er det et lige stykke
            if avg_angle_change < 8.0:  # Strammere grænse
                straight_sections += 1
                # Beregn distance for dette segment
                from math import radians, cos, sin, asin, sqrt
                segment_distance = 0
                for k in range(len(segment) - 1):
                    lat1, lon1 = segment[k]
                    lat2, lon2 = segment[k + 1]
                    dlat = radians(lat2 - lat1)
                    dlon = radians(lon2 - lon1)
                    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    segment_distance += c * 6371
                max_straight_distance = max(max_straight_distance, segment_distance)
    
    # Tjek om ruten følger waypoints
    deviates_from_waypoints = False
    if waypoints:
        # For hvert waypoint, find nærmeste punkt i ruten
        max_deviation = 0
        for wp in waypoints:
            # Find nærmeste punkt i ruten
            min_dist = float('inf')
            for coord in route_coordinates:
                from math import radians, cos, sin, asin, sqrt
                lat1, lon1 = wp
                lat2, lon2 = coord
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                dist = c * 6371
                min_dist = min(min_dist, dist)
            
            max_deviation = max(max_deviation, min_dist)
        
        # Hvis waypoints er mere end 2 km fra ruten, afviger den
        if max_deviation > 2.0:
            deviates_from_waypoints = True
    
    # Beregn score (0-1, højere er bedre)
    score = 1.0
    
    # Straff for lige stykker (skærpet)
    if max_straight_distance > 1.0:  # Mere end 1 km lige
        score -= 0.3
    elif max_straight_distance > 0.8:
        score -= 0.15

    if straight_sections > 2:
        score -= 0.2
    
    # Straff for afvigelse fra waypoints
    if deviates_from_waypoints:
        score -= 0.3
    
    score = max(0.0, min(1.0, score))
    
    return {
        'score': score,
        'has_straight_sections': max_straight_distance > 1.5,
        'max_straight_distance_km': max_straight_distance,
        'straight_sections_count': straight_sections,
        'deviates_from_waypoints': deviates_from_waypoints
    }

