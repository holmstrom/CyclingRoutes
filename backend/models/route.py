"""
Pydantic models for route request and response.
"""

from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    start_lat: float = Field(..., ge=-90, le=90)
    start_lon: float = Field(..., ge=-180, le=180)
    target_distance_km: float = Field(..., ge=10, le=100, alias="distance_km")
    direction: str | None = Field(
        None,
        pattern="^(north|northeast|east|southeast|south|southwest|west|northwest)$",
    )
    elevation_preference: str | None = Field(
        None, pattern="^(flat|rolling|hilly)$"
    )
    include_hill_min_m: float | None = Field(None, ge=0, le=1000)
    num_alternatives: int = Field(3, ge=1, le=5)

    class Config:
        populate_by_name = True


class Coordinate(BaseModel):
    lat: float
    lon: float
    ele: float | None = None


class ElevationPoint(BaseModel):
    distance_km: float
    elevation_m: float


class RouteAlternative(BaseModel):
    id: str
    distance_km: float
    elevation_gain_m: float
    elevation_loss_m: float
    estimated_duration_min: int
    quality_score: float
    road_breakdown: dict[str, float]
    coordinates: list[Coordinate]
    elevation_profile: list[ElevationPoint]


class RouteResponse(BaseModel):
    routes: list[RouteAlternative]
