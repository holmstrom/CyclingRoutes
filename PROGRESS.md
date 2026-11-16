# RouteFinder — Progress Log

## Status: Working MVP

### What Works
- [x] OSM graph download + disk caching (`.tmp/graphs/`, 30-day TTL)
- [x] Edge weighting by road type (cycleway 1.0 → primary 8.0, highways excluded)
- [x] Unpaved surface exclusion (gravel, dirt, mud, etc.)
- [x] Hybrid loop algorithm: 5-waypoint teardrop shape + A* routing
- [x] Visited-edge penalty (10×) forces outbound and return on different roads
- [x] 3 diverse route alternatives (< 30% edge overlap between them)
- [x] Adaptive reach scaling when distance is off target
- [x] Open Elevation API integration with batching + interpolation
- [x] GPX 1.1 export (`<trk>/<trkpt>/<ele>`) compatible with Strava/RideWithGPS
- [x] Nominatim geocoding with 1 req/sec rate limiting
- [x] FastAPI backend with CORS + 4 endpoints
- [x] Next.js frontend: full-screen OSM map, glassmorphism control panel
- [x] Address search, distance slider (10–100km), compass rose, elevation picker, hill selector
- [x] Route tabs, elevation chart (Recharts), road breakdown bar, GPX download
- [x] API proxy: Next.js → FastAPI (`127.0.0.1` not `localhost` — critical on Windows)

### Challenges Solved
- **`network_type="bike"` doesn't exist in OSMnx** → use `custom_filter` with Overpass QL
- **scikit-learn required** for `ox.distance.nearest_nodes()` on unprojected graphs
- **Reach divisor tuning** — initial `target_km / 3.5` produced routes too long; changed to `4.5` + adaptive scaling
- **Windows localhost → IPv6** — Next.js proxy `localhost:8000` fails; must use `127.0.0.1:8000`
- **Blank page** — `html, body` needed `height: 100%` for the full-screen Leaflet map to render
- **`sleep` broken in bash env** — must use `python -c "import time; time.sleep(N)"`
- **Stale backend process** — old process (missing routes router) kept answering; fixed by hard-killing all Python processes
- **Async event loop blocked** — `generate_route` is 30–90s sync; must wrap in `asyncio.run_in_executor`
- **Next.js proxy 30s timeout** — rewrite proxy has hard 30s limit; replaced with App Router API route handler (`maxDuration=300`)
- **No-path routing failures** — segment 5 failing on disconnected subgraphs → fixed by using `ox.truncate.largest_component(strongly=True)` before routing
- **Oscillating reach_divisor** — direct ratio update caused divergence; fixed with rng state restoration (same jitter per calibration) + ±20% clamp per step
- **Slow route generation (158s)** — graph reloaded from disk (GraphML XML) for every alternative; fixed by: (1) pickle cache (10-20× faster than GraphML), (2) hoisting graph loading out of the alternative loop so all 3 routes share one load. Now **~25s** total.

### Not Yet Solved
- Elevation API unreliable — Open Elevation often slow/down; routes return 0m gain in that case
- No persistent route storage — routes lost on backend restart (in-memory store only)
- Hill finder not well-tested — depends on elevation API being available

### What's Next
- [ ] Add a loading progress indicator (currently just "Generating..." with spinner)
- [ ] Test GPX import into Strava and RideWithGPS
- [ ] Test more distances and directions (currently only tested south from Aarhus center)
- [ ] Handle case where only 1-2 alternatives found (show what we have, don't error)
- [ ] Add ability to drag the start marker on the map
- [ ] Consider caching routes in a SQLite file for persistence across restarts

## How to Run

```bash
# Terminal 1 — Backend
cd C:\Projects\RouteFinder
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd C:\Projects\RouteFinder\frontend
npm run dev
```

**App:** http://localhost:3000
**API docs:** http://localhost:8000/docs

## Key Numbers (verified)
- 30km route: ~30–31km actual, 92–97% quality score, < 3% overlap
- Road composition: ~29–33% cycleway, 33–44% tertiary, 13–26% residential, < 2% secondary
- Generation time: ~25s for 3 alternatives (cached graph, pickle format)
- Graph size (30km target, 12km radius): 45,457 nodes, 103,026 edges (SCC)
- GPX file size: ~68KB for 75km route (~730 trackpoints)
