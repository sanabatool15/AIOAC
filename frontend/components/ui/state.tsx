import { Inbox, TriangleAlert, type LucideIcon } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("rounded-md bg-surface motion-safe:animate-pulse", className)} />;
}

export function ErrorState({
  message,
  onRetry,
  title = "Something went wrong",
  className,
}: {
  message: string;
  onRetry?: () => void;
  title?: string;
  className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-center gap-3 px-6 py-10 text-center", className)}>
      <TriangleAlert aria-hidden className="size-6 text-danger" />
      <div>
        <p className="text-body font-semibold text-ink">{title}</p>
        <p className="text-body text-muted">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  body,
  action,
  className,
}: {
  /** A lucide icon component, for example `icon={FolderOpen}`. Passing an element still works but is deprecated. */
  icon?: LucideIcon | React.ReactNode;
  title: string;
  body: string;
  action?: React.ReactNode;
  className?: string;
}) {
  const isComponent = typeof Icon === "function" || (typeof Icon === "object" && Icon !== null && "render" in Icon);
  return (
    <div className={cn("flex flex-col items-center gap-2 px-6 py-10 text-center", className)}>
      <div aria-hidden className="text-muted [&_svg]:size-6">
        {isComponent ? <>{renderIcon(Icon as LucideIcon)}</> : (Icon as React.ReactNode)}
      </div>
      <p className="text-body font-semibold text-ink">{title}</p>
      <p className="max-w-xs text-body text-muted">{body}</p>
      {action && <div className="mt-1">{action}</div>}
    </div>
  );
}

function renderIcon(Icon: LucideIcon) {
  return <Icon />;
}
