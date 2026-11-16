"""
Vejrdata connectors:
- OpenWeatherMap (gratis tier)
- DMI OpenData (hvis tilgængelig)
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from ..utils.http import HTTPClient


def get_weather_openweathermap(
    base_url: str,
    api_key: str,
    lat: float,
    lon: float,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter vejrdata fra OpenWeatherMap.
    
    Args:
        base_url: OpenWeatherMap base URL
        api_key: API key
        lat: Latitude
        lon: Longitude
        logger: Optional logger
        
    Returns:
        Vejrdata dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    endpoint = f"{base_url}/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",  # Celsius, m/s
        "lang": "da"  # Dansk sprog
    }
    
    try:
        response = client.get(endpoint, params=params)
        data = response.json()
        
        # Ekstraher relevante data
        weather_info = {
            "temperature": data.get("main", {}).get("temp"),
            "feels_like": data.get("main", {}).get("feels_like"),
            "humidity": data.get("main", {}).get("humidity"),
            "wind_speed": data.get("wind", {}).get("speed"),  # m/s
            "wind_direction": data.get("wind", {}).get("deg"),  # grader
            "rain": data.get("rain", {}).get("1h", 0),  # mm
            "description": data.get("weather", [{}])[0].get("description", ""),
            "main": data.get("weather", [{}])[0].get("main", ""),
            "timestamp": datetime.now().isoformat()
        }
        
        return weather_info
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af vejrdata: {e}")
        return None


def get_weather_forecast_openweathermap(
    base_url: str,
    api_key: str,
    lat: float,
    lon: float,
    hours: int = 24,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter vejrudsigtsdata fra OpenWeatherMap.
    
    Args:
        base_url: OpenWeatherMap base URL
        api_key: API key
        lat: Latitude
        lon: Longitude
        hours: Antal timer frem (maks 48)
        logger: Optional logger
        
    Returns:
        Vejrudsigtsdata dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    endpoint = f"{base_url}/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "lang": "da",
        "cnt": min(hours // 3, 16)  # OpenWeatherMap giver 3-timers intervaller
    }
    
    try:
        response = client.get(endpoint, params=params)
        data = response.json()
        
        forecasts = []
        for item in data.get("list", []):
            forecasts.append({
                "datetime": item.get("dt_txt"),
                "temperature": item.get("main", {}).get("temp"),
                "wind_speed": item.get("wind", {}).get("speed"),
                "wind_direction": item.get("wind", {}).get("deg"),
                "rain": item.get("rain", {}).get("3h", 0),
                "description": item.get("weather", [{}])[0].get("description", ""),
                "main": item.get("weather", [{}])[0].get("main", "")
            })
        
        return {
            "forecasts": forecasts,
            "city": data.get("city", {}).get("name"),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af vejrudsigtsdata: {e}")
        return None


def is_good_cycling_weather(weather_data: Dict[str, Any]) -> bool:
    """
    Vurderer om vejret er godt til cykling.
    
    Args:
        weather_data: Vejrdata dict
        
    Returns:
        True hvis vejret er godt til cykling
    """
    if not weather_data:
        return False
    
    # Undgå regn
    rain = weather_data.get("rain", 0)
    if rain > 0.1:  # Mere end 0.1 mm regn
        return False
    
    # Undgå stærk modvind (kan justeres baseret på retning)
    wind_speed = weather_data.get("wind_speed", 0)
    if wind_speed > 10:  # Mere end 10 m/s (36 km/h)
        return False
    
    # Undgå ekstremt koldt vejr
    temperature = weather_data.get("temperature", 0)
    if temperature < -5:  # Under -5 grader
        return False
    
    return True


