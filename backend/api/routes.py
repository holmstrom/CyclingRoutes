"""
Route generation and GPX download endpoints.
"""

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend.models.route import RouteRequest, RouteResponse
from backend.services.route_service import generate_route, get_gpx

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate-route", response_model=RouteResponse)
async def generate_route_endpoint(request: RouteRequest):
    """Generate cycling route alternatives.

    Route generation is CPU-bound and takes 30–90s.
    Run it in a thread pool so uvicorn's event loop stays responsive.
    """
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(None, partial(generate_route, request))
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Route generation failed")
        raise HTTPException(status_code=500, detail=f"Route generation failed: {str(e)}")


@router.get("/route/{route_id}/gpx")
async def download_gpx(route_id: str):
    """Download GPX file for a specific route alternative."""
    gpx_xml = get_gpx(route_id)
    if not gpx_xml:
        raise HTTPException(status_code=404, detail="Route not found")
    return Response(
        content=gpx_xml,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f"attachment; filename=route_{route_id}.gpx"},
    )
