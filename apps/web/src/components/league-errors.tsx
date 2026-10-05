import { AlertCircle, RefreshCw } from "lucide-react";
import Link from "next/link";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { LeagueError } from "@/lib/types";

/** Per-league problems rendered inline so one bad provider never blanks the page. */
export function LeagueErrors({ errors }: { errors: LeagueError[] }) {
  if (!errors.length) return null;
  const authExpired = errors.filter((e) => e.code === "PROVIDER_AUTH_EXPIRED");
  const others = errors.filter((e) => e.code !== "PROVIDER_AUTH_EXPIRED");
  return (
    <div className="space-y-2">
      {authExpired.length > 0 && (
        <Alert variant="destructive" data-testid="reconnect-banner">
          <AlertCircle aria-hidden />
          <AlertTitle>Your Yahoo connection has expired</AlertTitle>
          <AlertDescription>
            <p>
              Reconnect Yahoo to refresh {authExpired.map((e) => e.league_name).join(", ")}. Until then you&apos;re
              seeing the last synced rosters — or create the roster as a custom team instead.
            </p>
            <div className="flex flex-wrap gap-2 pt-2">
              <a href={api.yahooConnectUrl} className={buttonVariants({ size: "sm" })}>
                <RefreshCw aria-hidden />
                Reconnect Yahoo
              </a>
              <Link href="/teams/custom/new" className={buttonVariants({ size: "sm", variant: "outline" })}>
                Create custom team
              </Link>
            </div>
          </AlertDescription>
        </Alert>
      )}
      {others.map((e) => (
        <Alert key={`${e.league_id}-${e.code}`} data-testid="league-error">
          <AlertCircle aria-hidden />
          <AlertTitle>{e.league_name}</AlertTitle>
          <AlertDescription>
            {e.message}
            {e.code === "TEAM_NOT_SELECTED" && (
              <div className="pt-2">
                <Link href="/teams" className={buttonVariants({ size: "sm", variant: "outline" })}>
                  Pick your team
                </Link>
              </div>
            )}
          </AlertDescription>
        </Alert>
      ))}
    </div>
  );
}
