"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { CardSkeletons, QueryError } from "@/components/query-state";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api, ApiError } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import type { League, ManualTeam } from "@/lib/types";

function TeamPicker({ league, onDone }: { league: League; onDone: () => void }) {
  const queryClient = useQueryClient();
  const teams = useQuery({ queryKey: ["league-teams", league.id], queryFn: () => api.leagueTeams(league.id) });
  const select = useMutation({
    mutationFn: (teamId: number) => api.selectTeam(league.id, teamId),
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      onDone();
    },
  });
  if (!teams.data) return <p className="text-sm text-muted-foreground">Loading teams…</p>;
  return (
    <RadioGroup
      value={league.selected_team_id ? String(league.selected_team_id) : ""}
      onValueChange={(v) => select.mutate(Number(v))}
      aria-label={`Your team in ${league.name}`}
      disabled={select.isPending}
    >
      {teams.data.map((t) => (
        <Label key={t.id} className="flex items-center gap-2 font-normal">
          <RadioGroupItem value={String(t.id)} />
          {t.name}
          {t.owner_name && <span className="text-muted-foreground">· {t.owner_name}</span>}
        </Label>
      ))}
    </RadioGroup>
  );
}

function LeagueCard({ league }: { league: League }) {
  const queryClient = useQueryClient();
  const [picking, setPicking] = useState(!league.selected_team_id);
  const refresh = useMutation({
    mutationFn: () => api.refreshLeague(league.id),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const remove = useMutation({
    mutationFn: () => api.deleteLeague(league.id),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const authExpired = refresh.error instanceof ApiError && refresh.error.code === "PROVIDER_AUTH_EXPIRED";

  return (
    <Card className="gap-3 px-4 py-4" data-testid="league-card">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{league.provider === "yahoo" ? "Yahoo" : league.provider}</Badge>
            <h3 className="truncate font-semibold">{league.name}</h3>
          </div>
          <p className="pt-1 text-sm">
            {league.selected_team_name ? (
              <>
                Your team: <span className="font-medium">{league.selected_team_name}</span>
              </>
            ) : (
              <span className="text-amber-700 dark:text-amber-300">Pick your team to see it on game day</span>
            )}
          </p>
          <p className="text-xs text-muted-foreground">
            {league.scoring_name ?? "League scoring"} · Last synced {formatRelative(league.last_synced_at)}
          </p>
        </div>
      </div>
      {picking && <TeamPicker league={league} onDone={() => setPicking(false)} />}
      {refresh.isError && (
        <Alert variant="destructive">
          <AlertDescription>
            {refresh.error.message}
            {authExpired && (
              <a href={api.yahooConnectUrl} className={buttonVariants({ size: "sm", className: "mt-2" })}>
                Reconnect Yahoo
              </a>
            )}
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" onClick={() => refresh.mutate()} disabled={refresh.isPending}>
          <RefreshCw className={refresh.isPending ? "animate-spin" : undefined} aria-hidden />
          {refresh.isPending ? "Syncing…" : "Sync"}
        </Button>
        {league.selected_team_id && (
          <Button size="sm" variant="outline" onClick={() => setPicking((p) => !p)}>
            Change team
          </Button>
        )}
        <Button
          size="sm"
          variant="destructive"
          onClick={() => confirm(`Remove ${league.name}? You can import it again later.`) && remove.mutate()}
          disabled={remove.isPending}
        >
          <Trash2 aria-hidden />
          Remove
        </Button>
      </div>
    </Card>
  );
}

function ManualTeamCard({ team }: { team: ManualTeam }) {
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: () => api.deleteManualTeam(team.id),
    onSuccess: () => queryClient.invalidateQueries(),
  });
  return (
    <Card className="gap-2 px-4 py-4" data-testid="manual-team-card">
      <div className="flex items-center gap-2">
        <Badge variant="outline">Custom</Badge>
        <h3 className="truncate font-semibold">{team.name}</h3>
      </div>
      <p className="text-sm text-muted-foreground">
        {team.scoring_name} · {team.starters.length} starters · {team.bench.length} bench
      </p>
      <div className="flex flex-wrap gap-2">
        <Link href={`/teams/custom/${team.id}`} className={buttonVariants({ size: "sm", variant: "outline" })}>
          <Pencil aria-hidden />
          Edit
        </Link>
        <Button
          size="sm"
          variant="destructive"
          onClick={() => confirm(`Delete ${team.name}?`) && remove.mutate()}
          disabled={remove.isPending}
        >
          <Trash2 aria-hidden />
          Delete
        </Button>
      </div>
    </Card>
  );
}

export default function TeamsPage() {
  const leagues = useQuery({ queryKey: ["leagues"], queryFn: api.leagues });
  const manual = useQuery({ queryKey: ["manual-teams"], queryFn: api.manualTeams });

  return (
    <>
      <PageHeader
        title="Teams"
        action={
          <Link href="/teams/new" className={buttonVariants({ size: "sm" })}>
            <Plus aria-hidden />
            Add Team
          </Link>
        }
      />
      <div className="space-y-6">
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Connected leagues</h2>
          {leagues.isPending && <CardSkeletons count={1} />}
          {leagues.isError && <QueryError error={leagues.error} onRetry={() => leagues.refetch()} />}
          {leagues.data?.length === 0 && <p className="text-sm text-muted-foreground">No connected leagues yet.</p>}
          {leagues.data?.map((lg) => <LeagueCard key={lg.id} league={lg} />)}
        </section>
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Custom teams</h2>
          {manual.isPending && <CardSkeletons count={1} />}
          {manual.isError && <QueryError error={manual.error} onRetry={() => manual.refetch()} />}
          {manual.data?.length === 0 && <p className="text-sm text-muted-foreground">No custom teams yet.</p>}
          {manual.data?.map((t) => <ManualTeamCard key={t.id} team={t} />)}
        </section>
        <Link href="/teams/new" className={buttonVariants({ size: "lg", variant: "outline", className: "w-full" })}>
          <Plus aria-hidden />
          Add Team
        </Link>
      </div>
    </>
  );
}
