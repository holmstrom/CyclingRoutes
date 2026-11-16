"""
Config loading utility.
"""

from pathlib import Path
import yaml
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional


def load_yaml(path: str) -> Dict[str, Any]:
    """
    Indlæser en YAML fil.
    
    Args:
        path: Sti til YAML fil
        
    Returns:
        Dict med YAML indhold
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(
    config_path: str = "config.yaml",
    env_file: str = ".env",
    environment: str = "dev"
) -> Dict[str, Any]:
    """
    Indlæser konfiguration fra YAML og .env fil.
    
    Args:
        config_path: Sti til config.yaml
        env_file: Sti til .env fil
        environment: Environment navn (dev, test, prod)
        
    Returns:
        Dict med konfiguration
    """
    # Indlæs .env fil hvis den eksisterer
    if Path(env_file).exists():
        load_dotenv(env_file)
    
    # Indlæs YAML config
    config = load_yaml(config_path)
    
    # Hent environment specifik config
    env_config = config.get("environments", {}).get(environment, {})
    
    # Tilføj environment variabler
    env_config["_env"] = {
        "OPENWEATHERMAP_API_KEY": os.getenv("OPENWEATHERMAP_API_KEY"),
        "OPENROUTESERVICE_API_KEY": os.getenv("OPENROUTESERVICE_API_KEY"),
        "ORS_API_KEY": os.getenv("ORS_API_KEY") or os.getenv("OPENROUTESERVICE_API_KEY"),  # Support both names
        "GRAPHHOPPER_API_KEY": os.getenv("GRAPHHOPPER_API_KEY"),
        "MAPBOX_API_KEY": os.getenv("MAPBOX_API_KEY"),
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO")
    }
    
    return env_config


def get_config_value(
    config: Dict[str, Any],
    key_path: str,
    default: Any = None
) -> Any:
    """
    Henter en værdi fra config ved hjælp af punkt-separeret key path.
    
    Args:
        config: Config dict
        key_path: Punkt-separeret path (fx "weather.openweathermap.base_url")
        default: Default værdi hvis ikke fundet
        
    Returns:
        Config værdi eller default
    """
    keys = key_path.split(".")
    value = config
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    
    return value


