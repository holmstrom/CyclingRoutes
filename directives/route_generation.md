# Route Generation SOP

## Purpose
Generate scenic cycling loop routes on small, paved roads around Aarhus, Denmark.

## Algorithm: Hybrid Waypoint + A*

### Input
- Start coordinates (lat, lon)
- Target distance (10–100 km)
- Direction preference (N/NE/E/SE/S/SW/W/NW or any)
- Elevation preference (flat/rolling/hilly)
- Optional: include hill with minimum elevation gain

### Steps

1. **Download graph** — OSMnx cycling-filtered road graph, radius = target_km × 0.4 × 1000m
2. **Apply weights** — edge weight = road_type_factor × length_meters (see road_classification.md)
3. **Generate 5 waypoints** — elongated teardrop shape in preferred direction:
   - WP1: 40% reach, near outbound bearing
   - WP2: 85% reach, slightly rotated
   - WP3: 100% reach (apex), rotated 20–50° to create loop
   - WP4: 70% reach, return side (rotated 70–110°)
   - WP5: 35% reach, approaching start (rotated 130–170°)
   - reach = target_km / 4.5 (adjusted adaptively if distance is off)
4. **Route through waypoints** — A* shortest path with cycling_weight between consecutive waypoints
5. **Apply visited-edge penalty** (10×) after each segment to force different return roads
6. **Validate** — loop closure (≤100m gap), distance (±15%), overlap (<20%)
7. **Score** — quality 0.0–1.0 based on road types, overlap, straightness
8. **Retry** — up to 6 attempts with adaptive reach scaling

### Output
- List of (lat, lon) coordinates forming a closed loop
- Edge sequence for analysis
- Road type breakdown, overlap percentage, quality score

### Edge Cases
- Graph too sparse → fallback to network_type="all"
- No path between waypoints → try next-nearest node, or skip waypoint
- Distance consistently wrong → adaptive reach_divisor scaling
- Elevation API down → routes work without elevation, inform user
