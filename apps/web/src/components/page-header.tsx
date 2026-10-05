import { ChevronLeft } from "lucide-react";
import Link from "next/link";

export function PageHeader({
  title,
  subtitle,
  back,
  action,
}: {
  title: string;
  subtitle?: React.ReactNode;
  back?: string;
  action?: React.ReactNode;
}) {
  return (
    <header className="pb-4">
      <div className="flex items-start justify-between gap-3 pb-3">
        <div className="min-w-0">
          {back && (
            <Link href={back} className="mb-1 inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
              <ChevronLeft className="size-4" aria-hidden />
              Back
            </Link>
          )}
          <h1 className="truncate font-heading text-[32px] leading-none font-bold tracking-[0.02em] uppercase">{title}</h1>
          {subtitle && <div className="mt-1.5 text-sm text-muted-foreground">{subtitle}</div>}
        </div>
        {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
      </div>
      <div className="hash-divider" aria-hidden />
    </header>
  );
}
