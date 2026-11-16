"use client";

import "leaflet/dist/leaflet.css";
import { useEffect, useState, useMemo, useCallback } from "react";
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  CircleMarker,
  Tooltip,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import type { InspirationRoute, RouteAlternative, WindInfo } from "@/lib/types";
import { detectHills } from "@/lib/hills";

const ROUTE_COLORS = ["#3b82f6", "#10b981", "#f59e0b"];
const AARHUS_CENTER: [number, number] = [56.15, 10.2];

// Gradient color scale for route steepness
function gradientColor(absGradientPct: number): string {
  if (absGradientPct < 3) return "#22c55e";  // green — flat
  if (absGradientPct < 6) return "#eab308";  // yellow — moderate
  if (absGradientPct < 9) return "#f97316";  // orange — steep
  return "#ef4444";                           // red — very steep
}

// Custom start marker icon
const startIcon = new L.DivIcon({
  html: `<div style="
    width: 28px; height: 28px;
    background: #ef4444;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow: 0 2px 8px rgba(0,0,0,0.4);
  "></div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  className: "",
});

function MapClickHandler({
  onMapClick,
}: {
  onMapClick: (lat: number, lon: number) => void;
}) {
  useMapEvents({
    click(e) {
      onMapClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function FitBounds({
  routes,
  selectedIndex,
}: {
  routes: RouteAlternative[];
  selectedIndex: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (routes.length === 0) return;
    const route = routes[selectedIndex];
    if (!route || route.coordinates.length === 0) return;

    const bounds = L.latLngBounds(
      route.coordinates.map((c) => [c.lat, c.lon] as [number, number])
    );
    map.fitBounds(bounds, { padding: [60, 60], maxZoom: 14 });
  }, [routes, selectedIndex, map]);

  return null;
}

interface HoverTooltipState {
  x: number;
  y: number;
  km: number;
  ele: number | null;
}

interface RouteMapProps {
  routes: RouteAlternative[];
  selectedRouteIndex: number;
  startLocation: { lat: number; lon: number } | null;
  onMapClick: (lat: number, lon: number) => void;
  onSelectRoute: (index: number) => void;
  hoveredDistanceKm?: number | null;
  onRouteHover?: (km: number | null) => void;
  activeHillIndex?: number | null;
  onActiveHillChange?: (index: number | null) => void;
  wind?: WindInfo | null;
  inspirationRoutes?: InspirationRoute[];
  selectedInspirationFilenames?: Set<string>;
}

export default function RouteMap({
  routes,
  selectedRouteIndex,
  startLocation,
  onMapClick,
  onSelectRoute,
  hoveredDistanceKm,
  onRouteHover,
  activeHillIndex,
  onActiveHillChange,
  wind,
  inspirationRoutes,
  selectedInspirationFilenames,
}: RouteMapProps) {
  const [hoverTooltip, setHoverTooltip] = useState<HoverTooltipState | null>(null);

  // Precompute cumulative distances, elevation profile lookup, hills, and gradient segments
  const { cumulativeKm, hills, profileArr, gradientSegments } = useMemo(() => {
    const route = routes[selectedRouteIndex];
    if (!route) return {
      cumulativeKm: [] as number[],
      hills: [] as ReturnType<typeof detectHills>,
      profileArr: [] as { distance_km: number; elevation_m: number }[],
      gradientSegments: [] as { positions: [number, number][]; color: string }[],
    };

    const coords = route.coordinates;

    // Cumulative km along the coordinate array
    const cumKm: number[] = [0];
    for (let i = 1; i < coords.length; i++) {
      const R = 6371;
      const dLat = ((coords[i].lat - coords[i - 1].lat) * Math.PI) / 180;
      const dLon = ((coords[i].lon - coords[i - 1].lon) * Math.PI) / 180;
      const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((coords[i - 1].lat * Math.PI) / 180) *
          Math.cos((coords[i].lat * Math.PI) / 180) *
          Math.sin(dLon / 2) ** 2;
      cumKm.push(cumKm[cumKm.length - 1] + 2 * R * Math.asin(Math.sqrt(a)));
    }

    // Sorted profile for efficient elevation lookup
    const profile = [...(route.elevation_profile ?? [])].sort(
      (a, b) => a.distance_km - b.distance_km
    );

    // Detect hills using shared utility
    const detectedHills = detectHills(profile);

    // Build gradient-colored segments from coordinate elevation data
    const segments: { positions: [number, number][]; color: string }[] = [];
    if (coords.length > 1) {
      // Build elevation lookup from profile for each coordinate
      const eleAtCoord: number[] = [];
      for (let i = 0; i < coords.length; i++) {
        const km = cumKm[i];
        let ele = 0;
        let prevDiff = Infinity;
        for (const p of profile) {
          const diff = Math.abs(p.distance_km - km);
          if (diff > prevDiff) break;
          ele = p.elevation_m;
          prevDiff = diff;
        }
        eleAtCoord.push(ele);
      }

      // Group consecutive segments by color (batch for performance)
      let currentColor = "";
      let currentPositions: [number, number][] = [];

      for (let i = 1; i < coords.length; i++) {
        const distM = (cumKm[i] - cumKm[i - 1]) * 1000;
        const eleDiff = Math.abs(eleAtCoord[i] - eleAtCoord[i - 1]);
        const gradient = distM > 0 ? (eleDiff / distM) * 100 : 0;
        const color = gradientColor(gradient);

        if (color !== currentColor) {
          // Save previous segment batch
          if (currentPositions.length > 1) {
            segments.push({ positions: [...currentPositions], color: currentColor });
          }
          currentColor = color;
          currentPositions = [[coords[i - 1].lat, coords[i - 1].lon]];
        }
        currentPositions.push([coords[i].lat, coords[i].lon]);
      }
      // Final batch
      if (currentPositions.length > 1) {
        segments.push({ positions: currentPositions, color: currentColor });
      }
    }

    return { cumulativeKm: cumKm, hills: detectedHills, profileArr: profile, gradientSegments: segments };
  }, [routes, selectedRouteIndex]);

  // Map hill peaks to lat/lon coordinates
  const hillMarkers = useMemo(() => {
    const route = routes[selectedRouteIndex];
    if (!route || cumulativeKm.length === 0) return [];

    const coords = route.coordinates;
    return hills.map((hill) => {
      let nearestIdx = 0;
      let minDiff = Infinity;
      cumulativeKm.forEach((km, idx) => {
        const diff = Math.abs(km - hill.peakKm);
        if (diff < minDiff) {
          minDiff = diff;
          nearestIdx = idx;
        }
      });
      return {
        ...hill,
        lat: coords[nearestIdx].lat,
        lon: coords[nearestIdx].lon,
      };
    });
  }, [hills, routes, selectedRouteIndex, cumulativeKm]);

  // Compute the coordinate position for the chart hover marker
  const hoverMarkerPos = useMemo(() => {
    if (hoveredDistanceKm == null) return null;
    const route = routes[selectedRouteIndex];
    if (!route || cumulativeKm.length === 0) return null;

    const coords = route.coordinates;
    // Find the two coordinates bracketing the hovered distance
    for (let i = 1; i < cumulativeKm.length; i++) {
      if (cumulativeKm[i] >= hoveredDistanceKm) {
        const t =
          cumulativeKm[i] === cumulativeKm[i - 1]
            ? 0
            : (hoveredDistanceKm - cumulativeKm[i - 1]) /
              (cumulativeKm[i] - cumulativeKm[i - 1]);
        return {
          lat: coords[i - 1].lat + t * (coords[i].lat - coords[i - 1].lat),
          lon: coords[i - 1].lon + t * (coords[i].lon - coords[i - 1].lon),
        };
      }
    }
    // Past end — use last coordinate
    const last = coords[coords.length - 1];
    return last ? { lat: last.lat, lon: last.lon } : null;
  }, [hoveredDistanceKm, routes, selectedRouteIndex, cumulativeKm]);

  // Compute hill extent polyline for the active hill
  const hillExtentPositions = useMemo(() => {
    if (activeHillIndex == null || !hills[activeHillIndex]) return null;
    const route = routes[selectedRouteIndex];
    if (!route || cumulativeKm.length === 0) return null;

    const hill = hills[activeHillIndex];
    const coords = route.coordinates;
    const positions: [number, number][] = [];

    for (let i = 0; i < cumulativeKm.length; i++) {
      if (cumulativeKm[i] >= hill.startKm && cumulativeKm[i] <= hill.endKm) {
        positions.push([coords[i].lat, coords[i].lon]);
      }
    }
    return positions.length > 1 ? positions : null;
  }, [activeHillIndex, hills, routes, selectedRouteIndex, cumulativeKm]);

  // Compute wind arrow markers at ~5km intervals
  const windMarkers = useMemo(() => {
    if (!wind || cumulativeKm.length < 2) return [];
    const route = routes[selectedRouteIndex];
    if (!route) return [];

    const coords = route.coordinates;
    const totalKm = cumulativeKm[cumulativeKm.length - 1];
    const intervalKm = 5;
    const markers: { lat: number; lon: number; type: "head" | "cross" | "tail"; angle: number }[] = [];

    // Wind blows FROM direction_deg, so the wind vector points TO (direction_deg + 180)
    const windToRad = ((wind.direction_deg + 180) % 360) * (Math.PI / 180);

    for (let km = intervalKm; km < totalKm - 1; km += intervalKm) {
      // Find coordinate index at this km
      let idx = 0;
      for (let i = 1; i < cumulativeKm.length; i++) {
        if (cumulativeKm[i] >= km) { idx = i; break; }
      }

      // Travel bearing at this point (look ahead a few indices for stability)
      const lookAhead = Math.min(idx + 5, coords.length - 1);
      const dLat = coords[lookAhead].lat - coords[idx].lat;
      const dLon = coords[lookAhead].lon - coords[idx].lon;
      const travelRad = Math.atan2(dLon, dLat); // radians, 0=N, pi/2=E

      // Angle between wind direction and travel direction
      let angleDiff = windToRad - travelRad;
      // Normalize to [-PI, PI]
      while (angleDiff > Math.PI) angleDiff -= 2 * Math.PI;
      while (angleDiff < -Math.PI) angleDiff += 2 * Math.PI;

      const absDeg = Math.abs(angleDiff * 180 / Math.PI);
      const type: "head" | "cross" | "tail" =
        absDeg < 60 ? "tail" : absDeg > 120 ? "head" : "cross";

      markers.push({
        lat: coords[idx].lat,
        lon: coords[idx].lon,
        type,
        angle: wind.direction_deg, // CSS rotation: where wind comes FROM
      });
    }

    return markers;
  }, [wind, routes, selectedRouteIndex, cumulativeKm]);

  const handleMouseMove = useCallback((e: L.LeafletMouseEvent) => {
    const route = routes[selectedRouteIndex];
    if (!route || cumulativeKm.length === 0) return;

    const coords = route.coordinates;
    const { lat, lng } = e.latlng;

    // Find coordinate nearest to mouse (taxicab distance — fast approximation)
    let minDist = Infinity;
    let nearestIdx = 0;
    for (let i = 0; i < coords.length; i++) {
      const d = Math.abs(coords[i].lat - lat) + Math.abs(coords[i].lon - lng);
      if (d < minDist) {
        minDist = d;
        nearestIdx = i;
      }
    }

    const km = cumulativeKm[nearestIdx] ?? 0;

    // Look up elevation from sorted profile (stop when diff starts growing)
    let ele: number | null = null;
    let prevDiff = Infinity;
    for (const p of profileArr) {
      const diff = Math.abs(p.distance_km - km);
      if (diff > prevDiff) break;
      ele = p.elevation_m;
      prevDiff = diff;
    }

    setHoverTooltip({ x: e.containerPoint.x, y: e.containerPoint.y, km, ele });
    onRouteHover?.(km);
  }, [routes, selectedRouteIndex, cumulativeKm, profileArr, onRouteHover]);

  const handleMouseOut = useCallback(() => {
    setHoverTooltip(null);
    onRouteHover?.(null);
  }, [onRouteHover]);

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={AARHUS_CENTER}
        zoom={12}
        className="w-full h-full"
        zoomControl={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapClickHandler onMapClick={onMapClick} />
        <FitBounds routes={routes} selectedIndex={selectedRouteIndex} />

        {/* Inspiration route overlays */}
        {inspirationRoutes
          ?.filter((ir) => selectedInspirationFilenames?.has(ir.filename))
          .map((ir) => (
            <Polyline
              key={`insp-${ir.filename}`}
              positions={ir.coordinates.map((c) => [c[0], c[1]] as [number, number])}
              pathOptions={{
                color: "#a855f7",
                weight: 3,
                opacity: 0.55,
                dashArray: "8 6",
              }}
            >
              <Tooltip sticky>{ir.name}</Tooltip>
            </Polyline>
          ))}

        {/* Render non-selected routes first (behind) */}
        {routes.map((route, i) => {
          if (i === selectedRouteIndex) return null;
          const positions = route.coordinates.map(
            (c) => [c.lat, c.lon] as [number, number]
          );
          return (
            <Polyline
              key={route.id}
              positions={positions}
              pathOptions={{
                color: ROUTE_COLORS[i % ROUTE_COLORS.length],
                weight: 3,
                opacity: 0.35,
              }}
              eventHandlers={{ click: () => onSelectRoute(i) }}
            />
          );
        })}

        {/* Selected route — gradient-colored segments */}
        {gradientSegments.map((seg, i) => (
          <Polyline
            key={`grad-${i}`}
            positions={seg.positions}
            pathOptions={{
              color: seg.color,
              weight: 5,
              opacity: 0.9,
            }}
            eventHandlers={
              i === 0
                ? { mousemove: handleMouseMove, mouseout: handleMouseOut }
                : undefined
            }
          />
        ))}

        {/* Invisible wide polyline on top for mouse events across all segments */}
        {routes[selectedRouteIndex] && (
          <Polyline
            positions={routes[selectedRouteIndex].coordinates.map(
              (c) => [c.lat, c.lon] as [number, number]
            )}
            pathOptions={{
              color: "transparent",
              weight: 20,
              opacity: 0,
            }}
            eventHandlers={{
              mousemove: handleMouseMove,
              mouseout: handleMouseOut,
            }}
          />
        )}

        {/* Hill extent highlight overlay */}
        {hillExtentPositions && (
          <Polyline
            positions={hillExtentPositions}
            pathOptions={{
              color: "#f97316",
              weight: 8,
              opacity: 0.6,
            }}
          />
        )}

        {/* Hill peak markers on selected route */}
        {hillMarkers.map((hill, i) => {
          const isActive = activeHillIndex === i;
          return (
            <CircleMarker
              key={i}
              center={[hill.lat, hill.lon] as [number, number]}
              radius={isActive ? 10 : 7}
              pathOptions={{
                color: "white",
                fillColor: isActive ? "#ea580c" : "#f97316",
                fillOpacity: 1,
                weight: isActive ? 3 : 2,
              }}
              eventHandlers={{
                click: () => onActiveHillChange?.(isActive ? null : i),
              }}
            >
              <Tooltip sticky={!isActive} permanent={isActive}>
                <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.4 }}>
                  <div>{hill.peakElevation.toFixed(0)} m &nbsp;·&nbsp; {hill.peakKm.toFixed(1)} km</div>
                  <div style={{ fontSize: 11, fontWeight: 400, color: "#666" }}>
                    ↑{hill.gainM}m gain &nbsp;·&nbsp; {hill.lengthKm.toFixed(1)} km long &nbsp;·&nbsp; {hill.avgGradientPercent}% avg
                  </div>
                </div>
              </Tooltip>
            </CircleMarker>
          );
        })}

        {/* Wind direction arrows along route */}
        {windMarkers.map((wm, i) => {
          const color = wm.type === "tail" ? "#22c55e" : wm.type === "cross" ? "#eab308" : "#ef4444";
          const icon = new L.DivIcon({
            html: `<div style="
              font-size: 18px;
              color: ${color};
              text-shadow: 0 0 3px rgba(0,0,0,0.8);
              transform: rotate(${wm.angle}deg);
              line-height: 1;
              text-align: center;
              width: 20px;
              height: 20px;
            ">↓</div>`,
            iconSize: [20, 20],
            iconAnchor: [10, 10],
            className: "",
          });
          return (
            <Marker
              key={`wind-${i}`}
              position={[wm.lat, wm.lon]}
              icon={icon}
              interactive={false}
            />
          );
        })}

        {/* Chart hover position marker */}
        {hoverMarkerPos && (
          <CircleMarker
            center={[hoverMarkerPos.lat, hoverMarkerPos.lon] as [number, number]}
            radius={6}
            pathOptions={{
              color: "white",
              fillColor: ROUTE_COLORS[selectedRouteIndex % ROUTE_COLORS.length],
              fillOpacity: 1,
              weight: 2.5,
            }}
          />
        )}

        {/* Start marker */}
        {startLocation && (
          <Marker
            position={[startLocation.lat, startLocation.lon]}
            icon={startIcon}
          />
        )}
      </MapContainer>

      {/* Hover tooltip overlay — rendered outside MapContainer so it's above all map layers */}
      {hoverTooltip && (
        <div
          className="absolute z-[2000] pointer-events-none select-none
            bg-gray-900/95 border border-white/10 rounded-lg px-2.5 py-1.5 shadow-lg"
          style={{ left: hoverTooltip.x + 14, top: hoverTooltip.y - 52 }}
        >
          <div className="text-sm font-semibold text-white leading-tight">
            {hoverTooltip.km.toFixed(1)} km
          </div>
          {hoverTooltip.ele !== null && (
            <div className="text-xs text-gray-400">{hoverTooltip.ele.toFixed(0)} m elev.</div>
          )}
        </div>
      )}
    </div>
  );
}
