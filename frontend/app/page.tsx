"use client";

import { useState, useCallback, useEffect } from "react";
import dynamic from "next/dynamic";
import ControlPanel from "@/components/Controls/ControlPanel";
import RouteResults from "@/components/Results/RouteResults";
import { geocodeAddress, generateRoute, fetchWind, fetchInspirationRoutes } from "@/lib/api";
import InspirationPanel from "@/components/Inspiration/InspirationPanel";
import type { InspirationRoute, RouteAlternative, WindInfo } from "@/lib/types";

const LOADING_STAGES = [
  { threshold: 0,  label: "Connecting..." },
  { threshold: 10, label: "Loading map data..." },
  { threshold: 38, label: "Planning routes..." },
  { threshold: 62, label: "Optimising paths..." },
  { threshold: 84, label: "Finishing up..." },
];

// Dynamic import for Leaflet (no SSR)
const RouteMap = dynamic(() => import("@/components/Map/RouteMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-950 flex items-center justify-center">
      <div className="text-gray-600 text-sm">Loading map...</div>
    </div>
  ),
});

export default function Home() {
  // Start location
  const [startLocation, setStartLocation] = useState<{
    lat: number;
    lon: number;
    address?: string;
  } | null>(null);

  // Controls
  const [distance, setDistance] = useState(30);
  const [direction, setDirection] = useState<string | null>("south");
  const [elevationPref, setElevationPref] = useState("rolling");
  const [includeHill, setIncludeHill] = useState(false);
  const [hillMinM, setHillMinM] = useState(50);

  // Results
  const [routes, setRoutes] = useState<RouteAlternative[]>([]);
  const [selectedRouteIndex, setSelectedRouteIndex] = useState(0);
  const [avgSpeed, setAvgSpeed] = useState(25);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hoveredDistanceKm, setHoveredDistanceKm] = useState<number | null>(null);
  const [activeHillIndex, setActiveHillIndex] = useState<number | null>(null);
  const [wind, setWind] = useState<WindInfo | null>(null);

  // Inspiration routes
  const [inspirationRoutes, setInspirationRoutes] = useState<InspirationRoute[]>([]);
  const [selectedInspirationFilenames, setSelectedInspirationFilenames] = useState<Set<string>>(new Set());
  const [inspirationOpen, setInspirationOpen] = useState(false);

  // Load inspiration routes on mount
  useEffect(() => {
    fetchInspirationRoutes().then(setInspirationRoutes);
  }, []);

  const handleToggleInspiration = useCallback((filename: string) => {
    setSelectedInspirationFilenames((prev) => {
      const next = new Set(prev);
      if (next.has(filename)) next.delete(filename);
      else next.add(filename);
      return next;
    });
  }, []);

  const handleClearInspirations = useCallback(() => {
    setSelectedInspirationFilenames(new Set());
  }, []);

  // Loading progress bar (simulated — backend has no streaming progress)
  const [loadingProgress, setLoadingProgress] = useState(0);
  const [showBar, setShowBar] = useState(false);

  useEffect(() => {
    if (isLoading) {
      setShowBar(true);
      setLoadingProgress(0);
      const start = Date.now();
      // Exponential approach toward 90%: p = 90*(1 - e^(-t/T)), T=20s
      const interval = setInterval(() => {
        const t = (Date.now() - start) / 1000;
        setLoadingProgress(Math.min(90 * (1 - Math.exp(-t / 20)), 90));
      }, 150);
      return () => clearInterval(interval);
    } else {
      // Snap to 100%, then hide bar after brief pause
      setLoadingProgress(100);
      const t = setTimeout(() => {
        setShowBar(false);
        setLoadingProgress(0);
      }, 500);
      return () => clearTimeout(t);
    }
  }, [isLoading]);

  const loadingStage = isLoading
    ? [...LOADING_STAGES].reverse().find(s => loadingProgress >= s.threshold)?.label ?? "Connecting..."
    : "";

  const handleMapClick = useCallback((lat: number, lon: number) => {
    setStartLocation({ lat, lon });
    setError(null);
  }, []);

  const handleAddressSearch = useCallback(async (query: string) => {
    try {
      setError(null);
      const result = await geocodeAddress(query);
      setStartLocation({
        lat: result.lat,
        lon: result.lon,
        address: result.display_name,
      });
    } catch {
      setError("Address not found");
    }
  }, []);

  const handleGenerate = useCallback(async () => {
    if (!startLocation) return;

    setIsLoading(true);
    setError(null);
    setRoutes([]);

    try {
      // Fetch routes and wind data in parallel
      const [response, windData] = await Promise.all([
        generateRoute({
          start_lat: startLocation.lat,
          start_lon: startLocation.lon,
          distance_km: distance,
          direction,
          elevation_preference: elevationPref,
          include_hill_min_m: includeHill ? hillMinM : null,
          num_alternatives: 3,
        }),
        fetchWind(startLocation.lat, startLocation.lon),
      ]);
      setRoutes(response.routes);
      setSelectedRouteIndex(0);
      setWind(windData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Route generation failed");
    } finally {
      setIsLoading(false);
    }
  }, [startLocation, distance, direction, elevationPref, includeHill, hillMinM]);

  return (
    <div className="w-screen h-screen relative">
      {/* Top loading bar */}
      {showBar && (
        <div className="absolute top-0 left-0 right-0 z-[2000] h-[3px] bg-white/5">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 shadow-[0_0_8px_rgba(59,130,246,0.8)] transition-all duration-300 ease-out"
            style={{ width: `${loadingProgress}%` }}
          />
        </div>
      )}

      {/* Full-screen map */}
      <RouteMap
        routes={routes}
        selectedRouteIndex={selectedRouteIndex}
        startLocation={startLocation}
        onMapClick={handleMapClick}
        onSelectRoute={setSelectedRouteIndex}
        hoveredDistanceKm={hoveredDistanceKm}
        onRouteHover={setHoveredDistanceKm}
        activeHillIndex={activeHillIndex}
        onActiveHillChange={setActiveHillIndex}
        wind={wind}
        inspirationRoutes={inspirationRoutes}
        selectedInspirationFilenames={selectedInspirationFilenames}
      />

      {/* Control panel */}
      <ControlPanel
        startAddress={startLocation?.address || ""}
        onAddressSearch={handleAddressSearch}
        distance={distance}
        onDistanceChange={setDistance}
        direction={direction}
        onDirectionChange={setDirection}
        elevationPref={elevationPref}
        onElevationPrefChange={setElevationPref}
        includeHill={includeHill}
        onIncludeHillChange={setIncludeHill}
        hillMinM={hillMinM}
        onHillMinMChange={setHillMinM}
        onGenerate={handleGenerate}
        isLoading={isLoading}
        loadingStage={loadingStage}
        loadingProgress={loadingProgress}
        hasStart={!!startLocation}
      />

      {/* Error toast */}
      {error && (
        <div className="absolute top-4 right-4 z-[1000] bg-red-500/90 backdrop-blur-sm text-white text-sm px-4 py-2 rounded-lg shadow-lg">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-3 text-white/70 hover:text-white"
          >
            ×
          </button>
        </div>
      )}

      {/* Inspiration route browser */}
      <InspirationPanel
        routes={inspirationRoutes}
        selectedFilenames={selectedInspirationFilenames}
        onToggleRoute={handleToggleInspiration}
        onClearAll={handleClearInspirations}
        isOpen={inspirationOpen}
        onToggleOpen={() => setInspirationOpen(!inspirationOpen)}
      />

      {/* Route results */}
      <RouteResults
        routes={routes}
        selectedIndex={selectedRouteIndex}
        onSelectRoute={setSelectedRouteIndex}
        avgSpeed={avgSpeed}
        onAvgSpeedChange={setAvgSpeed}
        hoveredDistanceKm={hoveredDistanceKm}
        onChartHover={setHoveredDistanceKm}
        activeHillIndex={activeHillIndex}
        onPeakClick={setActiveHillIndex}
        wind={wind}
      />
    </div>
  );
}
