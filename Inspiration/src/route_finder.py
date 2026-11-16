"""
Hovedmodul til at finde bedste cykelruter.
Kombinerer routing og geodata.
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime

from .connectors.dawa import get_address_coordinates
from .routing.osrm import get_route_osrm, get_route_with_waypoints_osrm
from .routing.osmnx_router import get_route_with_elevation_osmnx
from .routing.graphhopper import get_route_graphhopper, get_route_with_waypoints_graphhopper
from .routing.ors import get_route_with_waypoints_ors
from .gpx.generator import create_gpx_from_route_data, save_gpx
from .visualization.map import (
    create_map_with_route_data, 
    save_map,
    create_static_map_image,
    save_static_map_image
)
from .utils.config import load_config
from .utils.logging import get_logger, ensure_dirs
from .utils.route_helpers import (
    generate_loop_waypoints,
    filter_route_by_distance,
    filter_route_by_elevation,
    is_in_direction
)
from .utils.route_cache import RouteCache
from .utils.route_optimizer import generate_smart_waypoints, evaluate_route_quality
from .utils.route_validator import check_route_overlap, validate_route_structure
from concurrent.futures import ThreadPoolExecutor, as_completed
import os


class RouteFinder:
    """
    Hovedklasse til at finde bedste cykelruter.
    """
    
    def __init__(
        self,
        config_path: str = "config.yaml",
        env_file: str = ".env",
        environment: str = "dev"
    ):
        """
        Args:
            config_path: Sti til config.yaml
            env_file: Sti til .env fil
            environment: Environment navn
        """
        self.config = load_config(config_path, env_file, environment)
        self.logger = get_logger(
            log_dir=self.config.get("output", {}).get("logs_dir", "logs"),
            log_level=self.config.get("_env", {}).get("LOG_LEVEL", "INFO")
        )
        
        # Opret output mapper
        routes_dir = self.config.get("output", {}).get("routes_dir", "output/routes")
        maps_dir = self.config.get("output", {}).get("maps_dir", "output/maps")
        static_maps_dir = self.config.get("output", {}).get("static_maps_dir", "output/maps/static")
        ensure_dirs(routes_dir, maps_dir, static_maps_dir)
        
        # Initialiser route cache for at lære fra gode ruter
        cache_dir = self.config.get("output", {}).get("cache_dir", "cache/routes")
        self.route_cache = RouteCache(cache_dir=cache_dir, logger=self.logger)
    
    def find_route(
        self,
        start_address: str,
        end_address: str,
        route_name: Optional[str] = None,
        alternatives: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Finder en cykelrute mellem to adresser.
        
        Args:
            start_address: Start adresse
            end_address: Slut adresse
            route_name: Navn på ruten (hvis None, genereres automatisk)
            alternatives: Antal alternative ruter (0-3)
            
        Returns:
            Dict med rute data, eller None ved fejl
        """
        self.logger.info(f"Finder rute: {start_address} -> {end_address}")
        
        # Hent koordinater
        dawa_base = self.config.get("dawa", {}).get("base_url")
        start_coords = get_address_coordinates(dawa_base, start_address, self.logger)
        end_coords = get_address_coordinates(dawa_base, end_address, self.logger)
        
        if not start_coords or not end_coords:
            self.logger.error("Kunne ikke finde koordinater for adresser")
            return None
        
        self.logger.info(
            f"Koordinater: Start ({start_coords['lat']}, {start_coords['lon']}) -> "
            f"Slut ({end_coords['lat']}, {end_coords['lon']})"
        )
        
        # Hent rute
        routing_config = self.config.get("routing", {}).get("osrm", {})
        if not routing_config.get("enabled"):
            self.logger.error("OSRM routing ikke aktiveret")
            return None
        
        base_url = routing_config.get("base_url")
        profile = routing_config.get("profile", "cycling")
        
        route_data = get_route_osrm(
            base_url,
            start_coords['lat'],
            start_coords['lon'],
            end_coords['lat'],
            end_coords['lon'],
            profile=profile,
            alternatives=alternatives,
            logger=self.logger
        )
        
        if not route_data:
            self.logger.error("Kunne ikke finde rute")
            return None
        
        # Tilføj metadata
        route_data['start_address'] = start_address
        route_data['end_address'] = end_address
        route_data['start_coords'] = start_coords
        route_data['end_coords'] = end_coords
        route_data['route_name'] = route_name or f"{start_address} -> {end_address}"
        
        self.logger.info(
            f"Rute fundet: {route_data['distance']:.2f} km, "
            f"{route_data['duration']:.1f} minutter"
        )
        
        return route_data
    
    def find_multiple_routes(
        self,
        start_address: str,
        end_address: str,
        max_routes: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Finder flere alternative ruter mellem to adresser.
        
        Args:
            start_address: Start adresse
            end_address: Slut adresse
            max_routes: Maksimalt antal ruter at finde
            
        Returns:
            Liste af rute data dicts
        """
        routes = []
        
        # Find hovedrute
        main_route = self.find_route(start_address, end_address, alternatives=max_routes-1)
        if main_route:
            routes.append(main_route)
        
        # OSRM kan returnere alternativer i samme kald, men vi implementerer det simpelt her
        # For flere ruter kan vi bruge waypoints eller forskellige routing strategier
        
        return routes
    
    def find_routes_from_start(
        self,
        start_address: str,
        num_routes: int = 5,
        min_distance_km: Optional[float] = None,
        max_distance_km: Optional[float] = None,
        min_elevation_gain_m: Optional[float] = None,
        max_elevation_gain_m: Optional[float] = None,
        direction: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Finder flere loop ruter fra en startadresse.
        Ruterne starter og slutter på samme sted (loop ruter).
        
        Args:
            start_address: Start adresse (og slut adresse for loop ruter)
            num_routes: Antal ruter at finde
            min_distance_km: Minimum distance per rute (None = ingen minimum)
            max_distance_km: Maksimal distance per rute (None = ingen maksimum)
            min_elevation_gain_m: Minimum højdemeter (None = ingen minimum)
            max_elevation_gain_m: Maksimum højdemeter (None = ingen maksimum)
            direction: Retning for rute område (nord, syd, vest, øst, nordøst, sydøst, sydvest, nordvest, eller None for alle)
            
        Returns:
            Liste af rute data dicts
        """
        self.logger.info(f"Finder {num_routes} loop ruter fra: {start_address}")
        if direction:
            self.logger.info(f"Retning: {direction}")
        
        # Hent start koordinater
        dawa_base = self.config.get("dawa", {}).get("base_url")
        start_coords = get_address_coordinates(dawa_base, start_address, self.logger)
        
        if not start_coords:
            self.logger.error(f"Kunne ikke finde koordinater for start adresse: {start_address}")
            return []
        
        self.logger.info(f"Start koordinater: ({start_coords['lat']}, {start_coords['lon']})")
        
        # Beregn target distance for destinationer
        # For loop ruter: start -> destination -> start
        # Total distance = 2 * distance til destination
        # Så hvis vi vil have en loop på X km, skal destinationen være X/2 km væk
        
        # Beregn target distance baseret på minimum og maksimum
        if min_distance_km:
            # Hvis minimum er sat, brug den som basis (med lidt buffer)
            target_loop_distance = min_distance_km * 1.1  # 10% buffer over minimum
            if max_distance_km:
                target_loop_distance = min(target_loop_distance, max_distance_km)
        elif max_distance_km:
            target_loop_distance = max_distance_km * 0.8  # 80% af maksimum
        else:
            target_loop_distance = 30.0  # Default 30 km
        
        # Distance til destination (halvdelen af loop distance)
        destination_distance = target_loop_distance / 2
        
        self.logger.info(f"Target loop distance: {target_loop_distance:.2f} km")
        self.logger.info(f"Target destination distance: {destination_distance:.2f} km")
        
        # Generer waypoint sets for rigtige loop ruter
        # Brug smart waypoint generering der lærer fra cache og undgår lige stykker
        waypoint_sets = []
        num_waypoint_sets = num_routes * 3  # Reduceret for bedre performance
        
        # Generer waypoint sets med varierende afstande og antal waypoints
        for i in range(num_waypoint_sets):
            # Varier distance lidt for at få forskellige rute længder
            variation = 0.8 + (i % 5) * 0.1  # 80-120% variation
            current_target_distance = target_loop_distance * variation
            
            # Færre waypoints for simplere loop (max 3 waypoints for GraphHopper gratis tier limit på 5 points total)
            # GraphHopper gratis tier: max 5 points (start + waypoints + slut)
            # Så vi kan have max 3 waypoints (start + 3 waypoints + slut = 5)
            num_waypoints = 3  # Fast til 3 waypoints for GraphHopper kompatibilitet
            
            # Brug smart waypoint generering - lær fra eksisterende GPX ruter
            # Tjek både output/routes (nye ruter) og docs/gpx routes (eksisterende ruter)
            gpx_routes_dirs = [
                self.config.get("output", {}).get("routes_dir", "output/routes"),
                self.config.get("output", {}).get("gpx_routes_dir", "docs/gpx routes")
            ]
            # Vælg første mappe der findes OG har mindst én .gpx, ellers fallback til docs/gpx routes
            from pathlib import Path
            gpx_routes_dir = None
            for dir_path in gpx_routes_dirs:
                p = Path(dir_path)
                if p.exists():
                    if any(p.rglob("*.gpx")):
                        gpx_routes_dir = dir_path
                        break
            if not gpx_routes_dir:
                # Fallback til docs/gpx routes hvis den findes
                if Path("docs/gpx routes").exists():
                    gpx_routes_dir = "docs/gpx routes"
                else:
                    gpx_routes_dir = None
            waypoints = generate_smart_waypoints(
                start_coords['lat'],
                start_coords['lon'],
                target_distance_km=current_target_distance,
                direction=direction,
                num_waypoints=num_waypoints,
                route_cache=self.route_cache,
                gpx_routes_dir=gpx_routes_dir,
                logger=self.logger
            )
            if waypoints:
                # Tilføj start/slut som første og sidste waypoint for rigtig loop
                loop_waypoints = [(start_coords['lat'], start_coords['lon'])] + waypoints + [(start_coords['lat'], start_coords['lon'])]
                waypoint_sets.append(loop_waypoints)
        
        self.logger.info(f"Genereret {len(waypoint_sets)} waypoint sets for loop ruter")
        
        # Hent routing config - prøv GraphHopper først (bedre), derefter OSRM, derefter OSMnx
        ors_config = self.config.get("routing", {}).get("ors", {})
        graphhopper_config = self.config.get("routing", {}).get("graphhopper", {})
        osmnx_config = self.config.get("routing", {}).get("osmnx", {})
        osrm_config = self.config.get("routing", {}).get("osrm", {})
        
        use_ors = ors_config.get("enabled", False)
        use_graphhopper = graphhopper_config.get("enabled", False)
        use_osmnx = osmnx_config.get("enabled", False)
        use_osrm = osrm_config.get("enabled", True)
        
        if not use_ors and not use_graphhopper and not use_osmnx and not use_osrm:
            self.logger.error("Ingen routing metode aktiveret")
            return []
        
        # ORS config
        ors_base = ors_config.get("base_url") if use_ors else None
        ors_profile = ors_config.get("profile", "cycling-regular") if use_ors else None
        ors_key = os.getenv("ORS_API_KEY") if use_ors else None
        if use_ors and not ors_key:
            self.logger.warning("ORS er enabled, men ORS_API_KEY mangler. Skipper ORS.")
            use_ors = False

        # GraphHopper config
        graphhopper_base = graphhopper_config.get("base_url") if use_graphhopper else None
        graphhopper_key = os.getenv("GRAPHHOPPER_API_KEY") if use_graphhopper else None
        
        # OSRM config
        base_url = osrm_config.get("base_url") if use_osrm else None
        profile = osrm_config.get("profile", "cycling") if use_osrm else None
        
        # OSMnx config
        network_type = osmnx_config.get("network_type", "bike") if use_osmnx else None
        
        routes = []
        
        # Funktion til at finde enkelt loop rute med waypoints (rigtig loop)
        def find_single_loop_route(waypoint_list):
            try:
                self.logger.debug(f"Prøver at finde loop rute med {len(waypoint_list)} waypoints")
                
                # Find rute med waypoints - prioritér ORS (gratis tier, waypoint support)
                route_data = None
                if use_ors and ors_base and ors_key:
                    try:
                        self.logger.debug(f"Bruger ORS for waypoint rute (gratis tier)")
                        route_data = get_route_with_waypoints_ors(
                            ors_base,
                            ors_key,
                            waypoint_list,
                            profile=ors_profile or "cycling-regular",
                            elevation=True,
                            logger=self.logger
                        )
                        if route_data:
                            self.logger.debug(f"ORS fandt waypoint rute: {route_data.get('distance', 0):.2f} km")
                    except Exception as e:
                        self.logger.warning(f"ORS fejlede for waypoint rute: {e}")

                # Fallback: GraphHopper hvis aktiveret
                if not route_data and use_graphhopper and graphhopper_base and graphhopper_key:
                    try:
                        self.logger.debug(f"Bruger GraphHopper for waypoint rute (fallback små veje)")
                        route_data = get_route_with_waypoints_graphhopper(
                            graphhopper_base,
                            graphhopper_key,
                            waypoint_list,
                            vehicle="bike",
                            elevation=True,
                            logger=self.logger
                        )
                        if route_data:
                            self.logger.debug(f"GraphHopper fandt waypoint rute: {route_data.get('distance', 0):.2f} km")
                    except Exception as e:
                        self.logger.warning(f"GraphHopper fejlede for waypoint rute: {e}")
                
                # Fallback til OSRM hvis GraphHopper ikke virker
                if not route_data and use_osrm and base_url:
                    try:
                        self.logger.debug(f"Bruger OSRM for waypoint rute (fallback)")
                        route_data = get_route_with_waypoints_osrm(
                            base_url,
                            waypoint_list,
                            profile=profile,
                            logger=self.logger
                        )
                        if route_data:
                            self.logger.debug(f"OSRM fandt waypoint rute: {route_data.get('distance', 0):.2f} km")
                    except Exception as e:
                        self.logger.warning(f"OSRM fejlede for waypoint rute: {e}")
                
                if not route_data:
                    self.logger.debug("Ingen waypoint rute fundet")
                    return None
                
                # Rute data er allerede en komplet loop
                combined_coords = route_data.get('coordinates', [])
                
                # Elevation data er allerede i route_data hvis GraphHopper blev brugt
                # Hvis ikke, prøv at hente det
                if not route_data.get('elevation') and combined_coords:
                    try:
                        import requests
                        url = "https://api.open-elevation.com/api/v1/lookup"
                        locations = [{"latitude": lat, "longitude": lon} for lat, lon in combined_coords]
                        
                        elevation_results = []
                        batch_size = 100
                        for i in range(0, len(locations), batch_size):
                            batch = locations[i:i + batch_size]
                            payload = {"locations": batch}
                            response = requests.post(url, json=payload, timeout=30)
                            if response.status_code == 200:
                                results = response.json().get('results', [])
                                elevation_results.extend(results)
                        
                        if elevation_results:
                            elevation_data = []
                            cum_distance = 0
                            for i, (lat, lon) in enumerate(combined_coords):
                                elev = elevation_results[i].get('elevation', 0) if i < len(elevation_results) else 0
                                if i > 0:
                                    from math import radians, cos, sin, asin, sqrt
                                    lat1, lon1 = combined_coords[i-1]
                                    lat2, lon2 = lat, lon
                                    dlat = radians(lat2 - lat1)
                                    dlon = radians(lon2 - lon1)
                                    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                                    c = 2 * asin(sqrt(a))
                                    cum_distance += c * 6371
                                
                                elevation_data.append({
                                    'lat': lat,
                                    'lon': lon,
                                    'elevation': elev,
                                    'distance': cum_distance
                                })
                            
                            elevations = [e.get('elevation', 0) for e in elevation_data]
                            gain = 0
                            loss = 0
                            for i in range(1, len(elevations)):
                                diff = elevations[i] - elevations[i-1]
                                if diff > 0:
                                    gain += diff
                                else:
                                    loss += abs(diff)
                            route_data["elevation"] = elevation_data
                            route_data["elevation_gain"] = gain
                            route_data["elevation_loss"] = loss
                    except Exception as e:
                        self.logger.debug(f"Kunne ikke hente elevation data: {e}")
                
                # Filtrer på distance
                if not filter_route_by_distance(route_data, min_distance_km, max_distance_km, self.logger):
                    self.logger.debug(f"Loop rute filtreret væk pga. distance: {route_data.get('distance', 0):.2f} km")
                    return None
                
                # Filtrer på elevation (hvis tilgængelig)
                if not filter_route_by_elevation(route_data, min_elevation_gain_m, max_elevation_gain_m, self.logger):
                    self.logger.debug(f"Loop rute filtreret væk pga. elevation")
                    return None
                
                # Filtrer på retning hvis specificeret (tjek første waypoint)
                if direction and route_data.get('coordinates') and len(waypoint_list) > 1:
                    first_waypoint = waypoint_list[1]  # Første waypoint (efter start)
                    if not is_in_direction(start_coords['lat'], start_coords['lon'], first_waypoint[0], first_waypoint[1], direction):
                        self.logger.debug(f"Loop rute filtreret: første waypoint ikke i retning {direction}")
                        return None
                
                # Tjek for overlappende sektioner (max 20% overlap)
                route_coords = route_data.get('coordinates', [])
                if route_coords:
                    overlap_check = check_route_overlap(route_coords, max_overlap_percent=20.0, logger=self.logger)
                    if overlap_check['has_overlap']:
                        self.logger.debug(f"Loop rute filtreret: for meget overlap ({overlap_check['overlap_percent']:.1f}%)")
                        return None
                    # Undgå for store veje via vejnavne, hvis tilgængeligt
                    blocked_names = [
                        "viborgvej",
                        "randersvej",
                        "grenåvej",
                        "grenå vej",
                        "silkeborgvej",
                        "skanderborgvej",
                        "oddervej",
                        "aarhusvej",
                        "åboulevarden",
                        "ringvej",
                        "ring gade",
                        "herningmotorvejen",
                        "e45",
                    ]
                    total_blocked_km = 0.0
                    max_blocked_step_km = 0.0
                    
                    # Tjek steps for vejnavne (ORS og GraphHopper)
                    # GraphHopper kan have navne i step.get("name") ELLER i step.get("text")
                    for step in route_data.get("steps", []):
                        # Prøv først "name" feltet
                        name = (step.get("name") or "").lower()
                        # Hvis tom, prøv at ekstrahere fra "text" feltet (GraphHopper instructions)
                        if not name and step.get("text"):
                            text = (step.get("text") or "").lower()
                            # GraphHopper format: "Continue onto Viborgvej", "Turn left onto Randersvej"
                            if "onto" in text:
                                parts = text.split("onto")
                                if len(parts) > 1:
                                    name = parts[1].strip()
                            elif "on " in text and "continue" not in text:
                                parts = text.split("on ")
                                if len(parts) > 1:
                                    name = parts[1].strip()
                        
                        dist = step.get("distance", 0) / 1000.0  # km
                        if name:  # Kun tjek steps med navne
                            for bn in blocked_names:
                                if bn in name:
                                    total_blocked_km += dist
                                    max_blocked_step_km = max(max_blocked_step_km, dist)
                                    # Afvis hvis et enkelt step er for langt på stor vej
                                    if dist > 0.5:
                                        self.logger.debug(f"Loop rute filtreret: lang sektion på stor vej ({bn}, {dist:.2f} km)")
                                        return None
                                    break
                    
                    # Afvis hvis samlet distance på store veje overstiger 0.5 km
                    if total_blocked_km > 0.5:
                        self.logger.debug(f"Loop rute filtreret: samlet {total_blocked_km:.2f} km på store veje")
                        return None
                    # Afvis hvis et enkelt step er for langt
                    if max_blocked_step_km > 0.5:
                        self.logger.debug(f"Loop rute filtreret: lang sektion på stor vej ({max_blocked_step_km:.2f} km)")
                        return None
                    
                    # Valider route struktur (simpel loop, ikke for mange afvigelser)
                    route_start = route_coords[0] if route_coords else None
                    route_end = route_coords[-1] if route_coords else None
                    if route_start and route_end:
                        structure_check = validate_route_structure(
                            route_coords,
                            route_start,
                            route_end,
                            self.logger
                        )
                        if not structure_check['valid']:
                            self.logger.debug(f"Loop rute filtreret: dårlig struktur")
                            if not structure_check['is_loop']:
                                self.logger.debug(f"  - Ikke en loop (start-slut distance: {structure_check['start_end_distance_km']:.2f} km)")
                            if structure_check['too_many_deviations']:
                                self.logger.debug(f"  - For mange afvigelser ({structure_check['sharp_turns']} skarpe sving)")
                            return None
                
                # Evaluer rutekvalitet (undgå lange lige stykker og afvigende veje)
                waypoints_only = waypoint_list[1:-1]  # Fjern start/slut duplikater
                quality = evaluate_route_quality(
                    route_coords,
                    waypoints_only,
                    self.logger
                )
                
                # Filtrer ruter med dårlig kvalitet (lange lige stykker eller afvigende veje)
                if quality['score'] < 0.5:
                    self.logger.debug(f"Loop rute filtreret: dårlig kvalitet (score: {quality['score']:.2f})")
                    if quality.get('has_straight_sections'):
                        self.logger.debug(f"  - Lange lige stykker: {quality.get('max_straight_distance_km', 0):.2f} km")
                    if quality.get('deviates_from_waypoints'):
                        self.logger.debug(f"  - Afviger fra waypoints")
                    return None
                
                # Tilføj metadata
                route_data['start_address'] = start_address
                route_data['end_address'] = start_address  # Loop rute - slutter hvor den starter
                route_data['start_coords'] = start_coords
                route_data['end_coords'] = start_coords  # Loop rute
                route_data['route_name'] = f"Loop rute fra {start_address}"
                if direction:
                    route_data['route_name'] += f" ({direction})"
                route_data['quality_score'] = quality['score']
                
                # Gem god rute i cache for fremtidig læring (kun hvis kvalitet er god)
                if quality['score'] >= 0.6:
                    try:
                        self.route_cache.save_good_route(
                            route_data,
                            (start_coords['lat'], start_coords['lon']),
                            waypoints_only
                        )
                    except Exception as e:
                        self.logger.debug(f"Kunne ikke gemme rute i cache: {e}")
                
                self.logger.info(f"Loop rute accepteret: {route_data.get('distance', 0):.2f} km (kvalitet: {quality['score']:.2f})")
                return route_data
                
            except Exception as e:
                self.logger.error(f"Fejl ved loop rute søgning: {e}")
                import traceback
                self.logger.debug(traceback.format_exc())
                return None
        
        # Paralleliser rute søgninger for bedre performance
        self.logger.info(f"Starter paralleliseret loop rute søgning for {num_routes} ruter...")
        self.logger.info(f"Genereret {len(waypoint_sets)} waypoint sets")
        
        # Øg max_workers for bedre performance
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit alle rute søgninger
            future_to_waypoints = {
                executor.submit(find_single_loop_route, waypoint_list): waypoint_list 
                for waypoint_list in waypoint_sets
            }
            
            # Hent resultater når de er klar (early stopping når nok ruter er fundet)
            completed = 0
            for future in as_completed(future_to_waypoints):
                completed += 1
                if len(routes) >= num_routes:
                    # Stop når vi har nok gode ruter
                    self.logger.info(f"Fundet {len(routes)} gode ruter - stopper søgning")
                    break
                
                # Stop hvis vi har prøvet mange uden at finde nok (timeout)
                if completed >= num_routes * 10 and len(routes) == 0:
                    self.logger.warning(f"Har prøvet {completed} waypoint sets uden at finde ruter - stopper")
                    break
                
                route_data = future.result()
                if route_data:
                    routes.append(route_data)
                    self.logger.info(
                        f"Loop rute {len(routes)}/{num_routes} fundet: "
                        f"{route_data['distance']:.2f} km, {route_data['duration']:.1f} min"
                    )
        
        # Sorter ruter efter kvalitet (højeste først)
        routes.sort(key=lambda r: r.get('quality_score', 0.5), reverse=True)
        
        self.logger.info(f"Total loop ruter fundet: {len(routes)}/{num_routes}")
        return routes
    
    def save_route(
        self,
        route_data: Dict[str, Any],
        output_name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Gemmer en rute som GPX fil og HTML kort.
        
        Args:
            route_data: Rute data dict
            output_name: Output filnavn (uden extension)
            
        Returns:
            Dict med stier til gemte filer
        """
        if not output_name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_name = f"route_{timestamp}"
        
        routes_dir = self.config.get("output", {}).get("routes_dir", "output/routes")
        maps_dir = self.config.get("output", {}).get("maps_dir", "output/maps")
        static_maps_dir = self.config.get("output", {}).get("static_maps_dir", "output/maps/static")
        
        # Gem GPX
        gpx = create_gpx_from_route_data(
            route_data,
            name=route_data.get('route_name', 'Cykelrute'),
            description=f"Fra {route_data.get('start_address')} til {route_data.get('end_address')}",
            logger=self.logger
        )
        gpx_path = f"{routes_dir}/{output_name}.gpx"
        save_gpx(gpx, gpx_path, self.logger)
        
        # Gem interaktivt kort (HTML)
        map_obj = create_map_with_route_data(
            route_data,
            start_name="Start",
            end_name="Slut",
            route_name=route_data.get('route_name', 'Cykelrute'),
            logger=self.logger
        )
        map_path = f"{maps_dir}/{output_name}.html"
        save_map(map_obj, map_path, self.logger)
        
        result = {
            "gpx": gpx_path,
            "map": map_path
        }
        
        # Generer statisk kort hvis konfigureret
        static_map_config = self.config.get("static_maps", {})
        mapbox_config = static_map_config.get("mapbox", {})
        
        if mapbox_config.get("enabled", False):
            api_key = self.config.get("_env", {}).get("MAPBOX_API_KEY")
            if api_key:
                try:
                    static_image = create_static_map_image(
                        route_data,
                        api_key=api_key,
                        provider="mapbox",
                        start_name="Start",
                        end_name="Slut",
                        route_name=route_data.get('route_name', 'Cykelrute'),
                        width=mapbox_config.get("default_width", 800),
                        height=mapbox_config.get("default_height", 600),
                        style=mapbox_config.get("style", "mapbox/streets-v12"),
                        logger=self.logger
                    )
                    
                    if static_image:
                        static_map_path = f"{static_maps_dir}/{output_name}.png"
                        if save_static_map_image(static_image, static_map_path, self.logger):
                            result["static_map"] = static_map_path
                except Exception as e:
                    self.logger.warning(f"Kunne ikke generere statisk kort: {e}")
            else:
                self.logger.debug("Mapbox API key ikke fundet - springer statisk kort over")
        
        return result
