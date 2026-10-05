"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CloudOff, Plus, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { FilterChips } from "@/components/filter-chips";
import { GameCard } from "@/components/game-card";
import { GameSortPicker } from "@/components/game-sort-picker";
import { LeagueErrors } from "@/components/league-errors";
import { PageHeader } from "@/components/page-header";
import { PlayerRow } from "@/components/player-row";
import { CardSkeletons, QueryError } from "@/components/query-state";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { sortGames } from "@/lib/game-sort";
import { useFilters } from "@/lib/prefs";
import type { GameDay, PlayerGroups } from "@/lib/types";

function EmptyState() {
  return (
    <Card className="items-center px-6 py-12 text-center" data-testid="empty-state">
      <h2 className="text-xl font-bold">Every NFL game that matters to you</h2>
      <p className="max-w-sm text-muted-foreground">
        Connect your fantasy teams and see every NFL game that matters to you in one place.
      </p>
      <Link href="/teams/new" className={buttonVariants({ size: "lg" })}>
        <Plus aria-hidden />
        Add Fantasy Team
      </Link>
    </Card>
  );
}

function pick(groups: PlayerGroups, f: { starters: boolean; bench: boolean; opponents: boolean }) {
  return {
    starters: f.starters ? groups.my_starters : [],
    bench: f.bench ? groups.my_bench : [],
    opponents: f.opponents ? groups.opponents : [],
  };
}

function StaleNotice({ data }: { data: GameDay }) {
  if (!data.live_data_available) {
    return (
      <p className="flex items-center gap-1 text-sm text-amber-700 dark:text-amber-300" data-testid="stale-notice">
        <CloudOff className="size-4" aria-hidden />
        Live data unavailable{data.stats_as_of ? ` — stats as of ${formatTime(data.stats_as_of)}` : ""}
      </p>
    );
  }
  return data.stats_as_of ? <span>Stats as of {formatTime(data.stats_as_of)}</span> : null;
}

export default function GamesPage() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useFilters();
  const [refreshing, setRefreshing] = useState(false);

  const query = useQuery({
    queryKey: ["game-day"],
    queryFn: () => api.gameDay(),
    // Poll only while a game is live; otherwise data is refreshed on focus/explicit refresh.
    refetchInterval: (q) => (q.state.data?.any_live ? 60_000 : false),
  });

  async function refresh() {
    setRefreshing(true);
    try {
      queryClient.setQueryData(["game-day"], await api.gameDay({ refresh: true }));
    } catch {
      await query.refetch();
    } finally {
      setRefreshing(false);
    }
  }

  const data = query.data;
  const visible = sortGames(
    data?.games
      .map((g) => ({ group: g, ...pick(g, filters) }))
      .filter((g) => filters.allGames || g.starters.length || g.bench.length || g.opponents.length) ?? [],
    filters.sort,
  );
  const noGame = data ? pick(data.no_game, filters) : null;
  const noGameRows = noGame ? [...noGame.starters, ...noGame.bench, ...noGame.opponents] : [];

  return (
    <>
      <PageHeader
        title={data ? `Week ${data.week}` : "Games"}
        subtitle={data ? <StaleNotice data={data} /> : "Your NFL Sunday, in one place"}
        action={
          data?.has_teams && (
            <Button variant="outline" size="sm" onClick={refresh} disabled={refreshing} aria-label="Refresh">
              <RefreshCw className={refreshing ? "animate-spin" : undefined} aria-hidden />
              Refresh
            </Button>
          )
        }
      />

      {query.isPending && <CardSkeletons />}
      {query.isError && <QueryError error={query.error} onRetry={() => query.refetch()} />}

      {data && !data.has_teams && (
        <div className="space-y-3">
          <LeagueErrors errors={data.league_errors} />
          <EmptyState />
        </div>
      )}

      {data?.has_teams && (
        <div className="space-y-4">
          <FilterChips filters={filters} onChange={setFilters} />
          <GameSortPicker value={filters.sort} onChange={(sort) => setFilters({ sort })} />
          <LeagueErrors errors={data.league_errors} />
          {visible.length === 0 && (
            <Card className="px-6 py-8 text-center text-muted-foreground">
              No games match these filters. Turn on <strong>All NFL games</strong> to see the full schedule.
            </Card>
          )}
          {visible.map(({ group, starters, bench, opponents }) => (
            <GameCard key={group.game.id} group={group} starters={starters} bench={bench} opponents={opponents} />
          ))}
          {noGameRows.length > 0 && (
            <Card className="gap-0 px-4 py-3" data-testid="no-game-group">
              <h2 className="text-sm font-semibold">Bye week, free agent, or unmatched</h2>
              <ul className="divide-y">
                {noGameRows.map((r) => (
                  <PlayerRow key={r.key} row={r} />
                ))}
              </ul>
            </Card>
          )}
        </div>
      )}
    </>
  );
}
