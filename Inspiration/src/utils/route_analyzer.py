"""
Analyzer til at lære fra eksisterende GPX ruter.
Analyserer waypoint patterns og retninger fra gode ruter.
"""

import gpxpy
import gpxpy.gpx
import logging
import math
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path


def analyze_gpx_route(gpx_file: str, logger: Optional[logging.Logger] = None) -> Optional[Dict[str, Any]]:
    """
    Analyserer en GPX fil og ekstraherer waypoint patterns.
    
    Args:
        gpx_file: Sti til GPX fil
        logger: Optional logger
        
    Returns:
        Dict med route analysis data eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        with open(gpx_file, 'r', encoding='utf-8') as f:
            gpx = gpxpy.parse(f)
        
        # Hent alle koordinater fra tracks
        all_coords = []
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    all_coords.append((point.latitude, point.longitude))
        
        if len(all_coords) < 10:
            logger.debug(f"GPX fil har for få koordinater: {len(all_coords)}")
            return None
        
        # Beregn waypoints (samplere koordinater)
        # For simplere loops: vælg 3-4 waypoints jævnt fordelt
        # Dette giver bedre match med vores simple loop strategi
        num_waypoints = min(4, max(3, len(all_coords) // 200))  # 3-4 waypoints
        waypoint_indices = [int(i * len(all_coords) / (num_waypoints + 1)) for i in range(1, num_waypoints + 1)]
        waypoints = [all_coords[i] for i in waypoint_indices]
        
        # Beregn start og slut
        start_coord = all_coords[0]
        end_coord = all_coords[-1]
        
        # Beregn distance
        total_distance = 0.0
        for i in range(len(all_coords) - 1):
            total_distance += _haversine_distance(all_coords[i], all_coords[i + 1])
        
        # Beregn retninger fra start
        directions = []
        for wp in waypoints[:5]:  # Første 5 waypoints
            bearing = _calculate_bearing(start_coord[0], start_coord[1], wp[0], wp[1])
            direction_name = _bearing_to_direction(bearing)
            directions.append(direction_name)
        
        # Analyser vinkelændringer (undgå lige stykker)
        angle_changes = []
        for i in range(1, len(waypoints) - 1):
            prev = waypoints[i - 1]
            curr = waypoints[i]
            next_wp = waypoints[i + 1]
            
            angle1 = _calculate_bearing(prev[0], prev[1], curr[0], curr[1])
            angle2 = _calculate_bearing(curr[0], curr[1], next_wp[0], next_wp[1])
            
            angle_change = abs(angle2 - angle1)
            if angle_change > 180:
                angle_change = 360 - angle_change
            
            angle_changes.append(angle_change)
        
        avg_angle_change = sum(angle_changes) / len(angle_changes) if angle_changes else 0
        
        # Beregn radius (gennemsnitlig afstand fra start)
        distances_from_start = [_haversine_distance(start_coord, wp) for wp in waypoints]
        avg_radius = sum(distances_from_start) / len(distances_from_start) if distances_from_start else 0
        
        return {
            'start_coord': start_coord,
            'end_coord': end_coord,
            'waypoints': waypoints,
            'total_distance_km': total_distance,
            'directions': directions,
            'avg_angle_change': avg_angle_change,
            'avg_radius_km': avg_radius,
            'num_coords': len(all_coords),
            'num_waypoints': len(waypoints)
        }
        
    except Exception as e:
        logger.error(f"Fejl ved analyse af GPX fil {gpx_file}: {e}")
        return None


def extract_waypoint_patterns(gpx_dir: str, logger: Optional[logging.Logger] = None) -> List[Dict[str, Any]]:
    """
    Ekstraherer waypoint patterns fra alle GPX filer i en mappe.
    
    Args:
        gpx_dir: Mappe med GPX filer
        logger: Optional logger
        
    Returns:
        Liste af route analysis data
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    patterns = []
    gpx_path = Path(gpx_dir)
    
    if not gpx_path.exists():
        logger.warning(f"GPX mappe findes ikke: {gpx_dir}")
        return patterns
    
    # Søg rekursivt efter GPX filer
    gpx_files = list(gpx_path.rglob("*.gpx"))
    logger.info(f"Finder {len(gpx_files)} GPX filer i {gpx_dir} (rekursivt)")
    
    for gpx_file in gpx_files:
        analysis = analyze_gpx_route(str(gpx_file), logger)
        if analysis:
            patterns.append(analysis)
            logger.debug(f"Analyseret {gpx_file.name}: {analysis['total_distance_km']:.2f} km, {analysis['num_waypoints']} waypoints")
    
    logger.info(f"Ekstraheret {len(patterns)} waypoint patterns")
    return patterns


