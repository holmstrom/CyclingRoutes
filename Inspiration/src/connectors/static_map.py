"""
Static Map API connector for at generere statiske kortbilleder.
Understøtter flere providers: OpenStreetMap Static Maps, Mapbox Static Images.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from urllib.parse import urlencode
import base64
from ..utils.http import HTTPClient


def generate_static_map_osm(
    coordinates: List[Tuple[float, float]],
    width: int = 800,
    height: int = 600,
    zoom: Optional[int] = None,
    markers: Optional[List[Dict[str, Any]]] = None,
    polyline: Optional[List[Tuple[float, float]]] = None,
    logger: Optional[logging.Logger] = None
) -> Optional[bytes]:
    """
    Genererer et statisk kortbillede via OpenStreetMap Static Maps API.
    
    Args:
        coordinates: Liste af (lat, lon) tuples for ruten
        width: Billedbredde i pixels (default: 800)
        height: Billedhøjde i pixels (default: 600)
        zoom: Zoom niveau (hvis None, beregnes automatisk)
        markers: Liste af markere med {'lat': float, 'lon': float, 'color': str, 'label': str}
        polyline: Koordinater for rute linje (hvis None, bruges coordinates)
        logger: Optional logger
        
    Returns:
        Bytes af billedet (PNG format), eller None hvis fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if not coordinates:
        logger.error("Ingen koordinater givet")
        return None
    
    client = HTTPClient(logger=logger)
    
    # Beregn center og bounds
    lats = [coord[0] for coord in coordinates]
    lons = [coord[1] for coord in coordinates]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Beregn zoom hvis ikke givet
    if zoom is None:
        # Simpel zoom beregning baseret på koordinat spredning
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        max_range = max(lat_range, lon_range)
        
        if max_range > 0.1:
            zoom = 10
        elif max_range > 0.05:
            zoom = 12
        elif max_range > 0.01:
            zoom = 13
        else:
            zoom = 14
    
    # Brug StaticMap API (gratis, open-source)
    # Der er flere gratis Static Map services - vi bruger en simpel tilgang
    # med OpenStreetMap tiles via en static map service
    
    # Alternativ: Brug MapTiler eller lignende gratis service
    # For nu, bruger vi en simpel tilgang med OpenStreetMap
    
    # Build URL for static map
    # Note: OpenStreetMap har ikke en officiel static map API
    # Vi kan bruge en tredjepart service eller generere via tiles
    
    # Brug StaticMap.com eller lignende gratis service
    # Eller brug Mapbox Static Images API (kræver API key)
    
    logger.warning("OpenStreetMap Static Maps kræver tredjepart service eller Mapbox API key")
    logger.info("Bruger Mapbox Static Images API (kræver API key i config)")
    
    return None


