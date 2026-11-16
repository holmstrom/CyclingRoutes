"""
Route validator til at tjekke rute kvalitet:
- Ingen overlappende sektioner (max 20% overlap)
- Simpel loop struktur
- Prioriterer små landeveje
"""

import logging
import math
from typing import List, Tuple, Optional, Dict, Any


def check_route_overlap(
    route_coordinates: List[Tuple[float, float]],
    max_overlap_percent: float = 20.0,
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Tjekker om ruten har overlappende sektioner.
    
    Args:
        route_coordinates: Liste af koordinater i ruten
        max_overlap_percent: Maksimal overlap procent (default 20%)
        logger: Optional logger
        
    Returns:
        Dict med overlap information
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if len(route_coordinates) < 10:
        return {
            'has_overlap': False,
            'overlap_percent': 0.0,
            'overlap_segments': []
        }
    
    # Del ruten op i segmenter og tjek for overlap
    segment_length = max(5, len(route_coordinates) // 50)  # ~50 segmenter
    segments = []
    
    for i in range(0, len(route_coordinates) - segment_length, segment_length):
        segment = route_coordinates[i:i + segment_length]
        if len(segment) >= 2:
            segments.append({
                'start_idx': i,
                'end_idx': min(i + segment_length, len(route_coordinates)),
                'coords': segment
            })
    
    # Tjek hvert segment mod alle andre segmenter
    overlapping_segments = []
    total_overlap_distance = 0.0
    
    for i, seg1 in enumerate(segments):
        for j, seg2 in enumerate(segments[i + 2:], start=i + 2):  # Skip nabo segmenter
            # Tjek om segmenterne overlapper
            overlap = _check_segment_overlap(seg1['coords'], seg2['coords'])
            if overlap > 0:
                overlap_distance = _calculate_segment_distance(seg1['coords'])
                total_overlap_distance += overlap_distance
                overlapping_segments.append({
                    'segment1': (seg1['start_idx'], seg1['end_idx']),
                    'segment2': (seg2['start_idx'], seg2['end_idx']),
                    'overlap_distance': overlap_distance
                })
    
    # Beregn total distance
    total_distance = _calculate_route_distance(route_coordinates)
    
    # Beregn overlap procent
    overlap_percent = (total_overlap_distance / total_distance * 100) if total_distance > 0 else 0.0
    
    has_overlap = overlap_percent > max_overlap_percent
    
    if has_overlap:
        logger.debug(f"Rute har {overlap_percent:.1f}% overlap (max: {max_overlap_percent}%)")
    
    return {
        'has_overlap': has_overlap,
        'overlap_percent': overlap_percent,
        'overlap_segments': overlapping_segments,
        'total_distance': total_distance
    }


def _check_segment_overlap(
    seg1: List[Tuple[float, float]],
    seg2: List[Tuple[float, float]]
) -> float:
    """Tjekker om to segmenter overlapper."""
    if len(seg1) < 2 or len(seg2) < 2:
        return 0.0
    
    # Tjek om nogen koordinater i seg1 er tæt på koordinater i seg2
    overlap_count = 0
    threshold = 0.001  # ~100 meter
    
    for coord1 in seg1:
        for coord2 in seg2:
            distance = _haversine_distance(coord1, coord2)
            if distance < threshold:
                overlap_count += 1
                break
    
    # Hvis mere end 50% af koordinaterne overlapper, betragt det som overlap
    if overlap_count > len(seg1) * 0.5:
        return 1.0
    
    return 0.0


def _calculate_segment_distance(coords: List[Tuple[float, float]]) -> float:
    """Beregner distance for et segment."""
    if len(coords) < 2:
        return 0.0
    
    total = 0.0
    for i in range(len(coords) - 1):
        total += _haversine_distance(coords[i], coords[i + 1])
    
    return total


def _calculate_route_distance(coords: List[Tuple[float, float]]) -> float:
    """Beregner total distance for en rute."""
    return _calculate_segment_distance(coords)


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


def validate_route_structure(
    route_coordinates: List[Tuple[float, float]],
    start_coord: Tuple[float, float],
    end_coord: Tuple[float, float],
    logger: Optional[logging.Logger] = None
) -> Dict[str, Any]:
    """
    Validerer at ruten er en simpel loop struktur.
    
    Args:
        route_coordinates: Liste af koordinater
        start_coord: Start koordinat
        end_coord: Slut koordinat (skal være tæt på start)
        logger: Optional logger
        
    Returns:
        Dict med validering resultat
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Tjek at start og slut er tæt på hinanden (loop)
    start_end_distance = _haversine_distance(start_coord, end_coord)
    is_loop = start_end_distance < 0.5  # Mindre end 500 meter
    
    # Tjek for for mange afvigelser (for mange skarpe sving)
    sharp_turns = 0
    for i in range(2, len(route_coordinates) - 2):
        prev = route_coordinates[i - 2]
        curr = route_coordinates[i]
        next_p = route_coordinates[i + 2]
        
        angle1 = _calculate_bearing(prev[0], prev[1], curr[0], curr[1])
        angle2 = _calculate_bearing(curr[0], curr[1], next_p[0], next_p[1])
        
        angle_change = abs(angle2 - angle1)
        if angle_change > 180:
            angle_change = 360 - angle_change
        
        # Skarpt sving = mere end 120 grader
        if angle_change > 120:
            sharp_turns += 1
    
    # For mange skarpe sving = for mange afvigelser
    max_sharp_turns = len(route_coordinates) // 50  # Max 1 per 50 koordinater
    too_many_deviations = sharp_turns > max_sharp_turns
    
    return {
        'is_loop': is_loop,
        'start_end_distance_km': start_end_distance,
        'sharp_turns': sharp_turns,
        'too_many_deviations': too_many_deviations,
        'valid': is_loop and not too_many_deviations
    }


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