def learn_from_patterns(
    patterns: List[Dict[str, Any]],
    target_distance_km: float,
    direction: Optional[str] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[List[Tuple[float, float]]]:
    """
    Lærer waypoint patterns fra eksisterende ruter og genererer nye waypoints.
    
    Args:
        patterns: Liste af route analysis data
        target_distance_km: Mål distance
        direction: Ønsket retning (nord, syd, vest, øst)
        logger: Optional logger
        
    Returns:
        Liste af waypoints eller None
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if not patterns:
        return None
    
    # Find lignende ruter (distance inden for 30%)
    similar_patterns = [
        p for p in patterns
        if 0.7 * target_distance_km <= p['total_distance_km'] <= 1.3 * target_distance_km
    ]
    
    if not similar_patterns:
        # Brug alle hvis ingen lignende
        similar_patterns = patterns
    
    # Filtrer på retning hvis specificeret
    if direction:
        direction_filtered = []
        direction_lower = direction.lower()
        for p in similar_patterns:
            # Tjek om første waypoint er i ønsket retning
            if p['directions']:
                first_direction = p['directions'][0].lower()
                # Tjek om retningen matcher (inkluder også nærliggende retninger)
                if first_direction == direction_lower:
                    direction_filtered.append(p)
                # For vest: accepter også sydvest og nordvest
                elif direction_lower == "vest" and first_direction in ["vest", "sydvest", "nordvest"]:
                    direction_filtered.append(p)
                # For nord: accepter også nordøst og nordvest
                elif direction_lower == "nord" and first_direction in ["nord", "nordøst", "nordvest"]:
                    direction_filtered.append(p)
                # For syd: accepter også sydøst og sydvest
                elif direction_lower == "syd" and first_direction in ["syd", "sydøst", "sydvest"]:
                    direction_filtered.append(p)
                # For øst: accepter også nordøst og sydøst
                elif direction_lower == "øst" and first_direction in ["øst", "nordøst", "sydøst"]:
                    direction_filtered.append(p)
        
        if direction_filtered:
            similar_patterns = direction_filtered
            logger.info(f"Filtreret til {len(similar_patterns)} ruter i retning {direction} (fra {len(patterns)} total)")
        else:
            # Hvis ingen matcher præcist, prøv at finde ruter der primært går i retningen
            logger.debug(f"Ingen ruter matcher præcist retning {direction}, prøver at finde nærliggende")
            # Tjek gennemsnitlig retning for første 3 waypoints
            for p in similar_patterns:
                if p['directions'] and len(p['directions']) >= 3:
                    avg_direction = p['directions'][0:3]  # Første 3 retninger
                    # Hvis mindst 2 af 3 går i ønsket retning eller nærliggende
                    matches = sum(1 for d in avg_direction if d.lower() == direction_lower or 
                                 (direction_lower == "vest" and d.lower() in ["vest", "sydvest", "nordvest"]) or
                                 (direction_lower == "nord" and d.lower() in ["nord", "nordøst", "nordvest"]) or
                                 (direction_lower == "syd" and d.lower() in ["syd", "sydøst", "sydvest"]) or
                                 (direction_lower == "øst" and d.lower() in ["øst", "nordøst", "sydøst"]))
                    if matches >= 2:
                        direction_filtered.append(p)
            
            if direction_filtered:
                similar_patterns = direction_filtered
                logger.info(f"Fundet {len(similar_patterns)} ruter med primær retning {direction}")
    
    if not similar_patterns:
        return None
    
    # Vælg det bedste match (tættest på target distance)
    best_pattern = min(similar_patterns, key=lambda p: abs(p['total_distance_km'] - target_distance_km))
    
    # Skaler waypoints til target distance
    scale_factor = target_distance_km / best_pattern['total_distance_km']
    
    # Returner waypoints fra det bedste match (de skal senere justeres til start koordinater)
    # Vi returnerer waypoints relativt til deres oprindelige start, så de kan justeres senere
    logger.info(f"Lært waypoint pattern fra {best_pattern['total_distance_km']:.2f} km rute, skal skalere til {target_distance_km:.2f} km")
    
    # Skaler waypoints relativt til start
    start_coord = best_pattern['start_coord']
    scaled_waypoints = []
    
    for wp in best_pattern['waypoints']:
        # Beregn offset fra start
        lat_offset = (wp[0] - start_coord[0]) * scale_factor
        lon_offset = (wp[1] - start_coord[1]) * scale_factor
        
        # Tilføj skaleret offset
        scaled_lat = start_coord[0] + lat_offset
        scaled_lon = start_coord[1] + lon_offset
        
        scaled_waypoints.append((scaled_lat, scaled_lon))
    
    return scaled_waypoints


def _haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """Beregner distance mellem to koordinater i km."""
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    
    R = 6371  # Earth radius in km
    
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def _calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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


def _bearing_to_direction(bearing: float) -> str:
    """Konverterer bearing til retningsnavn."""
    directions = ["Nord", "Nordøst", "Øst", "Sydøst", "Syd", "Sydvest", "Vest", "Nordvest"]
    index = int((bearing + 22.5) / 45) % 8
    return directions[index]

