"use client";

import { useState, useMemo } from "react";
import type { InspirationRoute } from "@/lib/types";

interface InspirationPanelProps {
  routes: InspirationRoute[];
  selectedFilenames: Set<string>;
  onToggleRoute: (filename: string) => void;
  onClearAll: () => void;
  isOpen: boolean;
  onToggleOpen: () => void;
}

export default function InspirationPanel({
  routes,
  selectedFilenames,
  onToggleRoute,
  onClearAll,
  isOpen,
  onToggleOpen,
}: InspirationPanelProps) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return routes;
    const q = search.toLowerCase();
    return routes.filter((r) => r.name.toLowerCase().includes(q));
  }, [routes, search]);

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={onToggleOpen}
        className={`absolute top-4 right-4 z-[1000] px-3 py-2 rounded-lg backdrop-blur-xl border text-sm font-medium transition-all ${
          isOpen
            ? "bg-purple-500/20 border-purple-400/30 text-purple-300"
            : selectedFilenames.size > 0
              ? "bg-purple-500/20 border-purple-400/30 text-purple-300"
              : "bg-gray-900/85 border-white/10 text-gray-400 hover:text-white"
        }`}
      >
        Inspiration
        {selectedFilenames.size > 0 && (
          <span className="ml-1.5 px-1.5 py-0.5 rounded-full bg-purple-500/30 text-purple-200 text-xs">
            {selectedFilenames.size}
          </span>
        )}
      </button>

      {/* Panel */}
      {isOpen && (
        <div className="absolute top-14 right-4 z-[1000] w-80 max-h-[70vh] rounded-xl bg-gray-900/90 backdrop-blur-xl border border-white/10 overflow-hidden flex flex-col">
          {/* Header */}
          <div className="p-3 border-b border-white/5">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">
                Inspiration Routes ({routes.length})
              </span>
              {selectedFilenames.size > 0 && (
                <button
                  onClick={onClearAll}
                  className="text-xs text-gray-500 hover:text-gray-300 transition"
                >
                  Clear all
                </button>
              )}
            </div>
            <input
              type="text"
              placeholder="Search routes..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-gray-500 outline-none focus:border-purple-400/30"
            />
          </div>

          {/* Route list */}
          <div className="overflow-y-auto flex-1 p-1.5">
            {filtered.map((route) => {
              const selected = selectedFilenames.has(route.filename);
              return (
                <button
                  key={route.filename}
                  onClick={() => onToggleRoute(route.filename)}
                  className={`w-full text-left px-3 py-2 rounded-lg mb-0.5 transition-all ${
                    selected
                      ? "bg-purple-500/15 border border-purple-400/20"
                      : "hover:bg-white/5 border border-transparent"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded-sm border-2 flex items-center justify-center transition ${
                        selected
                          ? "bg-purple-500 border-purple-500"
                          : "border-gray-600"
                      }`}
                    >
                      {selected && (
                        <svg className="w-2 h-2 text-white" fill="currentColor" viewBox="0 0 12 12">
                          <path d="M10 3L4.5 8.5 2 6" stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className={`text-sm truncate ${selected ? "text-purple-200" : "text-gray-300"}`}>
                        {route.name}
                      </div>
                      <div className="text-xs text-gray-600">
                        {route.point_count} points
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
            {filtered.length === 0 && (
              <div className="text-center text-gray-600 text-sm py-4">
                No routes found
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
