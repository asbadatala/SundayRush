"use client";

import { GAME_SORTS, type GameSort } from "@/lib/game-sort";
import { cn } from "@/lib/utils";

export function GameSortPicker({ value, onChange }: { value: GameSort; onChange: (sort: GameSort) => void }) {
  return (
    <div role="radiogroup" aria-label="Game order" className="inline-flex rounded-full border p-0.5 text-sm">
      {GAME_SORTS.map((s) => {
        const on = s.value === value;
        return (
          <button
            key={s.value}
            type="button"
            role="radio"
            aria-checked={on}
            onClick={() => onChange(s.value)}
            className={cn(
              "rounded-full px-3 py-1 font-medium transition-colors",
              on ? "bg-foreground text-background" : "text-foreground hover:bg-muted",
            )}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}
