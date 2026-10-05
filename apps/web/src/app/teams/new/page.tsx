"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, PenLine } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { PageHeader } from "@/components/page-header";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { errorCopy } from "@/lib/errors";

function ConnectError() {
  const message = errorCopy(useSearchParams().get("error"));
  if (!message) return null;
  return (
    <Alert variant="destructive" data-testid="connect-error">
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

function Option({
  href,
  external,
  title,
  description,
  icon,
  disabled,
  badge,
}: {
  href?: string;
  external?: boolean;
  title: string;
  description: string;
  icon: React.ReactNode;
  disabled?: boolean;
  badge?: string;
}) {
  const inner = (
    <Card className={`flex-row items-center gap-3 px-4 py-4 ${disabled ? "opacity-60" : "hover:bg-muted/50"}`}>
      <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-muted text-lg font-black">{icon}</div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 font-semibold">
          {title}
          {badge && <Badge variant="outline">{badge}</Badge>}
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {!disabled && <ChevronRight className="size-4 text-muted-foreground" aria-hidden />}
    </Card>
  );
  if (disabled || !href) return <div aria-disabled="true">{inner}</div>;
  // Yahoo OAuth start is a full-page navigation to the API, not a client route.
  return external ? <a href={href}>{inner}</a> : <Link href={href}>{inner}</Link>;
}

export default function NewTeamPage() {
  const providers = useQuery({ queryKey: ["providers"], queryFn: api.providers });
  const yahoo = providers.data?.find((p) => p.id === "yahoo");

  return (
    <>
      <PageHeader back="/teams" title="Add fantasy team" subtitle="No account needed. Pick where your team lives." />
      <div className="space-y-3">
        <Suspense>
          <ConnectError />
        </Suspense>
        <Option
          href={yahoo?.connected ? "/teams/yahoo/select" : api.yahooConnectUrl}
          external={!yahoo?.connected}
          title="Yahoo Fantasy"
          description={
            yahoo?.connected
              ? "Connected. Choose which leagues to import."
              : "Sign in with Yahoo (read-only) to import your leagues."
          }
          icon={<span className="text-violet-700">Y!</span>}
          badge={yahoo?.connected ? "Connected" : undefined}
        />
        <Option
          href="/teams/custom/new"
          title="Custom team"
          description="Build any roster by hand — works for every provider."
          icon={<PenLine className="size-5" aria-hidden />}
        />
        {providers.data
          ?.filter((p) => !p.available)
          .map((p) => (
            <Option
              key={p.id}
              disabled
              title={p.name}
              description={p.note ?? "Coming soon"}
              icon={<span>{p.name[0]}</span>}
              badge="Coming soon"
            />
          ))}
      </div>
    </>
  );
}
