"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useRouter } from "next/navigation";
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
import type { ImportedLeague } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Step 1: pick leagues. Step 2: confirm the pre-selected team in each. */
export default function YahooSelectPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [imported, setImported] = useState<ImportedLeague[] | null>(null);
  const [teamByLeague, setTeamByLeague] = useState<Record<number, number>>({});

  const discover = useQuery({ queryKey: ["yahoo-discover"], queryFn: api.yahooDiscover, staleTime: 5 * 60_000 });

  const importMutation = useMutation({
    mutationFn: () => api.importLeagues([...chosen]),
    onSuccess: (result) => {
      setImported(result);
      setTeamByLeague(
        Object.fromEntries(
          result.filter((r) => r.suggested_team_id).map((r) => [r.league.id, r.suggested_team_id as number]),
        ),
      );
    },
  });

  const confirm = useMutation({
    mutationFn: async () => {
      for (const r of imported ?? []) {
        const teamId = teamByLeague[r.league.id];
        if (teamId) await api.selectTeam(r.league.id, teamId);
      }
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.push("/");
    },
  });

  const authError = discover.error instanceof ApiError && discover.error.code.startsWith("PROVIDER_AUTH");

  if (imported) {
    const allPicked = imported.every((r) => teamByLeague[r.league.id]);
    return (
      <>
        <PageHeader title="Confirm your teams" subtitle="We pre-selected the team Yahoo says is yours." />
        <div className="space-y-3">
          {imported.map((r) => (
            <Card key={r.league.id} className="gap-3 px-4 py-4" data-testid="confirm-league">
              <h2 className="font-semibold">{r.league.name}</h2>
              <RadioGroup
                value={teamByLeague[r.league.id] ? String(teamByLeague[r.league.id]) : ""}
                onValueChange={(v) => setTeamByLeague((cur) => ({ ...cur, [r.league.id]: Number(v) }))}
                aria-label={`Your team in ${r.league.name}`}
              >
                {r.teams.map((t) => (
                  <Label key={t.id} className="flex items-center gap-2 font-normal">
                    <RadioGroupItem value={String(t.id)} />
                    <span className="font-medium">{t.name}</span>
                    {t.owner_name && <span className="text-muted-foreground">· {t.owner_name}</span>}
                    {t.id === r.suggested_team_id && <Badge variant="secondary">Yours on Yahoo</Badge>}
                  </Label>
                ))}
              </RadioGroup>
            </Card>
          ))}
          {confirm.isError && (
            <Alert variant="destructive">
              <AlertDescription>{confirm.error.message}</AlertDescription>
            </Alert>
          )}
          <Button size="lg" onClick={() => confirm.mutate()} disabled={!allPicked || confirm.isPending}>
            {confirm.isPending ? "Loading rosters…" : "Confirm and go to Games"}
          </Button>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader back="/teams/new" title="Choose Yahoo leagues" subtitle="Import as many as you like." />
      {discover.isPending && <CardSkeletons count={2} />}
      {discover.isError &&
        (authError ? (
          <Alert variant="destructive">
            <AlertDescription>
              <p>{discover.error.message}</p>
              <a href={api.yahooConnectUrl} className={cn(buttonVariants({ size: "sm" }), "mt-2")}>
                Connect Yahoo
              </a>
            </AlertDescription>
          </Alert>
        ) : (
          <QueryError error={discover.error} onRetry={() => discover.refetch()} />
        ))}
      {discover.data && (
        <div className="space-y-3">
          {discover.data.length === 0 && (
            <Card className="px-4 py-6 text-center text-muted-foreground">
              No NFL leagues found on this Yahoo account for this season.
            </Card>
          )}
          {discover.data.map((lg) => {
            const on = chosen.has(lg.external_league_id);
            return (
              <button
                key={lg.external_league_id}
                type="button"
                role="checkbox"
                aria-checked={on}
                onClick={() =>
                  setChosen((cur) => {
                    const next = new Set(cur);
                    if (on) next.delete(lg.external_league_id);
                    else next.add(lg.external_league_id);
                    return next;
                  })
                }
                className="block w-full text-left"
              >
                <Card className={cn("flex-row items-center gap-3 px-4 py-4", on && "ring-2 ring-foreground")}>
                  <span
                    className={cn(
                      "flex size-5 shrink-0 items-center justify-center rounded border",
                      on && "border-foreground bg-foreground text-background",
                    )}
                    aria-hidden
                  >
                    {on && <Check className="size-3.5" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold">{lg.name}</div>
                    <div className="text-sm text-muted-foreground">
                      {lg.season} · {lg.num_teams ?? "?"} teams
                    </div>
                  </div>
                  {lg.imported_league_id && <Badge variant="outline">Imported</Badge>}
                </Card>
              </button>
            );
          })}
          {importMutation.isError && (
            <Alert variant="destructive">
              <AlertDescription>{importMutation.error.message}</AlertDescription>
            </Alert>
          )}
          <Button size="lg" onClick={() => importMutation.mutate()} disabled={!chosen.size || importMutation.isPending}>
            {importMutation.isPending ? "Importing…" : `Import ${chosen.size || ""} league${chosen.size === 1 ? "" : "s"}`}
          </Button>
        </div>
      )}
    </>
  );
}
