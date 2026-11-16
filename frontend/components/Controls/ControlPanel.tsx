"use client";

import { useState, useCallback } from "react";
import CompassRose from "./CompassRose";

interface ControlPanelProps {
  startAddress: string;
  onAddressSearch: (query: string) => void;
  distance: number;
  onDistanceChange: (km: number) => void;
  direction: string | null;
  onDirectionChange: (dir: string | null) => void;
  elevationPref: string;
  onElevationPrefChange: (pref: string) => void;
  includeHill: boolean;
  onIncludeHillChange: (v: boolean) => void;
  hillMinM: number;
  onHillMinMChange: (m: number) => void;
  onGenerate: () => void;
  isLoading: boolean;
  loadingStage: string;
  loadingProgress: number;
  hasStart: boolean;
}

export default function ControlPanel({
  startAddress,
  onAddressSearch,
  distance,
  onDistanceChange,
  direction,
  onDirectionChange,
  elevationPref,
  onElevationPrefChange,
  includeHill,
  onIncludeHillChange,
  hillMinM,
  onHillMinMChange,
  onGenerate,
  isLoading,
  loadingStage,
  loadingProgress,
  hasStart,
}: ControlPanelProps) {
  const [addressInput, setAddressInput] = useState(startAddress);

  const handleAddressSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      if (addressInput.trim()) {
        onAddressSearch(addressInput.trim());
      }
    },
    [addressInput, onAddressSearch]
  );

  return (
    <div className="absolute top-4 left-4 z-[1000] w-80 max-h-[calc(100vh-2rem)] overflow-y-auto rounded-2xl bg-gray-900/80 backdrop-blur-xl border border-white/10 shadow-2xl">
      {/* Header */}
      <div className="px-5 pt-4 pb-3 border-b border-white/5">
        <h1 className="text-lg font-semibold tracking-tight">RouteFinder</h1>
        <p className="text-xs text-gray-500 mt-0.5">Scenic cycling routes</p>
      </div>

      <div className="p-5 space-y-5">
        {/* Address Search */}
        <div>
          <label className="text-xs text-gray-400 uppercase tracking-wider block mb-1.5">
            Start Point
          </label>
          <form onSubmit={handleAddressSubmit}>
            <div className="relative">
              <input
                type="text"
                value={addressInput}
                onChange={(e) => setAddressInput(e.target.value)}
                placeholder="Search address..."
                className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/25 transition"
              />
              <button
                type="submit"
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white transition"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="11" cy="11" r="8" />
                  <path d="m21 21-4.35-4.35" />
                </svg>
              </button>
            </div>
          </form>
          <p className="text-[10px] text-gray-600 mt-1">or click the map</p>
        </div>

        {/* Distance Slider */}
        <div>
          <div className="flex justify-between items-center mb-1.5">
            <label className="text-xs text-gray-400 uppercase tracking-wider">
              Distance
            </label>
            <span className="text-sm font-medium text-blue-400">{distance} km</span>
          </div>
          <input
            type="range"
            min={10}
            max={100}
            step={5}
            value={distance}
            onChange={(e) => onDistanceChange(Number(e.target.value))}
            className="w-full h-1.5 bg-white/10 rounded-full appearance-none cursor-pointer accent-blue-500
              [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:shadow-lg"
          />
          <div className="flex justify-between text-[10px] text-gray-600 mt-0.5">
            <span>10</span>
            <span>100 km</span>
          </div>
        </div>

        {/* Compass Rose */}
        <CompassRose selected={direction} onSelect={onDirectionChange} />

        {/* Elevation Preference */}
        <div>
          <label className="text-xs text-gray-400 uppercase tracking-wider block mb-1.5">
            Elevation
          </label>
          <div className="grid grid-cols-3 gap-1">
            {["flat", "rolling", "hilly"].map((pref) => (
              <button
                key={pref}
                onClick={() => onElevationPrefChange(pref)}
                className={`py-1.5 rounded-lg text-xs font-medium transition-all ${
                  elevationPref === pref
                    ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                    : "bg-white/5 text-gray-400 border border-white/5 hover:bg-white/10"
                }`}
              >
                {pref.charAt(0).toUpperCase() + pref.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* Hill Selector */}
        <div>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeHill}
              onChange={(e) => onIncludeHillChange(e.target.checked)}
              className="rounded border-white/20 bg-white/5 text-blue-500 focus:ring-blue-500/25"
            />
            <span className="text-xs text-gray-300">Include one hill</span>
          </label>
          {includeHill && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-gray-500">min</span>
              <input
                type="number"
                value={hillMinM}
                onChange={(e) => onHillMinMChange(Number(e.target.value))}
                min={20}
                max={500}
                step={10}
                className="w-20 bg-white/5 border border-white/10 rounded-md px-2 py-1 text-sm text-white focus:outline-none focus:border-blue-500/50"
              />
              <span className="text-xs text-gray-500">m gain</span>
            </div>
          )}
        </div>

        {/* Generate Button */}
        <div className="space-y-2">
          <button
            onClick={onGenerate}
            disabled={isLoading || !hasStart}
            className="w-full py-2.5 rounded-xl font-medium text-sm transition-all
              bg-blue-600 hover:bg-blue-500 text-white shadow-lg shadow-blue-500/20
              disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none
              active:scale-[0.98]"
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin h-4 w-4 shrink-0" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                {loadingStage || "Generating..."}
              </span>
            ) : (
              "Generate Route"
            )}
          </button>

          {/* Progress bar — visible while loading */}
          {isLoading && (
            <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-300 ease-out"
                style={{ width: `${loadingProgress}%` }}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
