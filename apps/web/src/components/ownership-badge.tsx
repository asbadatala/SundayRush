import { Armchair, Star, Swords } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Ownership } from "@/lib/types";

// Text + icon + color: ownership is never conveyed by color alone (spec §18.1).
const STYLES: Record<Ownership, { label: string; icon: typeof Star; className: string }> = {
  MY_STARTER: {
    label: "My starter",
    icon: Star,
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  },
  MY_BENCH: {
    label: "My bench",
    icon: Armchair,
    className: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  },
  OPPONENT: {
    label: "Opponent",
    icon: Swords,
    className: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
  },
};

export function OwnershipBadge({ ownership }: { ownership: Ownership }) {
  const { label, icon: Icon, className } = STYLES[ownership];
  return (
    <span
      data-ownership={ownership}
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        className,
      )}
    >
      <Icon className="size-3" aria-hidden />
      {label}
    </span>
  );
}
