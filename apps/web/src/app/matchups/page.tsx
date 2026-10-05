"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Plus } from "lucide-react";
import Link from "next/link";

import { LeagueErrors } from "@/components/league-errors";
import { PageHeader } from "@/components/page-header";
import { CardSkeletons, QueryError } from "@/components/query-state";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { formatPoints } from "@/lib/format";
import type { MatchupCard } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<string, string> = { preevent: "Upcoming", midevent: "In progress", postevent: "Final" };

function Score({ name, owner, score, projected, leading }: {
  name: string;
  owner?: string | null;
  score: number | null;
  projected?: number | null;
  leading: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div className={cn("truncate font-semibold", leading && "font-bold")}>{name}</div>
        {owner && <div className="truncate text-xs text-muted-foreground">{owner}</div>}
      </div>
      <div className="shrink-0 text-right">
        <div className={cn("font-mono text-xl tabular-nums", leading && "font-bold")}>{formatPoints(score)}</div>
        {projected != null && <div className="text-xs text-muted-foreground">proj {projected.toFixed(1)}</div>}
      </div>
    </div>
  );
}

function Matchup({ m }: { m: MatchupCard }) {
  const mine = m.my_team.score ?? 0;
  const theirs = m.opponent?.score ?? 0;
  const body = (
    <Card className="gap-3 px-4 py-4" data-testid="matchup-card">
      <div className="flex items-center justify-between gap-2">
        <div className="truncate text-sm font-medium text-muted-foreground">{m.league_name}</div>
        <div className="flex shrink-0 items-center gap-2">
          {m.has_matchup ? (
            <Badge variant="secondary">{STATUS_LABEL[m.status ?? ""] ?? `Week ${m.week}`}</Badge>
          ) : (
            <Badge variant="outline">Custom team</Badge>
          )}
          {m.id && <ChevronRight className="size-4 text-muted-foreground" aria-hidden />}
        </div>
      </div>
      <Score name={m.my_team.name} owner="You" score={m.my_team.score} projected={m.my_team.projected} leading={m.has_matchup && mine > theirs} />
      {m.opponent ? (
        <Score
          name={m.opponent.name}
          owner={m.opponent.owner_name}
          score={m.opponent.score}
          projected={m.opponent.projected}
          leading={theirs > mine}
        />
      ) : (
        <p className="text-sm text-muted-foreground">No matchup data — custom teams don&apos;t have an opponent.</p>
      )}
      {m.has_matchup && m.opponent && (
        <p className="text-xs font-medium" data-testid="matchup-margin">
          {mine === theirs ? "Tied" : mine > theirs ? `Winning by ${(mine - theirs).toFixed(2)}` : `Losing by ${(theirs - mine).toFixed(2)}`}
        </p>
      )}
    </Card>
  );
  return m.id ? (
    <Link href={`/matchups/${m.id}`} className="block rounded-xl focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none">
      {body}
    </Link>
  ) : (
    body
  );
}

export default function MatchupsPage() {
  const query = useQuery({ queryKey: ["matchups"], queryFn: () => api.matchups() });
  const data = query.data;
  const winning = data?.matchups.filter((m) => m.has_matchup && (m.my_team.score ?? 0) > (m.opponent?.score ?? 0)).length ?? 0;
  const contests = data?.matchups.filter((m) => m.has_matchup).length ?? 0;

  return (
    <>
      <PageHeader
        title="Matchups"
        subtitle={data ? (contests ? `Week ${data.week} · winning ${winning} of ${contests}` : `Week ${data.week}`) : undefined}
      />
      {query.isPending && <CardSkeletons count={2} />}
      {query.isError && <QueryError error={query.error} onRetry={() => query.refetch()} />}
      {data && (
        <div className="space-y-3">
          <LeagueErrors errors={data.league_errors} />
          {data.matchups.length === 0 && (
            <Card className="items-center px-6 py-10 text-center">
              <p className="text-muted-foreground">Add a fantasy team to see all of your matchups in one place.</p>
              <Link href="/teams/new" className={buttonVariants()}>
                <Plus aria-hidden />
                Add Fantasy Team
              </Link>
            </Card>
          )}
          {data.matchups.map((m) => (
            <Matchup key={`${m.provider}-${m.id ?? m.my_team.team_id}`} m={m} />
          ))}
        </div>
      )}
    </>
  );
}
