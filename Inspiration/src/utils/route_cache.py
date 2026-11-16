"""
Cache system for at lære fra eksisterende gode ruter.
Gemmer information om gode ruter for at forbedre fremtidige forslag.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime
import hashlib


class RouteCache:
    """
    Cache system til at gemme og lære fra gode ruter.
    """
    
    def __init__(self, cache_dir: str = "cache/routes", logger: Optional[logging.Logger] = None):
        """
        Args:
            cache_dir: Mappe til at gemme cache filer
            logger: Optional logger
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger(__name__)
        self.cache_file = self.cache_dir / "good_routes.json"
        self.good_routes = self._load_cache()
    
    def _load_cache(self) -> List[Dict[str, Any]]:
        """Indlæser cache fra fil."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Kunne ikke indlæse route cache: {e}")
        return []
    
    def _save_cache(self):
        """Gemmer cache til fil."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.good_routes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Kunne ikke gemme route cache: {e}")
    
    def _route_hash(self, start_coords: Tuple[float, float], waypoints: List[Tuple[float, float]]) -> str:
        """Genererer hash for en rute baseret på koordinater."""
        coords_str = f"{start_coords[0]:.6f},{start_coords[1]:.6f}"
        for wp in waypoints:
            coords_str += f":{wp[0]:.6f},{wp[1]:.6f}"
        return hashlib.md5(coords_str.encode()).hexdigest()
    
    def save_good_route(
        self,
        route_data: Dict[str, Any],
        start_coords: Tuple[float, float],
        waypoints: List[Tuple[float, float]]
    ):
        """
        Gemmer en god rute i cache.
        
        Args:
            route_data: Rute data dict
            start_coords: Start koordinater
            waypoints: Liste af waypoint koordinater
        """
        route_hash = self._route_hash(start_coords, waypoints)
        
        # Tjek om ruten allerede er i cache
        existing = next((r for r in self.good_routes if r.get('hash') == route_hash), None)
        
        if existing:
            # Opdater eksisterende
            existing['last_used'] = datetime.now().isoformat()
            existing['use_count'] = existing.get('use_count', 0) + 1
        else:
            # Tilføj ny
            good_route = {
                'hash': route_hash,
                'start_coords': start_coords,
                'waypoints': waypoints,
                'distance': route_data.get('distance', 0),
                'elevation_gain': route_data.get('elevation_gain'),
                'coordinates': route_data.get('coordinates', [])[:100],  # Gem kun første 100 koordinater
                'created': datetime.now().isoformat(),
                'last_used': datetime.now().isoformat(),
                'use_count': 1
            }
            self.good_routes.append(good_route)
            
            # Behold kun de 100 bedste ruter
            if len(self.good_routes) > 100:
                self.good_routes.sort(key=lambda x: x.get('use_count', 0), reverse=True)
                self.good_routes = self.good_routes[:100]
        
        self._save_cache()
    
    def get_similar_waypoints(
        self,
        start_coords: Tuple[float, float],
        target_distance: float,
        direction: Optional[str] = None,
        num_suggestions: int = 3
    ) -> List[List[Tuple[float, float]]]:
        """
        Finder lignende waypoint patterns fra cache.
        
        Args:
            start_coords: Start koordinater
            target_distance: Mål distance
            direction: Retning (hvis specificeret)
            num_suggestions: Antal forslag
            
        Returns:
            Liste af waypoint lister fra cache
        """
        if not self.good_routes:
            return []
        
        # Find ruter med lignende distance og retning
        similar_routes = []
        for route in self.good_routes:
            route_distance = route.get('distance', 0)
            # Tjek om distance er inden for 30% af target
            if 0.7 * target_distance <= route_distance <= 1.3 * target_distance:
                # Tjek retning hvis specificeret
                if direction and route.get('waypoints'):
                    first_wp = route['waypoints'][0] if route['waypoints'] else None
                    if first_wp:
                        # Simpel retning check (kan forbedres)
                        similar_routes.append(route)
                else:
                    similar_routes.append(route)
        
        # Sorter efter use_count og distance match
        similar_routes.sort(
            key=lambda x: (
                x.get('use_count', 0),
                -abs(x.get('distance', 0) - target_distance)
            ),
            reverse=True
        )
        
        # Returner waypoints fra de bedste matches
        suggestions = []
        for route in similar_routes[:num_suggestions]:
            if route.get('waypoints'):
                suggestions.append(route['waypoints'])
        
        return suggestions
    
    def get_waypoint_patterns(self) -> List[Dict[str, Any]]:
        """
        Henter waypoint patterns fra cache for at lære strukturen af gode ruter.
        
        Returns:
            Liste af waypoint patterns
        """
        patterns = []
        for route in self.good_routes:
            if route.get('waypoints') and len(route['waypoints']) >= 3:
                patterns.append({
                    'waypoints': route['waypoints'],
                    'distance': route.get('distance', 0),
                    'use_count': route.get('use_count', 0)
                })
        return patterns

