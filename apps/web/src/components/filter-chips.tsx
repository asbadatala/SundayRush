"use client";

import { Check } from "lucide-react";

import type { FilterToggle, Filters } from "@/lib/prefs";
import { cn } from "@/lib/utils";

const CHIPS: { key: FilterToggle; label: string }[] = [
  { key: "starters", label: "My starters" },
  { key: "bench", label: "Bench" },
  { key: "opponents", label: "Opponents" },
  { key: "allGames", label: "All NFL games" },
];

export function FilterChips({ filters, onChange }: { filters: Filters; onChange: (patch: Partial<Filters>) => void }) {
  return (
    <div role="group" aria-label="Filters" className="flex flex-wrap gap-2">
      {CHIPS.map(({ key, label }) => {
        const on = filters[key];
        return (
          <button
            key={key}
            type="button"
            aria-pressed={on}
            onClick={() => onChange({ [key]: !on })}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-medium transition-colors",
              on ? "border-foreground bg-foreground text-background" : "bg-background text-foreground hover:bg-muted",
            )}
          >
            {on && <Check className="size-3.5" aria-hidden />}
            {label}
          </button>
        );
      })}
    </div>
  );
}
