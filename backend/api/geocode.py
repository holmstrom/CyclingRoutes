"""
Geocoding endpoint — address to coordinates lookup.
"""

from fastapi import APIRouter, HTTPException, Query

from execution.connectors.geocoder import geocode

router = APIRouter()


@router.get("/geocode")
async def geocode_address(q: str = Query(..., min_length=2)):
    """Geocode an address string.

    Returns lat, lon, and display_name.
    """
    result = geocode(q)
    if not result:
        raise HTTPException(status_code=404, detail="Address not found")
    return result
