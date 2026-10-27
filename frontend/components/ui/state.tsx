import { TriangleAlert } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "rounded-lg bg-surface motion-safe:animate-pulse",
        className,
      )}
    />
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center gap-3 px-6 py-10 text-center",
        className,
      )}
    >
      <TriangleAlert aria-hidden className="size-6 text-danger" />
      <div>
        <p className="text-sm font-semibold text-ink">Something went wrong</p>
        <p className="text-sm text-muted">{message}</p>
      </div>
      <Button variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  className,
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 px-6 py-10 text-center",
        className,
      )}
    >
      <div aria-hidden className="text-pending [&_svg]:size-6">
        {icon}
      </div>
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="max-w-xs text-sm text-muted">{body}</p>
    </div>
  );
}
