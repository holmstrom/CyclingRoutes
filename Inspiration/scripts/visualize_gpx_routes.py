"""
Visualize GPX routes on an interactive Folium map.

Usage:
    python scripts/visualize_gpx_routes.py \
        --gpx-dir "docs/gpx routes/ridewithgps" \
        --out "output/maps/ridewithgps_routes.html"
"""

import argparse
from pathlib import Path
from typing import List, Tuple

import folium
import gpxpy


def load_gpx_coordinates(path: Path) -> List[Tuple[float, float]]:
    """Return a flat list of (lat, lon) from tracks and routes in a GPX file."""
    coords: List[Tuple[float, float]] = []
    with path.open("r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    # Tracks
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.latitude, point.longitude))

    # Routes (fallback if no tracks)
    if not coords:
        for route in gpx.routes:
            for point in route.points:
                coords.append((point.latitude, point.longitude))

    return coords


def build_map(gpx_files: List[Path]) -> folium.Map:
    """Create a folium map with all GPX routes layered."""
    all_coords: List[Tuple[float, float]] = []
    for gpx_file in gpx_files:
        coords = load_gpx_coordinates(gpx_file)
        all_coords.extend(coords)

    if not all_coords:
        raise ValueError("Ingen koordinater fundet i GPX-filerne.")

    # Center map on average coordinate
    lats = [c[0] for c in all_coords]
    lons = [c[1] for c in all_coords]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))

    m = folium.Map(location=center, zoom_start=11, tiles="OpenStreetMap")

    colors = [
        "red",
        "blue",
        "green",
        "purple",
        "orange",
        "darkred",
        "lightred",
        "beige",
        "darkblue",
        "darkgreen",
        "cadetblue",
        "darkpurple",
        "white",
        "pink",
        "lightblue",
        "lightgreen",
        "gray",
        "black",
        "lightgray",
    ]

    for idx, gpx_file in enumerate(gpx_files):
        coords = load_gpx_coordinates(gpx_file)
        if not coords:
            continue

        color = colors[idx % len(colors)]
        name = gpx_file.stem

        layer = folium.FeatureGroup(name=name, show=idx < 20)  # show first 20 by default
        folium.PolyLine(
            coords,
            color=color,
            weight=3,
            opacity=0.8,
            tooltip=name,
        ).add_to(layer)

        # Start/stop markers
        folium.CircleMarker(
            location=coords[0],
            radius=4,
            color="green",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{name} start",
        ).add_to(layer)
        folium.CircleMarker(
            location=coords[-1],
            radius=4,
            color="red",
            fill=True,
            fill_opacity=0.9,
            tooltip=f"{name} slut",
        ).add_to(layer)

        layer.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualiser GPX-ruter på kort.")
    parser.add_argument(
        "--gpx-dir",
        default="docs/gpx routes/ridewithgps",
        type=str,
        help="Mappe med GPX-filer.",
    )
    parser.add_argument(
        "--out",
        default="output/maps/ridewithgps_routes.html",
        type=str,
        help="Output HTML-kort.",
    )
    args = parser.parse_args()

    gpx_dir = Path(args.gpx_dir)
    if not gpx_dir.exists():
        raise FileNotFoundError(f"GPX-mappe findes ikke: {gpx_dir}")

    gpx_files = sorted(gpx_dir.glob("*.gpx"))
    if not gpx_files:
        raise FileNotFoundError(f"Ingen GPX-filer i {gpx_dir}")

    print(f"Finder {len(gpx_files)} GPX-filer i {gpx_dir}")
    m = build_map(gpx_files)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(out_path))
    print(f"Kort gemt til {out_path.resolve()}")


if __name__ == "__main__":
    main()

