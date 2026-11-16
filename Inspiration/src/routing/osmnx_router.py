"""
OSMnx baseret routing med elevation data.
Bruger OpenStreetMap data lokalt for bedre performance og småveje.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
try:
    import osmnx as ox
    import networkx as nx
    from geopy.distance import geodesic
    import numpy as np
    OSMNX_AVAILABLE = True
    # OSMnx konfiguration
    ox.settings.use_cache = True
    ox.settings.log_console = False
except ImportError:
    OSMNX_AVAILABLE = False


def get_route_with_elevation_osmnx(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    network_type: str = "bike",
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Finder en cykelrute med OSMnx og beregner elevation/gradient.
    
    Args:
        start_lat: Start latitude
        start_lon: Start longitude
        end_lat: Slut latitude
        end_lon: Slut longitude
        network_type: Network type (bike, drive, walk, all)
        logger: Optional logger
        
    Returns:
        Rute dict med elevation data eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    if not OSMNX_AVAILABLE:
        logger.error("OSMnx ikke installeret. Installér med: pip install osmnx networkx geopy numpy")
        return None
    
    try:
        # Hent road network for et mindre område omkring ruten
        # Dette er meget hurtigere end at hente hele Aarhus
        
        # Beregn center point mellem start og slut
        center_lat = (start_lat + end_lat) / 2
        center_lon = (start_lon + end_lon) / 2
        
        # Beregn distance mellem start og slut
        distance_km = geodesic((start_lat, start_lon), (end_lat, end_lon)).kilometers
        
        # Brug distance + buffer (max 3 km radius for at holde det hurtigt)
        radius_km = min(distance_km * 1.5 + 1, 3)  # 1.5x distance + 1km buffer, max 3km
        
        logger.info(f"Henter OpenStreetMap netværk for område omkring ruten (radius: {radius_km:.1f} km)...")
        G = ox.graph_from_point(
            center_point=(center_lat, center_lon),
            dist=radius_km * 1000,  # Konverter til meter
            network_type=network_type,
            simplify=True
        )
        
        logger.info(f"Netværk hentet: {len(G.nodes)} noder, {len(G.edges)} kanter")
        
        # Find nærmeste noder til start og slut
        start_node = ox.distance.nearest_nodes(G, start_lon, start_lat)
        end_node = ox.distance.nearest_nodes(G, end_lon, end_lat)
        
        logger.info(f"Start node: {start_node}, End node: {end_node}")
        
        # Find korteste rute
        route = nx.shortest_path(G, start_node, end_node, weight='length')
        
        # Hent koordinater for ruten
        route_coords = [(G.nodes[node]['y'], G.nodes[node]['x']) for node in route]
        
        # Beregn distance
        total_distance = 0
        for i in range(len(route) - 1):
            node1 = route[i]
            node2 = route[i + 1]
            if G.has_edge(node1, node2):
                edge_data = G[node1][node2]
                total_distance += edge_data.get('length', 0)
        
        distance_km = total_distance / 1000
        
        # Estimer varighed (gennemsnitlig cykelhastighed: 15 km/h)
        duration_min = (distance_km / 15) * 60
        
        # Hent elevation data for ruten
        elevation_data = _get_elevation_for_route(route_coords, logger)
        
        # Beregn gradient
        gradient_data = _calculate_gradient(elevation_data, logger)
        
        return {
            "distance": distance_km,
            "duration": duration_min,
            "coordinates": route_coords,
            "elevation": elevation_data,
            "elevation_gain": gradient_data.get('total_gain', 0),
            "elevation_loss": gradient_data.get('total_loss', 0),
            "max_gradient": gradient_data.get('max_gradient', 0),
            "avg_gradient": gradient_data.get('avg_gradient', 0)
        }
        
    except Exception as e:
        logger.error(f"Fejl ved OSMnx routing: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


def _get_elevation_for_route(
    coordinates: List[Tuple[float, float]],
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Henter elevation data for koordinater.
    Bruger OpenElevation API (gratis).
    
    Args:
        coordinates: Liste af (lat, lon) tuples
        logger: Optional logger
        
    Returns:
        Liste af elevation data dicts
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    try:
        import requests
        
        # OpenElevation API (gratis, ingen API key)
        url = "https://api.open-elevation.com/api/v1/lookup"
        
        # Format: {"locations": [{"latitude": lat, "longitude": lon}, ...]}
        locations = [{"latitude": lat, "longitude": lon} for lat, lon in coordinates]
        
        # Batch request (max 100 locations per request)
        elevation_data = []
        batch_size = 100
        
        for i in range(0, len(locations), batch_size):
            batch = locations[i:i + batch_size]
            payload = {"locations": batch}
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                results = response.json().get('results', [])
                elevation_data.extend(results)
            else:
                logger.warning(f"OpenElevation API fejl: {response.status_code}")
                # Fallback: sæt elevation til 0
                elevation_data.extend([{"elevation": 0} for _ in batch])
        
        # Kombiner med koordinater
        result = []
        for i, (lat, lon) in enumerate(coordinates):
            elev = elevation_data[i].get('elevation', 0) if i < len(elevation_data) else 0
            result.append({
                'lat': lat,
                'lon': lon,
                'elevation': elev
            })
        
        return result
        
    except Exception as e:
        logger.warning(f"Kunne ikke hente elevation data: {e}")
        # Returner med elevation = 0
        return [{'lat': lat, 'lon': lon, 'elevation': 0} for lat, lon in coordinates]


def _calculate_gradient(
    elevation_data: List[Dict[str, Any]],
    logger: Optional[logging.Logger] = None
) -> Dict[str, float]:
    """
    Beregner gradient baseret på elevation data.
    
    Args:
        elevation_data: Liste af elevation data dicts
        logger: Optional logger
        
    Returns:
        Dict med gradient statistikker
    """
    if len(elevation_data) < 2:
        return {
            'total_gain': 0,
            'total_loss': 0,
            'max_gradient': 0,
            'avg_gradient': 0
        }
    
    elevations = [e.get('elevation', 0) for e in elevation_data]
    gradients = []
    total_gain = 0
    total_loss = 0
    
    for i in range(len(elevation_data) - 1):
        elev1 = elevations[i]
        elev2 = elevations[i + 1]
        elev_diff = elev2 - elev1
        
        # Beregn distance mellem punkter
        coord1 = (elevation_data[i]['lat'], elevation_data[i]['lon'])
        coord2 = (elevation_data[i + 1]['lat'], elevation_data[i + 1]['lon'])
        distance_m = geodesic(coord1, coord2).meters
        
        if distance_m > 0:
            # Gradient i procent: (elevation_diff / distance) * 100
            gradient = (elev_diff / distance_m) * 100
            gradients.append(gradient)
            
            if elev_diff > 0:
                total_gain += elev_diff
            else:
                total_loss += abs(elev_diff)
    
    if not OSMNX_AVAILABLE or not gradients:
        return {
            'total_gain': total_gain,
            'total_loss': total_loss,
            'max_gradient': 0,
            'avg_gradient': 0
        }
    
    return {
        'total_gain': total_gain,
        'total_loss': total_loss,
        'max_gradient': max(gradients),
        'avg_gradient': np.mean(gradients)
    }
