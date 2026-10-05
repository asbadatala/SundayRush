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
    <header className="flex items-start justify-between gap-3 pb-4">
      <div className="min-w-0">
        {back && (
          <Link href={back} className="mb-1 inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
            <ChevronLeft className="size-4" aria-hidden />
            Back
          </Link>
        )}
        <h1 className="truncate text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <div className="text-sm text-muted-foreground">{subtitle}</div>}
      </div>
      {action && <div className="flex shrink-0 items-center gap-2">{action}</div>}
    </header>
  );
}
