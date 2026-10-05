"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { PlayerSearch } from "@/components/player-search";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { api } from "@/lib/api";
import { PRESET_LABELS } from "@/lib/format";
import type { ManualTeam, Player, Preset } from "@/lib/types";

type Slot = "starter" | "bench";
interface Entry {
  player: Player;
  slot: Slot;
}

function fromTeam(team: ManualTeam): Entry[] {
  return [
    ...team.starters.map((s) => ({ player: s.player, slot: "starter" as const })),
    ...team.bench.map((s) => ({ player: s.player, slot: "bench" as const })),
  ];
}

/** Create (team undefined) or edit a custom team. Edits are saved in one pass on "Save". */
export function TeamBuilder({ team }: { team?: ManualTeam }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState(team?.name ?? "");
  const [preset, setPreset] = useState<Preset>(team?.preset ?? "ppr");
  const [entries, setEntries] = useState<Entry[]>(team ? fromTeam(team) : []);

  const save = useMutation({
    mutationFn: async () => {
      if (!team) {
        return api.createManualTeam({
          name: name.trim(),
          preset,
          players: entries.map((e) => ({ player_id: e.player.id, slot: e.slot })),
        });
      }
      await api.updateManualTeam(team.id, { name: name.trim(), preset });
      const before = new Map(fromTeam(team).map((e) => [e.player.id, e.slot]));
      const after = new Map(entries.map((e) => [e.player.id, e.slot]));
      for (const id of before.keys()) if (!after.has(id)) await api.removeManualPlayer(team.id, id);
      for (const [id, slot] of after) if (before.get(id) !== slot) await api.addManualPlayer(team.id, id, slot);
      return api.manualTeam(team.id);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries();
      router.push("/teams");
    },
  });

  const ids = new Set(entries.map((e) => e.player.id));
  const add = (player: Player, slot: Slot) =>
    setEntries((cur) => [...cur.filter((e) => e.player.id !== player.id), { player, slot }]);
  const move = (id: number, slot: Slot) => setEntries((cur) => cur.map((e) => (e.player.id === id ? { ...e, slot } : e)));
  const remove = (id: number) => setEntries((cur) => cur.filter((e) => e.player.id !== id));

  const list = (slot: Slot) => {
    const rows = entries.filter((e) => e.slot === slot);
    return (
      <section aria-label={slot === "starter" ? "Starters" : "Bench"}>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {slot === "starter" ? "Starters" : "Bench"} ({rows.length})
        </h3>
        {rows.length === 0 ? (
          <p className="py-2 text-sm text-muted-foreground">
            {slot === "starter" ? "Add players from search." : "No bench players."}
          </p>
        ) : (
          <ul className="divide-y">
            {rows.map(({ player }) => (
              <li key={player.id} className="flex items-center gap-2 py-2">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{player.full_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {player.position} · {player.nfl_team ?? "FA"}
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => move(player.id, slot === "starter" ? "bench" : "starter")}
                  aria-label={slot === "starter" ? `Move ${player.full_name} to bench` : `Start ${player.full_name}`}
                >
                  {slot === "starter" ? <ArrowDown aria-hidden /> : <ArrowUp aria-hidden />}
                  {slot === "starter" ? "Bench" : "Start"}
                </Button>
                <Button size="icon-sm" variant="ghost" onClick={() => remove(player.id)} aria-label={`Remove ${player.full_name}`}>
                  <X aria-hidden />
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  };

  return (
    <div className="space-y-4">
      <Card className="gap-4 px-4 py-4">
        <div className="space-y-2">
          <Label htmlFor="team-name">Team name</Label>
          <Input id="team-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="My Sunday squad" maxLength={80} />
        </div>
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">Scoring</legend>
          <RadioGroup value={preset} onValueChange={(v) => setPreset(v as Preset)} className="flex flex-wrap gap-4">
            {(Object.keys(PRESET_LABELS) as Preset[]).map((p) => (
              <Label key={p} className="flex items-center gap-2 font-normal">
                <RadioGroupItem value={p} />
                {PRESET_LABELS[p]}
              </Label>
            ))}
          </RadioGroup>
        </fieldset>
      </Card>

      <Card className="gap-4 px-4 py-4">
        <PlayerSearch onAdd={add} excludeIds={ids} />
      </Card>

      <Card className="gap-4 px-4 py-4">
        {list("starter")}
        {list("bench")}
      </Card>

      {save.isError && (
        <Alert variant="destructive">
          <AlertDescription>{save.error.message}</AlertDescription>
        </Alert>
      )}
      <div className="flex gap-2">
        <Button size="lg" onClick={() => save.mutate()} disabled={!name.trim() || save.isPending}>
          {save.isPending ? "Saving…" : team ? "Save changes" : "Save team"}
        </Button>
        <Button size="lg" variant="outline" onClick={() => router.back()}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
