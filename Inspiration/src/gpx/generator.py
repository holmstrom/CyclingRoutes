"""
GPX fil generator.
Genererer GPX filer fra rute koordinater.
"""

import gpxpy
import gpxpy.gpx
from typing import List, Tuple, Optional
from datetime import datetime
import logging


def create_gpx_from_coordinates(
    coordinates: List[Tuple[float, float]],
    name: str = "Cykelrute",
    description: str = "",
    logger: Optional[logging.Logger] = None
) -> gpxpy.gpx.GPX:
    """
    Opretter en GPX fil fra en liste af koordinater.
    Optimeret for Garmin og Wahoo kompatibilitet.
    
    Args:
        coordinates: Liste af (lat, lon) tuples
        name: Rute navn
        description: Rute beskrivelse
        logger: Optional logger
        
    Returns:
        GPX objekt
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    gpx = gpxpy.gpx.GPX()
    
    # Opret track i stedet for route (bedre kompatibilitet med Garmin/Wahoo)
    gpx_track = gpxpy.gpx.GPXTrack()
    gpx_track.name = name
    gpx_track.description = description
    
    # Opret track segment
    gpx_segment = gpxpy.gpx.GPXTrackSegment()
    
    # Tilføj track points (dette er det format Garmin/Wahoo forventer)
    for lat, lon in coordinates:
        track_point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon)
        track_point.time = datetime.now()  # Tilføj timestamp
        gpx_segment.points.append(track_point)
    
    gpx_track.segments.append(gpx_segment)
    gpx.tracks.append(gpx_track)
    
    # Opret også route for kompatibilitet (nogle enheder foretrækker dette)
    gpx_route = gpxpy.gpx.GPXRoute(name=name)
    gpx_route.description = description
    
    # Tilføj route points (sparsomt - kun hver 10. koordinat for at holde filen lille)
    for i, (lat, lon) in enumerate(coordinates):
        if i % 10 == 0 or i == len(coordinates) - 1:  # Første, hver 10., og sidste
            gpx_route.points.append(
                gpxpy.gpx.GPXRoutePoint(latitude=lat, longitude=lon)
            )
    
    gpx.routes.append(gpx_route)
    
    # Tilføj metadata
    gpx.name = name
    gpx.description = description
    gpx.time = datetime.now()
    
    # Tilføj creator info (nogle enheder kræver dette)
    gpx.creator = "Aarhus Best Cycling Routes"
    
    return gpx


def save_gpx(
    gpx: gpxpy.gpx.GPX,
    filepath: str,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Gemmer en GPX fil til disk.
    
    Args:
        gpx: GPX objekt
        filepath: Sti til output fil
        logger: Optional logger
        
    Returns:
        True hvis succesfuldt, False ellers
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(gpx.to_xml())
        logger.info(f"GPX fil gemt: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Fejl ved gemning af GPX fil: {e}")
        return False


def create_gpx_from_route_data(
    route_data: dict,
    name: str = "Cykelrute",
    description: str = "",
    logger: Optional[logging.Logger] = None
) -> gpxpy.gpx.GPX:
    """
    Opretter en GPX fil fra rute data (fra routing API).
    
    Args:
        route_data: Rute data dict med 'coordinates' key
        name: Rute navn
        description: Rute beskrivelse
        logger: Optional logger
        
    Returns:
        GPX objekt
    """
    coordinates = route_data.get("coordinates", [])
    
    # Tilføj distance og duration til beskrivelse hvis tilgængelig
    if "distance" in route_data:
        description += f"\nDistance: {route_data['distance']:.2f} km"
    if "duration" in route_data:
        description += f"\nVarighed: {route_data['duration']:.1f} minutter"
    
    return create_gpx_from_coordinates(
        coordinates,
        name=name,
        description=description,
        logger=logger
    )


