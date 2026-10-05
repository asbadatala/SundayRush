"use client";

import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Player } from "@/lib/types";

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}

export function PlayerSearch({
  onAdd,
  excludeIds,
}: {
  onAdd: (player: Player, slot: "starter" | "bench") => void;
  excludeIds: Set<number>;
}) {
  const [q, setQ] = useState("");
  const term = useDebounced(q.trim(), 250);
  const query = useQuery({
    queryKey: ["player-search", term],
    queryFn: ({ signal }) => api.searchPlayers(term, signal),
    enabled: term.length >= 2,
    staleTime: 5 * 60_000,
  });
  const results = (query.data ?? []).filter((p) => !excludeIds.has(p.id));

  return (
    <div className="space-y-2">
      <label htmlFor="player-search" className="text-sm font-medium">
        Search NFL players
      </label>
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <Input
          id="player-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. Josh Allen, Bills"
          className="pl-8"
          autoComplete="off"
        />
      </div>
      {term.length >= 2 && (
        <ul className="divide-y rounded-lg border" aria-label="Search results" data-testid="search-results">
          {query.isFetching && !query.data && <li className="p-3 text-sm text-muted-foreground">Searching…</li>}
          {query.isError && <li className="p-3 text-sm text-destructive">{query.error.message}</li>}
          {query.data && results.length === 0 && (
            <li className="p-3 text-sm text-muted-foreground">No players match &ldquo;{term}&rdquo;.</li>
          )}
          {results.map((p) => (
            <li key={p.id} className="flex items-center gap-2 p-2">
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{p.full_name}</div>
                <div className="text-xs text-muted-foreground">
                  {p.position} · {p.nfl_team ?? "FA"}
                  {p.injury_status ? ` · ${p.injury_status}` : ""}
                </div>
              </div>
              <Button size="sm" onClick={() => onAdd(p, "starter")} aria-label={`Add ${p.full_name} as starter`}>
                Starter
              </Button>
              <Button size="sm" variant="outline" onClick={() => onAdd(p, "bench")} aria-label={`Add ${p.full_name} to bench`}>
                Bench
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
