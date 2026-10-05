import { Clock, Star, Swords } from "lucide-react";

import { cn } from "@/lib/utils";
import type { Ownership } from "@/lib/types";

// Text + icon + color: ownership is never conveyed by color alone (spec §18.1).
const STYLES: Record<Ownership, { label: string; icon: typeof Star; className: string }> = {
  MY_STARTER: { label: "My starter", icon: Star, className: "text-starter" },
  MY_BENCH: { label: "My bench", icon: Clock, className: "text-bench" },
  OPPONENT: { label: "Opponent", icon: Swords, className: "text-opponent" },
};

/** Outlined "jersey patch" label. */
export function OwnershipBadge({ ownership }: { ownership: Ownership }) {
  const { label, icon: Icon, className } = STYLES[ownership];
  return (
    <span
      data-ownership={ownership}
      className={cn(
        "inline-flex items-center gap-1 rounded-[3px] border-[1.5px] border-current px-1.5 py-px font-heading text-[10.5px] font-semibold tracking-[0.08em] uppercase",
        className,
      )}
    >
      <Icon className="size-[11px]" aria-hidden />
      {label}
    </span>
  );
}
