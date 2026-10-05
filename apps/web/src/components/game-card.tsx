import { Tv } from "lucide-react";

import { PlayerRow } from "@/components/player-row";
import { Card } from "@/components/ui/card";
import { formatCountdown, gameStatusLabel, isLive } from "@/lib/format";
import type { GameGroup, PlayerRow as Row } from "@/lib/types";
import { cn } from "@/lib/utils";

type Deltas = ReadonlyMap<string, number>;

function Section({ title, rows, deltas }: { title: string; rows: Row[]; deltas?: Deltas }) {
  if (!rows.length) return null;
  return (
    <section className="px-4">
      <h3 className="pt-2.5 font-heading text-xs font-semibold tracking-[0.12em] text-muted-foreground uppercase">{title}</h3>
      <ul className="divide-y">
        {rows.map((r) => {
          const delta = deltas?.get(r.key);
          // Re-key on new points so the flash replays on every gain.
          return <PlayerRow key={delta ? `${r.key}:${r.points}` : r.key} row={r} delta={delta} />;
        })}
      </ul>
    </section>
  );
}

function TeamLine({ abbr, score, showScore, result }: {
  abbr: string;
  score: number | null;
  showScore: boolean;
  result?: "won" | "lost";
}) {
  return (
    <div className={cn("flex items-center gap-2.5", result === "lost" && "opacity-55")}>
      <span className="w-12 font-heading text-[22px] leading-tight font-bold tracking-[0.02em]">{abbr}</span>
      {showScore && (
        <span className="min-w-[2.2ch] text-right font-heading text-2xl leading-tight font-semibold tabular-nums">{score}</span>
      )}
      {result === "won" && (
        <>
          <span className="text-[10px] text-live" aria-hidden>
            ◀
          </span>
          <span className="sr-only">(winner)</span>
        </>
      )}
    </div>
  );
}

const sum = (rows: Row[]) => rows.reduce((t, r) => t + (r.points ?? 0), 0);

/** "3 of your players · You 34.0 · Opp 18.4": what this game is worth to you, independent of filters. */
function Stake({ group, scored }: { group: GameGroup; scored: boolean }) {
  const mine = group.my_starters.length + group.my_bench.length;
  const opp = group.opponents.length;
  const countdown = scored ? null : formatCountdown(group.game.kickoff_at);
  return (
    <div className="flex justify-between gap-2 border-b bg-stake px-4 py-1.5 text-xs text-muted-foreground" data-testid="game-stake">
      <span>
        {mine > 0
          ? `${mine} of your player${mine === 1 ? "" : "s"}`
          : `${opp} opponent player${opp === 1 ? "" : "s"}`}
      </span>
      {scored ? (
        <span>
          You <b className="text-foreground tabular-nums">{sum(group.my_starters).toFixed(1)}</b> · Opp{" "}
          <b className="text-foreground tabular-nums">{sum(group.opponents).toFixed(1)}</b>
        </span>
      ) : (
        countdown && <span>{countdown}</span>
      )}
    </div>
  );
}

export function GameCard({ group, starters, bench, opponents, deltas }: {
  group: GameGroup;
  deltas?: Deltas;
} & Record<"starters" | "bench" | "opponents", Row[]>) {
  const { game } = group;
  const live = isLive(game);
  const final = game.status === "final";
  const showScore = live || final;
  const away = game.away_score ?? 0;
  const home = game.home_score ?? 0;
  const awayResult = final && away !== home ? (away > home ? "won" : "lost") : undefined;
  const homeResult = final && away !== home ? (home > away ? "won" : "lost") : undefined;
  const empty = !starters.length && !bench.length && !opponents.length;

  return (
    <Card className="gap-0 overflow-hidden py-0" data-testid="game-card" data-game={`${game.away_team}@${game.home_team}`} data-kickoff={game.kickoff_at}>
      {/* Turf band; live games get the yellow first-down line along the bottom. */}
      <div className={cn("turf-band flex items-center justify-between gap-3 px-4 py-3 text-white", live && "shadow-[inset_0_-4px_0_var(--live)]")}>
        <div className="flex min-w-0 flex-col gap-1">
          <TeamLine abbr={game.away_team} score={game.away_score} showScore={showScore} result={awayResult} />
          <TeamLine abbr={game.home_team} score={game.home_score} showScore={showScore} result={homeResult} />
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1 text-right text-xs">
          {live && (
            <span className="inline-flex items-center gap-1.5 rounded-[2px] bg-live px-2 py-0.5 text-[11px] font-extrabold tracking-[0.08em] text-live-foreground">
              <span className="size-1.5 rounded-full bg-current motion-safe:animate-pulse" aria-hidden />
              LIVE
            </span>
          )}
          <span className="font-heading text-[15px] font-semibold tracking-[0.03em]">{gameStatusLabel(game)}</span>
          {game.broadcaster && (
            <span className="flex items-center gap-1 text-white/80">
              <Tv className="size-3" aria-hidden />
              {game.broadcaster}
            </span>
          )}
        </div>
      </div>
      {empty ? (
        <p className="px-4 py-3 text-sm text-muted-foreground">None of your players are in this game.</p>
      ) : (
        <>
          <Stake group={group} scored={showScore} />
          <div className="pb-1">
            <Section title="My players" rows={starters} deltas={deltas} />
            <Section title="My bench" rows={bench} deltas={deltas} />
            <Section title="Opponent players" rows={opponents} deltas={deltas} />
          </div>
        </>
      )}
    </Card>
  );
}
