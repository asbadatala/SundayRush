"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { api, resetSession } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { GAME_SORTS, type GameSort } from "@/lib/game-sort";
import { clearLocalPrefs, type FilterToggle, useDefaultFilters, useFilters } from "@/lib/prefs";

const FILTER_LABELS: { key: FilterToggle; label: string }[] = [
  { key: "starters", label: "Show my starters" },
  { key: "bench", label: "Show bench players" },
  { key: "opponents", label: "Show opponent players" },
  { key: "allGames", label: "Show all NFL games" },
];

export default function SettingsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [defaults, setDefaults] = useDefaultFilters();
  const [, setFilters] = useFilters();
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const yahoo = providers.data?.find((p) => p.id === "yahoo");

  const disconnect = useMutation({
    mutationFn: api.yahooDisconnect,
    onSuccess: () => queryClient.invalidateQueries(),
  });
  const clear = useMutation({
    mutationFn: api.clearSession,
    onSuccess: () => {
      clearLocalPrefs();
      resetSession();
      queryClient.clear();
      router.push("/");
    },
  });

  return (
    <>
      <PageHeader title="Settings" />
      <div className="space-y-4">
        <Card className="gap-3 px-4 py-4">
          <h2 className="font-semibold">Default game-day filters</h2>
          {FILTER_LABELS.map(({ key, label }) => (
            <div key={key} className="flex items-center justify-between gap-3">
              <Label htmlFor={`default-${key}`} className="font-normal">
                {label}
              </Label>
              <Switch
                id={`default-${key}`}
                checked={defaults[key]}
                onCheckedChange={(checked) => {
                  setDefaults({ [key]: checked });
                  setFilters({ [key]: checked });
                }}
              />
            </div>
          ))}
          <h3 className="pt-1 text-sm font-semibold">Default game order</h3>
          <RadioGroup
            value={defaults.sort}
            onValueChange={(v) => {
              setDefaults({ sort: v as GameSort });
              setFilters({ sort: v as GameSort });
            }}
            aria-label="Default game order"
          >
            {GAME_SORTS.map(({ value, label }) => (
              <Label key={value} className="flex items-center gap-2 font-normal">
                <RadioGroupItem value={value} />
                {label}
              </Label>
            ))}
          </RadioGroup>
        </Card>

        <Card className="gap-3 px-4 py-4">
          <h2 className="font-semibold">Yahoo</h2>
          {yahoo?.connected ? (
            <>
              <p className="text-sm text-muted-foreground">
                Connected {formatRelative(yahoo.connected_at)} with read-only access. Disconnecting deletes the stored
                tokens; imported leagues stay but stop syncing.
              </p>
              <Button
                variant="destructive"
                className="self-start"
                onClick={() => disconnect.mutate()}
                disabled={disconnect.isPending}
              >
                Disconnect Yahoo
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">Not connected.</p>
              <a href={api.yahooConnectUrl} className={buttonVariants({ variant: "outline", className: "self-start" })}>
                Connect Yahoo
              </a>
            </>
          )}
        </Card>

        <Card className="gap-3 px-4 py-4">
          <h2 className="font-semibold">Clear local data</h2>
          <p className="text-sm text-muted-foreground">
            Deletes this browser&apos;s anonymous profile: leagues, custom teams, Yahoo tokens, and preferences.
          </p>
          {clear.isError && (
            <Alert variant="destructive">
              <AlertDescription>{clear.error.message}</AlertDescription>
            </Alert>
          )}
          <Button
            variant="destructive"
            className="self-start"
            onClick={() => confirm("Delete all of your SundayRush data on this device?") && clear.mutate()}
            disabled={clear.isPending}
          >
            Clear all data
          </Button>
        </Card>
      </div>
    </>
  );
}
