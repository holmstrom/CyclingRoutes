"""
DAWA (Dataforsyningen) connector for geodata.
DAWA er en offentlig API - ingen credentials nødvendig.
"""

import logging
from typing import List, Dict, Any, Optional
from ..utils.http import HTTPClient


def get_aarhus_addresses(
    base_url: str,
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Henter alle adresser i Aarhus Kommune.
    
    Args:
        base_url: DAWA base URL
        logger: Optional logger
        
    Returns:
        Liste af adresser i Aarhus
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    # Aarhus Kommune kode: 751
    endpoint = f"{base_url}/adresser"
    params = {
        "kommunekode": "751",
        "per_side": 1000
    }
    
    all_addresses = []
    page = 0
    
    while True:
        params["side"] = page
        try:
            response = client.get(endpoint, params=params)
            addresses = response.json()
            
            if not addresses:
                break
                
            all_addresses.extend(addresses)
            logger.info(f"Hentet {len(addresses)} adresser (side {page})")
            page += 1
            
        except Exception as e:
            logger.error(f"Fejl ved hentning af adresser: {e}")
            break
    
    logger.info(f"Total adresser hentet: {len(all_addresses)}")
    return all_addresses


def search_address(
    base_url: str,
    query: str,
    logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Søger efter en adresse i DAWA.
    Prøver flere metoder for at finde adresser.
    
    Args:
        base_url: DAWA base URL
        query: Søgestreng (fx "Nørrebrogade 1, 8000 Aarhus C")
        logger: Optional logger
        
    Returns:
        Liste af matchende adresser
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    # Metode 1: Prøv autocomplete først
    endpoint = f"{base_url}/adresser/autocomplete"
    params = {"q": query, "per_side": 20}
    
    try:
        response = client.get(endpoint, params=params)
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            logger.info(f"Autocomplete fundet {len(data)} matches for: {query}")
            return data
    except Exception as e:
        logger.debug(f"Autocomplete fejlede: {e}")
    
    # Metode 2: Hvis autocomplete ikke virker, prøv direkte adresse søgning
    # Ekstraher vejnavn fra query
    vejnavn = query.split(',')[0].strip() if ',' in query else query.strip()
    # Fjern husnummer hvis det er der
    vejnavn_parts = vejnavn.split()
    if len(vejnavn_parts) > 1 and vejnavn_parts[-1].isdigit():
        vejnavn = ' '.join(vejnavn_parts[:-1])
    
    endpoint2 = f"{base_url}/adresser"
    params2 = {"vejnavn": vejnavn, "postnr": "8000", "per_side": 10}
    
    try:
        response2 = client.get(endpoint2, params=params2)
        data2 = response2.json()
        
        if isinstance(data2, list) and len(data2) > 0:
            logger.info(f"Direkte søgning fundet {len(data2)} matches for: {vejnavn}")
            # Konverter til autocomplete format
            matches = []
            for addr in data2[:10]:  # Tag første 10
                x = addr.get('x')
                y = addr.get('y')
                if x is not None and y is not None:
                    matches.append({
                        'tekst': f"{addr.get('vejnavn', '')} {addr.get('husnr', '')}, {addr.get('postnrnavn', '')}",
                        'adresse': {
                            'x': x,
                            'y': y
                        }
                    })
            return matches
    except Exception as e:
        logger.debug(f"Direkte søgning fejlede: {e}")
    
    logger.warning(f"Ingen matches fundet for: {query}")
    return []


def get_address_coordinates(
    base_url: str,
    address: str,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, float]]:
    """
    Henter koordinater for en adresse.
    
    Args:
        base_url: DAWA base URL
        address: Adresse streng
        logger: Optional logger
        
    Returns:
        Dict med 'lat' og 'lon', eller None hvis ikke fundet
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    # Prøv først med den fulde adresse
    matches = search_address(base_url, address, logger)
    
    # Hvis ingen matches, prøv at fjerne postnummer og bynavn
    if not matches or len(matches) == 0:
        # Prøv kun med gadenavn og husnummer
        parts = address.split(',')
        if len(parts) > 1:
            simplified = parts[0].strip()
            logger.info(f"Prøver simplificeret søgning: {simplified}")
            matches = search_address(base_url, simplified, logger)
    
    # Hvis stadig ingen matches, prøv kun med første del (gadenavn)
    if not matches or len(matches) == 0:
        parts = address.split()
        if len(parts) > 0:
            # Tag første 2-3 ord (typisk gadenavn)
            simplified = ' '.join(parts[:2])
            logger.info(f"Prøver kun gadenavn: {simplified}")
            matches = search_address(base_url, simplified, logger)
    
    if not matches or len(matches) == 0:
        logger.warning(f"Ingen matches fundet for adresse: {address}")
        return None
    
    first_match = matches[0]
    
    # DAWA autocomplete returnerer struktur: {'tekst': '...', 'adresse': {...}}
    # Adresse objektet har 'x' (lon) og 'y' (lat) koordinater direkte
    if 'adresse' in first_match:
        adresse = first_match['adresse']
        x = adresse.get('x')  # Longitude
        y = adresse.get('y')  # Latitude
        
        if x is not None and y is not None:
            logger.info(f"Koordinater fundet via adresse objekt: ({y}, {x})")
            return {
                'lat': y,
                'lon': x
            }
    
    # Fallback: Prøv adgangsadresse struktur (hvis det er en anden endpoint)
    if 'adgangsadresse' in first_match:
        adgangsadresse = first_match['adgangsadresse']
        if 'adgangspunkt' in adgangsadresse:
            punkt = adgangsadresse['adgangspunkt']
            koordinater = punkt.get('koordinater', [])
            if len(koordinater) >= 2:
                logger.info(f"Koordinater fundet via adgangspunkt: ({koordinater[1]}, {koordinater[0]})")
                return {
                    'lat': koordinater[1],  # GeoJSON format: [lon, lat]
                    'lon': koordinater[0]
                }
    
    # Prøv også vejpunkt hvis adgangspunkt ikke virker
    if 'vejpunkt' in first_match:
        vejpunkt = first_match['vejpunkt']
        koordinater = vejpunkt.get('koordinater', [])
        if len(koordinater) >= 2:
            logger.info(f"Koordinater fundet via vejpunkt: ({koordinater[1]}, {koordinater[0]})")
            return {
                'lat': koordinater[1],
                'lon': koordinater[0]
            }
    
    logger.warning(f"Kunne ikke finde koordinater i match for adresse: {address}")
    logger.debug(f"Match data keys: {list(first_match.keys())}")
    return None

