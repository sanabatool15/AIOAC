"use client";
import { Card } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { getActivity } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { toActivity } from "@/lib/screens";

// What the agent did, in plain words, from GET /projects/{id}/activity. `refreshKey` changes when the project moves on,
// so the list reads again. Used on the project page and in the chat's right pane.
export function ActivityCard({ projectId, refreshKey }: { projectId: string; refreshKey?: string }) {
  const { data, error, loading, retry } = useAsync(() => getActivity(projectId), refreshKey ?? projectId);
  if (loading && !data) return <Skeleton className="h-40" />;
  if (error || !data) return <ErrorState message={error?.message ?? "Activity unavailable."} onRetry={retry} />;
  const items = toActivity(data);
  return (
    <Card aria-label="What the agent did" className="gap-3 p-5">
      <h2 className="text-section text-ink">What the agent did</h2>
      {items.length === 0 ? (
        <p className="text-body text-muted">Nothing yet. Start in the chat.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {items.map((a) => (
            <li key={a.key} className="flex items-start gap-3 text-body">
              <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-full bg-brand" />
              <span className="min-w-0 flex-1 text-ink">{a.text}</span>
              <time className="shrink-0 text-micro text-muted">{a.when}</time>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
