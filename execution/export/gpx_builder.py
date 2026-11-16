"""
Build GPX 1.1 files compatible with Strava, RideWithGPS, Garmin, and Wahoo.

Uses track format (<trk>/<trkseg>/<trkpt>) with elevation data.
"""

from datetime import datetime, timezone

import gpxpy
import gpxpy.gpx


def build_gpx(
    coordinates: list[tuple[float, float]],
    elevations: list[float] | None = None,
    name: str = "RouteFinder Route",
    description: str = "",
) -> str:
    """Build a GPX 1.1 XML string with track and elevation.

    Args:
        coordinates: List of (lat, lon) tuples.
        elevations: Optional list of elevation values (meters), same length as coordinates.
        name: Route name for GPX metadata.
        description: Route description.

    Returns:
        GPX XML string.
    """
    gpx = gpxpy.gpx.GPX()
    gpx.creator = "RouteFinder"
    gpx.name = name
    gpx.description = description
    gpx.time = datetime.now(timezone.utc)

    # Create track
    track = gpxpy.gpx.GPXTrack()
    track.name = name
    track.description = description
    gpx.tracks.append(track)

    # Create segment
    segment = gpxpy.gpx.GPXTrackSegment()
    track.segments.append(segment)

    # Add track points
    for i, (lat, lon) in enumerate(coordinates):
        point = gpxpy.gpx.GPXTrackPoint(latitude=lat, longitude=lon)
        if elevations and i < len(elevations):
            point.elevation = elevations[i]
        segment.points.append(point)

    return gpx.to_xml()
