"use client";

import { Moon, Sun } from "lucide-react";
import Link from "next/link";

import { LogoMark, Wordmark } from "@/components/logo";
import { toggleTheme } from "@/lib/theme";

export function TopBar() {
  return (
    <div className="flex items-center justify-between pb-4">
      <Link href="/" aria-label="SundayRush home" className="flex items-center gap-2 rounded-md">
        <LogoMark className="size-[30px]" />
        <Wordmark />
      </Link>
      {/* Icons swap via the .dark class (set before paint), so the server render never mismatches. */}
      <button
        type="button"
        onClick={toggleTheme}
        aria-label="Toggle dark mode"
        className="grid size-[34px] place-items-center rounded-md border bg-card text-foreground transition-colors hover:bg-muted"
      >
        <Moon className="size-4 dark:hidden" aria-hidden />
        <Sun className="hidden size-4 dark:block" aria-hidden />
      </button>
    </div>
  );
}
