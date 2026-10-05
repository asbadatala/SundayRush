import { AlertTriangle } from "lucide-react";

import { OwnershipBadge } from "@/components/ownership-badge";
import { formatPoints } from "@/lib/format";
import type { PlayerRow as Row } from "@/lib/types";
import { cn } from "@/lib/utils";

const HEALTHY = new Set(["", "Active", "Healthy"]);

const POSITION_COLOR: Record<string, string> = {
  QB: "bg-pos-qb",
  RB: "bg-pos-rb",
  WR: "bg-pos-wr",
  TE: "bg-pos-te",
};

const PROVIDER_TAG: Record<string, string> = { yahoo: "Y!", manual: "C", sleeper: "SL", espn: "E" };

/** Position "jersey"; decorative, since the position is also spelled out next to the name. */
function Jersey({ position }: { position: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "jersey grid size-9 shrink-0 place-items-center font-heading text-[13px] font-bold text-jersey-ink",
        POSITION_COLOR[position] ?? "bg-pos-other",
      )}
    >
      {position.slice(0, 3)}
    </div>
  );
}

export function PlayerRow({ row, showOwnership = true, delta }: { row: Row; showOwnership?: boolean; delta?: number }) {
  const injury = row.injury_status && !HEALTHY.has(row.injury_status) ? row.injury_status : null;
  return (
    <li
      className={cn("flex items-center gap-3 py-2.5", delta && "-mx-4 px-4 motion-safe:animate-point-flash")}
      data-testid="player-row"
      data-ownership={row.ownership}
    >
      <Jersey position={row.position} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="truncate font-semibold">{row.name}</span>
          <span className="text-xs text-muted-foreground">
            {row.position}
            {row.nfl_team ? ` · ${row.nfl_team}` : ""}
          </span>
          {injury && (
            <span className="rounded bg-injury px-1.5 text-[10px] font-extrabold text-injury-foreground">{injury}</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 pt-1">
          {showOwnership && <OwnershipBadge ownership={row.ownership} />}
          <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
            <span className="shrink-0 rounded-[3px] border px-1 text-[9px] leading-[14px] font-extrabold" aria-hidden>
              {PROVIDER_TAG[row.provider] ?? row.provider.slice(0, 2).toUpperCase()}
            </span>
            <span className="truncate">{row.league_name}</span>
          </span>
        </div>
        {row.stat_line && <div className="truncate pt-1 text-xs text-muted-foreground">{row.stat_line}</div>}
        {!row.mapped && (
          <div className="flex items-center gap-1 pt-1 text-xs text-warning">
            <AlertTriangle className="size-3" aria-hidden />
            Unmapped player — couldn&apos;t match to an NFL player
          </div>
        )}
      </div>
      <div className="min-w-14 shrink-0 text-right">
        <div className="font-heading text-lg leading-tight font-semibold tabular-nums">{formatPoints(row.points)}</div>
        <div className="text-[10px] text-muted-foreground">
          {row.points === null ? (row.points_unavailable_reason ? "pts unavailable" : "—") : "pts"}
        </div>
        {delta ? (
          <span className="mt-0.5 inline-block rounded-full bg-live px-1.5 text-[10px] font-extrabold text-live-foreground">
            +{delta.toFixed(1)}
            <span className="sr-only"> points since last update</span>
          </span>
        ) : null}
      </div>
    </li>
  );
}
