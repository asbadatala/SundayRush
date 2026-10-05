import { Tv } from "lucide-react";

import { PlayerRow } from "@/components/player-row";
import { Card } from "@/components/ui/card";
import { gameStatusLabel, isLive } from "@/lib/format";
import type { GameGroup, PlayerRow as Row } from "@/lib/types";
import { cn } from "@/lib/utils";

function Section({ title, rows }: { title: string; rows: Row[] }) {
  if (!rows.length) return null;
  return (
    <section className="px-4">
      <h3 className="pt-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{title}</h3>
      <ul className="divide-y">
        {rows.map((r) => (
          <PlayerRow key={r.key} row={r} />
        ))}
      </ul>
    </section>
  );
}

export function GameCard({ group, starters, bench, opponents }: { group: GameGroup } & Record<"starters" | "bench" | "opponents", Row[]>) {
  const { game } = group;
  const live = isLive(game);
  const showScore = live || game.status === "final";
  const awayWin = game.status === "final" && (game.away_score ?? 0) > (game.home_score ?? 0);
  const homeWin = game.status === "final" && (game.home_score ?? 0) > (game.away_score ?? 0);
  const empty = !starters.length && !bench.length && !opponents.length;

  return (
    <Card className="gap-0 overflow-hidden py-0" data-testid="game-card" data-game={`${game.away_team}@${game.home_team}`} data-kickoff={game.kickoff_at}>
      <div className={cn("flex items-center justify-between gap-3 border-b px-4 py-3", live && "bg-emerald-50 dark:bg-emerald-950/40")}>
        <div className="flex min-w-0 items-baseline gap-2 text-lg font-bold">
          <span className={cn(awayWin && "underline decoration-2 underline-offset-4")}>{game.away_team}</span>
          {showScore && <span className="font-mono tabular-nums">{game.away_score}</span>}
          <span className="text-sm font-normal text-muted-foreground">@</span>
          <span className={cn(homeWin && "underline decoration-2 underline-offset-4")}>{game.home_team}</span>
          {showScore && <span className="font-mono tabular-nums">{game.home_score}</span>}
        </div>
        <div className="shrink-0 text-right text-xs">
          <div className={cn("font-semibold", live ? "text-emerald-700 dark:text-emerald-300" : "text-muted-foreground")}>
            {live && <span className="mr-1 inline-block size-2 animate-pulse rounded-full bg-emerald-600" aria-hidden />}
            {live && <span className="sr-only">Live: </span>}
            {gameStatusLabel(game)}
          </div>
          {game.broadcaster && (
            <div className="flex items-center justify-end gap-1 text-muted-foreground">
              <Tv className="size-3" aria-hidden />
              {game.broadcaster}
            </div>
          )}
        </div>
      </div>
      {empty ? (
        <p className="px-4 py-3 text-sm text-muted-foreground">None of your players are in this game.</p>
      ) : (
        <div className="pb-2">
          <Section title="My players" rows={starters} />
          <Section title="My bench" rows={bench} />
          <Section title="Opponent players" rows={opponents} />
        </div>
      )}
    </Card>
  );
}
