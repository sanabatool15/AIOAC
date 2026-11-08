import { cn } from "@/lib/utils";

/** One h1 per page: title, optional subtitle and actions. */
export function PageHeader({
  title,
  subtitle,
  actions,
  clampTitle,
  className,
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  /** Cut a long title (a project goal) to two lines; show the full text elsewhere on the page. */
  clampTitle?: boolean;
  className?: string;
}) {
  return (
    <header className={cn("flex flex-wrap items-start justify-between gap-x-4 gap-y-3", className)}>
      <div className="min-w-0 flex-1">
        <h1 className={cn("text-title text-ink break-words", clampTitle && "line-clamp-2")}>{title}</h1>
        {subtitle && <p className="mt-1 text-body text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}
