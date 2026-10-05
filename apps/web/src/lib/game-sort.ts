import type { GameGroup } from "@/lib/types";

export type GameSort = "relevance" | "kickoff" | "unfinished";

export const GAME_SORTS: { value: GameSort; label: string }[] = [
  { value: "relevance", label: "Most relevant" },
  { value: "kickoff", label: "Kickoff time" },
  { value: "unfinished", label: "Not finished" },
];

// My starters score directly for me and opponent starters score directly against me;
// bench players only matter as a tiebreaker.
const WEIGHTS = { my_starters: 3, opponents: 2, my_bench: 1 } as const;

const FINISHED = new Set(["final", "postponed", "canceled"]);

/** How much a game matters, from every fantasy player in it (independent of the filter chips). */
export function relevance(group: GameGroup): number {
  return (
    group.my_starters.length * WEIGHTS.my_starters +
    group.opponents.length * WEIGHTS.opponents +
    group.my_bench.length * WEIGHTS.my_bench
  );
}

/**
 * Orders (and for "unfinished", filters) games. The API already returns live, then
 * upcoming by kickoff, then final; Array.prototype.sort is stable, so that order breaks ties.
 */
export function sortGames<T extends { group: GameGroup }>(items: T[], sort: GameSort): T[] {
  switch (sort) {
    case "kickoff":
      return [...items].sort((a, b) => Date.parse(a.group.game.kickoff_at) - Date.parse(b.group.game.kickoff_at));
    case "unfinished":
      return items.filter((i) => !FINISHED.has(i.group.game.status));
    default:
      return [...items].sort((a, b) => relevance(b.group) - relevance(a.group));
  }
}
