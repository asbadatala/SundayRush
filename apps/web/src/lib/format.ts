import type { Game } from "./types";

export function formatKickoff(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { weekday: "short", hour: "numeric", minute: "2-digit" });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function formatRelative(iso: string | null): string {
  if (!iso) return "never";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** "Kicks off in 1h 38m" for games starting within a day; null otherwise. */
export function formatCountdown(iso: string): string | null {
  const mins = Math.round((new Date(iso).getTime() - Date.now()) / 60_000);
  if (mins <= 0 || mins >= 24 * 60) return null;
  const h = Math.floor(mins / 60);
  return `Kicks off in ${h ? `${h}h ` : ""}${mins % 60}m`;
}

export function formatPoints(points: number | null): string {
  return points === null ? "—" : points.toFixed(2);
}

export function isLive(game: Pick<Game, "status">): boolean {
  return game.status === "live" || game.status === "halftime";
}

export function gameStatusLabel(game: Game): string {
  switch (game.status) {
    case "live":
      return game.quarter ? `Q${game.quarter > 4 ? "OT" : game.quarter} ${game.clock ?? ""}`.trim() : "Live";
    case "halftime":
      return "Halftime";
    case "final":
      return game.status_detail && game.status_detail !== "Final" ? game.status_detail : "Final";
    case "postponed":
      return "Postponed";
    case "canceled":
      return "Canceled";
    default:
      return formatKickoff(game.kickoff_at);
  }
}

export const PRESET_LABELS = { standard: "Standard", half_ppr: "Half PPR", ppr: "Full PPR" } as const;
