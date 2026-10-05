"use client";

import { useCallback, useSyncExternalStore } from "react";

import type { GameSort } from "@/lib/game-sort";

// Display preferences live in localStorage; leagues/teams/tokens live server-side.
export interface Filters {
  starters: boolean;
  bench: boolean;
  opponents: boolean;
  allGames: boolean;
  sort: GameSort;
}

/** The on/off filters (everything except the sort order). */
export type FilterToggle = Exclude<keyof Filters, "sort">;

export const DEFAULT_FILTERS: Filters = {
  starters: true,
  bench: false,
  opponents: false,
  allGames: false,
  sort: "relevance",
};
const KEY = "sundayrush:filters";
const DEFAULTS_KEY = "sundayrush:default-filters";

const listeners = new Set<() => void>();
const cache = new Map<string, { raw: string | null; value: Filters }>();

function read(key: string, fallback: Filters): Filters {
  if (typeof window === "undefined") return fallback;
  const raw = window.localStorage.getItem(key);
  if (raw === null) return fallback; // fallbacks are themselves stable (cached or constant)
  const hit = cache.get(key);
  if (hit && hit.raw === raw) return hit.value;
  let value = fallback;
  try {
    value = { ...fallback, ...JSON.parse(raw) };
  } catch {
    value = fallback;
  }
  cache.set(key, { raw, value });
  return value;
}

function write(key: string, value: Filters) {
  window.localStorage.setItem(key, JSON.stringify(value));
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

export function readDefaultFilters(): Filters {
  return read(DEFAULTS_KEY, DEFAULT_FILTERS);
}

function useStoredFilters(key: string, fallback: () => Filters) {
  const value = useSyncExternalStore(
    subscribe,
    () => read(key, fallback()),
    () => DEFAULT_FILTERS,
  );
  const set = useCallback(
    (patch: Partial<Filters>) => write(key, { ...read(key, fallback()), ...patch }),
    [key, fallback],
  );
  return [value, set] as const;
}

/** Current game-day filters. New browsers start from the user's saved defaults. */
export function useFilters() {
  return useStoredFilters(KEY, readDefaultFilters);
}

/** Defaults edited on the Settings page. */
export function useDefaultFilters() {
  return useStoredFilters(DEFAULTS_KEY, () => DEFAULT_FILTERS);
}

export function clearLocalPrefs() {
  window.localStorage.removeItem(KEY);
  window.localStorage.removeItem(DEFAULTS_KEY);
  cache.clear();
  listeners.forEach((l) => l());
}
