export interface Coordinate {
  lat: number;
  lon: number;
  ele?: number | null;
}

export interface ElevationPoint {
  distance_km: number;
  elevation_m: number;
}

export interface HillInfo {
  peakIndex: number;
  peakKm: number;
  peakElevation: number;
  startKm: number;
  endKm: number;
  lengthKm: number;
  gainM: number;
  avgGradientPercent: number;
}

export interface RouteAlternative {
  id: string;
  distance_km: number;
  elevation_gain_m: number;
  elevation_loss_m: number;
  estimated_duration_min: number;
  quality_score: number;
  road_breakdown: Record<string, number>;
  coordinates: Coordinate[];
  elevation_profile: ElevationPoint[];
}

export interface RouteResponse {
  routes: RouteAlternative[];
}

export interface GeocodeResult {
  lat: number;
  lon: number;
  display_name: string;
}

export interface WindInfo {
  speed_kmh: number;
  direction_deg: number; // meteorological: 0=N, 90=E, 180=S, 270=W (direction wind comes FROM)
}

export interface InspirationRoute {
  filename: string;
  name: string;
  point_count: number;
  coordinates: [number, number][]; // [lat, lon]
}

export interface RouteRequest {
  start_lat: number;
  start_lon: number;
  distance_km: number;
  direction?: string | null;
  elevation_preference?: string | null;
  include_hill_min_m?: number | null;
  num_alternatives?: number;
}
