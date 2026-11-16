"""
Kortvisualisering med Folium.
Genererer interaktive HTML kort med ruter.
Understøtter også statiske kortbilleder via Static Map API.
"""

import folium
from typing import List, Tuple, Optional, Dict, Any
import logging
from ..connectors.static_map import generate_static_map, save_static_map


def create_route_map(
    coordinates: List[Tuple[float, float]],
    start_name: str = "Start",
    end_name: str = "Slut",
    route_name: str = "Cykelrute",
    center: Optional[Tuple[float, float]] = None,
    zoom_start: int = 13,
    logger: Optional[logging.Logger] = None
) -> folium.Map:
    """
    Opretter et interaktivt kort med en rute.
    
    Args:
        coordinates: Liste af (lat, lon) tuples
        start_name: Navn på startpunkt
        end_name: Navn på slutpunkt
        route_name: Navn på ruten
        center: Center koordinater (hvis None, beregnes fra koordinater)
        zoom_start: Start zoom niveau
        logger: Optional logger
        
    Returns:
        Folium Map objekt
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if not coordinates:
        logger.error("Ingen koordinater givet")
        return None
    
    # Beregn center hvis ikke givet
    if center is None:
        lats = [coord[0] for coord in coordinates]
        lons = [coord[1] for coord in coordinates]
        center = (sum(lats) / len(lats), sum(lons) / len(lons))
    
    # Opret kort
    m = folium.Map(
        location=center,
        zoom_start=zoom_start,
        tiles='OpenStreetMap'
    )
    
    # Beregn bounds for bedre zoom (som RideWithGPS - ingen stor firkant)
    if len(coordinates) > 1:
        lats = [c[0] for c in coordinates]
        lons = [c[1] for c in coordinates]
        bounds = [[min(lats), min(lons)], [max(lats), max(lons)]]
        # Fit bounds med minimal padding (ingen stor firkant)
        m.fit_bounds(bounds, padding=(20, 20))  # Minimal padding
    
    # Tilføj rute linje (rød som RideWithGPS)
    folium.PolyLine(
        coordinates,
        color='red',  # Rød som RideWithGPS
        weight=4,
        opacity=0.8,
        popup=route_name,
        tooltip=route_name
    ).add_to(m)
    
    # Tilføj start marker
    if coordinates:
        folium.Marker(
            coordinates[0],
            popup=start_name,
            tooltip=start_name,
            icon=folium.Icon(color='green', icon='play', prefix='fa')
        ).add_to(m)
    
    # Tilføj slut marker
    if len(coordinates) > 1:
        folium.Marker(
            coordinates[-1],
            popup=end_name,
            tooltip=end_name,
            icon=folium.Icon(color='red', icon='stop', prefix='fa')
        ).add_to(m)
    
    return m


def save_map(
    map_obj: folium.Map,
    filepath: str,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Gemmer et kort til HTML fil.
    
    Args:
        map_obj: Folium Map objekt
        filepath: Sti til output fil
        logger: Optional logger
        
    Returns:
        True hvis succesfuldt, False ellers
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        map_obj.save(filepath)
        logger.info(f"Kort gemt: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Fejl ved gemning af kort: {e}")
        return False


def create_map_with_route_data(
    route_data: Dict[str, Any],
    start_name: str = "Start",
    end_name: str = "Slut",
    route_name: str = "Cykelrute",
    logger: Optional[logging.Logger] = None
) -> folium.Map:
    """
    Opretter et kort fra rute data (fra routing API).
    
    Args:
        route_data: Rute data dict med 'coordinates' key
        start_name: Navn på startpunkt
        end_name: Navn på slutpunkt
        route_name: Navn på ruten
        logger: Optional logger
        
    Returns:
        Folium Map objekt
    """
    coordinates = route_data.get("coordinates", [])
    
    # Tilføj distance og duration til rute navn hvis tilgængelig
    if "distance" in route_data:
        route_name += f" ({route_data['distance']:.2f} km)"
    if "duration" in route_data:
        route_name += f" - {route_data['duration']:.1f} min"
    
    return create_route_map(
        coordinates,
        start_name=start_name,
        end_name=end_name,
        route_name=route_name,
        logger=logger
    )


def create_static_map_image(
    route_data: Dict[str, Any],
    api_key: Optional[str] = None,
    provider: str = "mapbox",
    start_name: str = "Start",
    end_name: str = "Slut",
    route_name: str = "Cykelrute",
    width: int = 800,
    height: int = 600,
    style: str = "mapbox/streets-v12",
    logger: Optional[logging.Logger] = None
) -> Optional[bytes]:
    """
    Opretter et statisk kortbillede fra rute data.
    
    Args:
        route_data: Rute data dict med 'coordinates' key
        api_key: API key for static map provider
        provider: Provider navn ("mapbox", "osm")
        start_name: Navn på startpunkt
        end_name: Navn på slutpunkt
        route_name: Navn på ruten
        width: Billedbredde i pixels
        height: Billedhøjde i pixels
        style: Style navn (for Mapbox)
        logger: Optional logger
        
    Returns:
        Bytes af billedet (PNG format), eller None hvis fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    coordinates = route_data.get("coordinates", [])
    
    if not coordinates:
        logger.error("Ingen koordinater i rute data")
        return None
    
    # Opret markere for start og slut
    markers = []
    if coordinates:
        markers.append({
            'lat': coordinates[0][0],
            'lon': coordinates[0][1],
            'color': 'green',
            'label': 'S'  # Start
        })
    
    if len(coordinates) > 1:
        markers.append({
            'lat': coordinates[-1][0],
            'lon': coordinates[-1][1],
            'color': 'red',
            'label': 'E'  # End
        })
    
    # Generer statisk kort
    image_bytes = generate_static_map(
        api_key=api_key,
        provider=provider,
        coordinates=coordinates,
        width=width,
        height=height,
        markers=markers,
        polyline=coordinates,
        style=style,
        logger=logger
    )
    
    return image_bytes


def save_static_map_image(
    image_bytes: bytes,
    filepath: str,
    logger: Optional[logging.Logger] = None
) -> bool:
    """
    Gemmer et statisk kortbillede til fil.
    
    Args:
        image_bytes: Bytes af billedet
        filepath: Sti til output fil
        logger: Optional logger
        
    Returns:
        True hvis succesfuldt, False ellers
    """
    return save_static_map(image_bytes, filepath, logger)


