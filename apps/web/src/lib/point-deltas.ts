"use client";

import { useState } from "react";

import type { GameDay } from "@/lib/types";

const NONE: ReadonlyMap<string, number> = new Map();

function pointsByKey(data: GameDay): Map<string, number> {
  const out = new Map<string, number>();
  for (const g of [...data.games, data.no_game]) {
    for (const r of [...g.my_starters, ...g.my_bench, ...g.opponents]) if (r.points !== null) out.set(r.key, r.points);
  }
  return out;
}

/**
 * Points each row gained since the previous game-day payload (live polling or manual refresh),
 * keyed by PlayerRow.key. Empty on first load.
 */
export function usePointDeltas(data: GameDay | undefined): ReadonlyMap<string, number> {
  const [snap, setSnap] = useState<{ data?: GameDay; deltas: ReadonlyMap<string, number> }>({ deltas: NONE });
  if (data !== snap.data) {
    let deltas = NONE;
    if (snap.data && data) {
      const before = pointsByKey(snap.data);
      const gained = new Map<string, number>();
      for (const [key, pts] of pointsByKey(data)) {
        const prev = before.get(key);
        if (prev !== undefined && pts - prev >= 0.05) gained.set(key, pts - prev);
      }
      deltas = gained;
    }
    // Adjusting state while rendering, per React's "storing information from previous renders".
    setSnap({ data, deltas });
  }
  return data === snap.data ? snap.deltas : NONE;
}
