import type { GeocodeResult, InspirationRoute, RouteRequest, RouteResponse, WindInfo } from "./types";

export async function geocodeAddress(query: string): Promise<GeocodeResult> {
  const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new Error("Address not found");
  }
  return res.json();
}

export async function generateRoute(
  request: RouteRequest
): Promise<RouteResponse> {
  const res = await fetch("/api/generate-route", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Route generation failed" }));
    throw new Error(err.detail || "Route generation failed");
  }
  return res.json();
}

export function getGpxDownloadUrl(routeId: string): string {
  return `/api/route/${routeId}/gpx`;
}

export async function fetchInspirationRoutes(): Promise<InspirationRoute[]> {
  const res = await fetch("/api/inspiration/routes");
  if (!res.ok) return [];
  return res.json();
}

export async function fetchWind(lat: number, lon: number): Promise<WindInfo | null> {
  try {
    const res = await fetch(
      `https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(4)}&longitude=${lon.toFixed(4)}&current=wind_speed_10m,wind_direction_10m`
    );
    if (!res.ok) return null;
    const data = await res.json();
    return {
      speed_kmh: data.current.wind_speed_10m,
      direction_deg: data.current.wind_direction_10m,
    };
  } catch {
    return null;
  }
}
