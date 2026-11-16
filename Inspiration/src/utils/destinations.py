"""
Liste af interessante destinationer i Aarhus til rute forslag.
"""

# Populære destinationer i Aarhus med specifikke adresser der findes i DAWA
AARHUS_DESTINATIONS = [
    {
        "name": "Aarhus Hovedbanegård",
        "address": "Hovedbanegårdspladsen",
        "category": "Transport"
    },
    {
        "name": "Aarhus Universitet",
        "address": "Nordre Ringgade",
        "category": "Uddannelse"
    },
    {
        "name": "ARoS Aarhus Kunstmuseum",
        "address": "Aros Allé",
        "category": "Kultur"
    },
    {
        "name": "Marselisborg Slot",
        "address": "Kongevejen",
        "category": "Seværdighed"
    },
    {
        "name": "Den Gamle By",
        "address": "Viborgvej",
        "category": "Museum"
    },
    {
        "name": "Moesgård Museum",
        "address": "Moesgård Allé",
        "category": "Museum"
    },
    {
        "name": "Tivoli Friheden",
        "address": "Skanderborgvej",
        "category": "Fritid"
    },
    {
        "name": "Dokk1",
        "address": "Hack Kampmanns Plads",
        "category": "Kultur"
    },
    {
        "name": "Aarhus Havn",
        "address": "Havnepladsen",
        "category": "Seværdighed"
    },
    {
        "name": "Botanisk Have",
        "address": "Peter Holms Vej",
        "category": "Natur"
    },
    {
        "name": "Risskov Strand",
        "address": "Strandvejen",
        "category": "Natur"
    },
    {
        "name": "Viborgvej",
        "address": "Viborgvej",
        "category": "Shopping"
    },
    {
        "name": "Skt. Clemens Torv",
        "address": "Skt. Clemens Torv",
        "category": "Shopping"
    },
    {
        "name": "Aarhus Domkirke",
        "address": "Store Torv",
        "category": "Seværdighed"
    },
    {
        "name": "Vejlby Risskov Skov",
        "address": "Vejlby Skovvej",
        "category": "Natur"
    }
]


def get_destinations_for_routes(count: int = 5) -> list:
    """
    Returnerer en liste af destinationer til rute forslag.
    
    Args:
        count: Antal destinationer at returnere
        
    Returns:
        Liste af destination dicts
    """
    return AARHUS_DESTINATIONS[:count]


def get_random_destinations(count: int = 5) -> list:
    """
    Returnerer tilfældige destinationer.
    
    Args:
        count: Antal destinationer at returnere
        
    Returns:
        Liste af destination dicts
    """
    import random
    return random.sample(AARHUS_DESTINATIONS, min(count, len(AARHUS_DESTINATIONS)))

