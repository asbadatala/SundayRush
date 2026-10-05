"use client";

import { GAME_SORTS, type GameSort } from "@/lib/game-sort";
import { cn } from "@/lib/utils";

export function GameSortPicker({ value, onChange }: { value: GameSort; onChange: (sort: GameSort) => void }) {
  return (
    <div className="flex items-center gap-2.5 text-xs text-muted-foreground">
      <span aria-hidden>Sort</span>
      <div role="radiogroup" aria-label="Game order" className="inline-flex gap-0.5 rounded-md bg-muted p-[3px]">
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
                "rounded-[3px] px-2.5 py-1 text-xs font-medium transition-colors",
                on ? "bg-card text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
              )}
            >
              {s.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
