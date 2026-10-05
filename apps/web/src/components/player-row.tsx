import { AlertTriangle } from "lucide-react";

import { OwnershipBadge } from "@/components/ownership-badge";
import { formatPoints } from "@/lib/format";
import type { PlayerRow as Row } from "@/lib/types";

const HEALTHY = new Set(["", "Active", "Healthy"]);

export function PlayerRow({ row, showOwnership = true }: { row: Row; showOwnership?: boolean }) {
  const injury = row.injury_status && !HEALTHY.has(row.injury_status) ? row.injury_status : null;
  return (
    <li className="flex items-center gap-3 py-2" data-testid="player-row" data-ownership={row.ownership}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
          <span className="truncate font-medium">{row.name}</span>
          <span className="text-xs text-muted-foreground">
            {row.position}
            {row.nfl_team ? ` · ${row.nfl_team}` : ""}
          </span>
          {injury && (
            <span className="rounded bg-amber-100 px-1 text-[10px] font-bold text-amber-900 dark:bg-amber-950 dark:text-amber-200">
              {injury}
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 pt-0.5">
          {showOwnership && <OwnershipBadge ownership={row.ownership} />}
          <span className="truncate text-xs text-muted-foreground">{row.league_name}</span>
        </div>
        {row.stat_line && <div className="truncate pt-0.5 text-xs text-muted-foreground">{row.stat_line}</div>}
        {!row.mapped && (
          <div className="flex items-center gap-1 pt-0.5 text-xs text-amber-700 dark:text-amber-300">
            <AlertTriangle className="size-3" aria-hidden />
            Unmapped player — couldn&apos;t match to an NFL player
          </div>
        )}
      </div>
      <div className="shrink-0 text-right">
        <div className="font-mono text-base font-semibold tabular-nums">{formatPoints(row.points)}</div>
        <div className="text-[10px] text-muted-foreground">
          {row.points === null ? (row.points_unavailable_reason ? "pts unavailable" : "—") : "pts"}
        </div>
      </div>
    </li>
  );
}
