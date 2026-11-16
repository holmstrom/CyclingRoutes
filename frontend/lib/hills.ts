import type { ElevationPoint, HillInfo } from "./types";

/**
 * Detect significant hills in an elevation profile.
 *
 * For each peak, walks left/right to find the valley floor, then computes
 * hill length, elevation gain from ground, and average gradient.
 */
export function detectHills(profile: ElevationPoint[]): HillInfo[] {
  if (profile.length < 5) return [];

  const results: HillInfo[] = [];
  const wSz = Math.max(3, Math.floor(profile.length / 12));

  for (let i = wSz; i < profile.length - wSz; i++) {
    const curr = profile[i].elevation_m;

    // Must be local maximum within the window
    let isMax = true;
    for (let j = i - wSz; j <= i + wSz; j++) {
      if (j !== i && profile[j] && profile[j].elevation_m > curr) {
        isMax = false;
        break;
      }
    }
    if (!isMax) continue;

    // Find valley floor to the left
    let leftIdx = i;
    for (let j = i - 1; j >= 0; j--) {
      if (profile[j].elevation_m <= profile[leftIdx].elevation_m) {
        leftIdx = j;
      } else {
        break; // elevation rising again = past the valley
      }
    }

    // Find valley floor to the right
    let rightIdx = i;
    for (let j = i + 1; j < profile.length; j++) {
      if (profile[j].elevation_m <= profile[rightIdx].elevation_m) {
        rightIdx = j;
      } else {
        break;
      }
    }

    const valleyElev = Math.min(
      profile[leftIdx].elevation_m,
      profile[rightIdx].elevation_m
    );
    const gain = curr - valleyElev;

    // Require at least 10m gain
    if (gain < 10) continue;

    const startKm = profile[leftIdx].distance_km;
    const endKm = profile[rightIdx].distance_km;
    const lengthKm = endKm - startKm;

    // Average gradient: gain / horizontal distance * 100
    // Use half the hill length (climb side) for a more meaningful gradient
    const climbDistKm = profile[i].distance_km - startKm;
    const avgGradient = climbDistKm > 0 ? (gain / (climbDistKm * 1000)) * 100 : 0;

    results.push({
      peakIndex: i,
      peakKm: profile[i].distance_km,
      peakElevation: curr,
      startKm,
      endKm,
      lengthKm: Math.round(lengthKm * 100) / 100,
      gainM: Math.round(gain),
      avgGradientPercent: Math.round(avgGradient * 10) / 10,
    });
  }

  return results;
}