def generate_static_map_mapbox(
    api_key: str,
    coordinates: List[Tuple[float, float]],
    width: int = 800,
    height: int = 600,
    zoom: Optional[int] = None,
    markers: Optional[List[Dict[str, Any]]] = None,
    polyline: Optional[List[Tuple[float, float]]] = None,
    style: str = "mapbox/streets-v12",
    logger: Optional[logging.Logger] = None
) -> Optional[bytes]:
    """
    Genererer et statisk kortbillede via Mapbox Static Images API.
    
    Args:
        api_key: Mapbox API key
        coordinates: Liste af (lat, lon) tuples for ruten
        width: Billedbredde i pixels (default: 800, max: 1280)
        height: Billedhøjde i pixels (default: 600, max: 1280)
        zoom: Zoom niveau (hvis None, beregnes automatisk)
        markers: Liste af markere med {'lat': float, 'lon': float, 'color': str, 'label': str}
        polyline: Koordinater for rute linje (hvis None, bruges coordinates)
        style: Mapbox style (default: "mapbox/streets-v12")
        logger: Optional logger
        
    Returns:
        Bytes af billedet (PNG format), eller None hvis fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if not api_key:
        logger.error("Mapbox API key mangler")
        return None
    
    if not coordinates:
        logger.error("Ingen koordinater givet")
        return None
    
    client = HTTPClient(logger=logger)
    
    # Beregn center
    lats = [coord[0] for coord in coordinates]
    lons = [coord[1] for coord in coordinates]
    center_lat = sum(lats) / len(lats)
    center_lon = sum(lons) / len(lons)
    
    # Beregn zoom hvis ikke givet
    if zoom is None:
        lat_range = max(lats) - min(lats)
        lon_range = max(lons) - min(lons)
        max_range = max(lat_range, lon_range)
        
        if max_range > 0.1:
            zoom = 10
        elif max_range > 0.05:
            zoom = 12
        elif max_range > 0.01:
            zoom = 13
        else:
            zoom = 14
    
    # Build Mapbox Static Images API URL
    # Mapbox Static Images API format:
    # https://api.mapbox.com/styles/v1/{username}/{style_id}/static/{overlay}/{lon},{lat},{zoom}/{width}x{height}?access_token={token}
    
    # Konstruer style path
    # Hvis style starter med "mapbox/", brug det direkte
    # Ellers tilføj "mapbox/" prefix
    if style.startswith("mapbox/"):
        style_path = style
    else:
        style_path = f"mapbox/{style}"
    
    # Build overlay string
    overlays = []
    
    # Tilføj rute linje (polyline)
    route_coords = polyline if polyline else coordinates
    if route_coords:
        # Konverter koordinater til polyline format: lon,lat;lon,lat;...
        # Mapbox path format: path-{stroke-width}+{stroke-color}-{opacity}({coordinates})
        polyline_str = ";".join([f"{lon},{lat}" for lat, lon in route_coords])
        overlays.append(f"path-5+0066ff-0.8({polyline_str})")
    
    # Tilføj markere
    if markers:
        for i, marker in enumerate(markers):
            lat = marker.get('lat')
            lon = marker.get('lon')
            color = marker.get('color', 'green')
            label = marker.get('label', str(i + 1))
            
            if lat is not None and lon is not None:
                # Mapbox marker format: pin-s-{size}+{color}({lon},{lat})
                # Eller: pin-s-{label}+{color}({lon},{lat})
                # Farve mapping: green -> 00ff00, red -> ff0000
                color_map = {
                    'green': '00ff00',
                    'red': 'ff0000',
                    'blue': '0066ff',
                    'orange': 'ff8800'
                }
                color_hex = color_map.get(color.lower(), '0066ff')
                overlays.append(f"pin-s-{label}+{color_hex}({lon},{lat})")
    
    # Build URL
    overlay_str = "|".join(overlays) if overlays else ""
    
    base_url = "https://api.mapbox.com/styles/v1"
    
    if overlay_str:
        path = f"/{style_path}/static/{overlay_str}/{center_lon},{center_lat},{zoom}/{width}x{height}"
    else:
        path = f"/{style_path}/static/{center_lon},{center_lat},{zoom}/{width}x{height}"
    
    url = f"{base_url}{path}"
    params = {
        "access_token": api_key
    }
    
    try:
        logger.info(f"Henter statisk kort fra Mapbox: {center_lat:.4f}, {center_lon:.4f}, zoom={zoom}")
        response = client.get(url, params=params)
        
        if response.status_code == 200:
            logger.info(f"Statisk kort hentet succesfuldt ({len(response.content)} bytes)")
            return response.content
        else:
            logger.error(f"Fejl ved hentning af statisk kort: HTTP {response.status_code}")
            logger.debug(f"Response: {response.text[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"Exception ved hentning af statisk kort: {e}")
        return None


def generate_static_map(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    provider: str = "mapbox",
    coordinates: List[Tuple[float, float]] = None,
    width: int = 800,
    height: int = 600,
    zoom: Optional[int] = None,
    markers: Optional[List[Dict[str, Any]]] = None,
    polyline: Optional[List[Tuple[float, float]]] = None,
    style: str = "mapbox/streets-v12",
    logger: Optional[logging.Logger] = None
) -> Optional[bytes]:
    """
    Genererer et statisk kortbillede via forskellige providers.
    
    Args:
        base_url: Base URL for API (hvis nødvendig)
        api_key: API key (hvis nødvendig for provider)
        provider: Provider navn ("mapbox", "osm")
        coordinates: Liste af (lat, lon) tuples for ruten
        width: Billedbredde i pixels
        height: Billedhøjde i pixels
        zoom: Zoom niveau
        markers: Liste af markere
        polyline: Koordinater for rute linje
        style: Style navn (for Mapbox)
        logger: Optional logger
        
    Returns:
        Bytes af billedet (PNG format), eller None hvis fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if provider.lower() == "mapbox":
        if not api_key:
            logger.error("Mapbox kræver API key")
            return None
        return generate_static_map_mapbox(
            api_key=api_key,
            coordinates=coordinates,
            width=width,
            height=height,
            zoom=zoom,
            markers=markers,
            polyline=polyline,
            style=style,
            logger=logger
        )
    elif provider.lower() == "osm":
        return generate_static_map_osm(
            coordinates=coordinates,
            width=width,
            height=height,
            zoom=zoom,
            markers=markers,
            polyline=polyline,
            logger=logger
        )
    else:
        logger.error(f"Ukendt provider: {provider}")
        return None


def save_static_map(
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
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
        logger.info(f"Statisk kort gemt: {filepath}")
        return True
    except Exception as e:
        logger.error(f"Fejl ved gemning af statisk kort: {e}")
        return False

