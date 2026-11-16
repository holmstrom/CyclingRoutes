# GPX Format SOP

## Format
- GPX version 1.1
- XML namespace: `http://www.topografix.com/GPX/1/1`
- Creator: `RouteFinder`

## Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1" creator="RouteFinder">
  <metadata>
    <name>Route name</name>
    <desc>Distance and elevation info</desc>
    <time>2024-01-01T00:00:00Z</time>
  </metadata>
  <trk>
    <name>Route name</name>
    <trkseg>
      <trkpt lat="56.1500" lon="10.2000">
        <ele>45.0</ele>
      </trkpt>
      <!-- More track points -->
    </trkseg>
  </trk>
</gpx>
```

## Rules

1. Use `<trk>/<trkseg>/<trkpt>` format (track), NOT `<rte>/<rtept>` (route)
2. Include `<ele>` element on each trackpoint with elevation in meters
3. Do NOT include `<time>` on individual trackpoints (these are planned routes, not recordings)
4. Include `<time>` only in `<metadata>` (creation timestamp)
5. Metadata `<desc>` should include distance and elevation gain

## Compatibility

Tested with:
- Strava (import as route)
- RideWithGPS (import as route)
- Garmin Connect (import as course)
- Wahoo (import via companion app)

All require track format with elevation data for proper display.
