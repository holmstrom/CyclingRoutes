"""
Inspiration routes — list and serve GPX files from Inspiration/ridewithgps/.
"""

import os
from xml.etree import ElementTree as ET

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

GPX_DIR = os.path.join("Inspiration", "ridewithgps")
NS = {"g": "http://www.topografix.com/GPX/1/1"}

# Cache parsed metadata so we don't re-parse 115 files on every request
_metadata_cache: list[dict] | None = None


class InspirationRoute(BaseModel):
    filename: str
    name: str
    point_count: int
    coordinates: list[list[float]]  # [[lat, lon], ...]


def _parse_gpx_metadata(path: str, filename: str) -> dict | None:
    """Extract name and coordinates from a GPX file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        # Get route name from metadata or rte/trk name
        name = filename.replace("_", " ").replace(".gpx", "")
        name_el = root.find(".//g:metadata/g:name", NS)
        if name_el is not None and name_el.text:
            name = name_el.text
        else:
            name_el = root.find(".//g:rte/g:name", NS) or root.find(".//g:trk/g:name", NS)
            if name_el is not None and name_el.text:
                name = name_el.text

        # Get coordinates (rtept or trkpt)
        pts = root.findall(".//g:rtept", NS) or root.findall(".//g:trkpt", NS)
        coords = []
        # Sample every Nth point for preview (keep it lightweight)
        sample = max(1, len(pts) // 200)
        for i, pt in enumerate(pts):
            if i % sample == 0:
                try:
                    coords.append([float(pt.get("lat")), float(pt.get("lon"))])
                except (TypeError, ValueError):
                    pass
        # Always include last point
        if pts and len(coords) > 0:
            try:
                last = [float(pts[-1].get("lat")), float(pts[-1].get("lon"))]
                if coords[-1] != last:
                    coords.append(last)
            except (TypeError, ValueError):
                pass

        if not coords:
            return None

        return {
            "filename": filename,
            "name": name,
            "point_count": len(pts),
            "coordinates": coords,
        }
    except Exception:
        return None


def _get_all_metadata() -> list[dict]:
    """Parse all GPX files and cache results."""
    global _metadata_cache
    if _metadata_cache is not None:
        return _metadata_cache

    if not os.path.isdir(GPX_DIR):
        return []

    results = []
    files = sorted(f for f in os.listdir(GPX_DIR) if f.lower().endswith(".gpx"))
    for fname in files:
        meta = _parse_gpx_metadata(os.path.join(GPX_DIR, fname), fname)
        if meta:
            results.append(meta)

    _metadata_cache = results
    return results


@router.get("/inspiration/routes")
async def list_inspiration_routes() -> list[InspirationRoute]:
    """List all inspiration routes with preview coordinates."""
    return [InspirationRoute(**m) for m in _get_all_metadata()]


@router.get("/inspiration/routes/{filename}")
async def get_inspiration_route(filename: str):
    """Get full GPX file for download."""
    path = os.path.join(GPX_DIR, filename)
    if not os.path.isfile(path) or not filename.lower().endswith(".gpx"):
        raise HTTPException(status_code=404, detail="Route not found")

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="application/gpx+xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
