"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { PlayerRow } from "@/components/player-row";
import { CardSkeletons, QueryError } from "@/components/query-state";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatPoints } from "@/lib/format";
import type { MatchupSide, PlayerRow as Row } from "@/lib/types";

function Lineup({ side, rows, label }: { side: MatchupSide | null; rows: Row[]; label: string }) {
  return (
    <Card className="gap-0 px-4 py-3" data-testid={`lineup-${label}`}>
      <div className="flex items-baseline justify-between gap-2 border-b pb-2">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
          <h2 className="truncate text-lg font-bold">{side?.name ?? "—"}</h2>
        </div>
        <div className="font-heading text-3xl font-semibold tabular-nums">{formatPoints(side?.score ?? null)}</div>
      </div>
      {rows.length ? (
        <ul className="divide-y">
          {rows.map((r) => (
            <PlayerRow key={r.key} row={r} showOwnership={false} />
          ))}
        </ul>
      ) : (
        <p className="py-3 text-sm text-muted-foreground">Starting lineup isn&apos;t available yet.</p>
      )}
    </Card>
  );
}

export default function MatchupDetailPage() {
  const { id } = useParams<{ id: string }>();
  const query = useQuery({ queryKey: ["matchup", id], queryFn: () => api.matchup(Number(id)) });
  const data = query.data;

  return (
    <>
      <PageHeader
        back="/matchups"
        title={data?.card.league_name ?? "Matchup"}
        subtitle={data ? `Week ${data.card.week} · totals reported by ${data.card.provider === "yahoo" ? "Yahoo" : data.card.provider}` : undefined}
      />
      {query.isPending && <CardSkeletons count={2} />}
      {query.isError && <QueryError error={query.error} onRetry={() => query.refetch()} />}
      {data && (
        <div className="grid gap-3 md:grid-cols-2">
          <Lineup label="You" side={data.card.my_team} rows={data.my_starters} />
          <Lineup label="Opponent" side={data.card.opponent} rows={data.opponent_starters} />
        </div>
      )}
    </>
  );
}
