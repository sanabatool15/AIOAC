"use client";
import { Download, FlaskConical } from "lucide-react";
import { Button, LinkButton } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EstimateNote } from "@/components/ui/estimate-note";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
import { outOf100 } from "@/lib/adapters";
import { downloadModel, getModel } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { formatWhen } from "@/lib/screens";
import { saveFile } from "./model-tab";
import { ErrorLine, useAction } from "./step-parts";

// The model in the right pane: one card, two choices. Test your model opens its own page; Download saves the file.
export function ModelPanel({ projectId }: { projectId: string }) {
  const { data, error, loading, retry } = useAsync(() => getModel(projectId), projectId);
  const dl = useAction();
  if (loading && !data) return <Skeleton className="h-40" />;
  if (error || !data) return <ErrorState message={error?.message ?? "The model could not be loaded."} onRetry={retry} />;
  if (!data.available) {
    return <EmptyState title="No model yet" body="A model is saved here when a training run finishes." />;
  }
  return (
    <>
      <Card aria-label="Your model" className="gap-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-section text-ink">Your model</h2>
          <Tag variant={data.usable ? "success" : "warning"}>{data.usable ? "Ready" : "Cannot be tested here"}</Tag>
        </div>
        <p className="text-body text-ink-2">
          It predicts &quot;{data.target}&quot;. {data.version_no ? `Version ${data.version_no}, ` : ""}trained {formatWhen(data.trained_at)}.{" "}
          {data.task_type && data.task_type !== "classification"
            ? "It is a different kind of model, so see the Model tab for how it did."
            : `On test data it got about ${outOf100(data.accuracy)} right. A simple guess gets ${outOf100(data.simple_guess_accuracy)}.`}
        </p>
        {!data.usable && (
          <p className="text-body text-ink-2">
            {data.unusable_reason ?? "The saved model could not be opened on this server."} You can still download it.
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          {data.usable ? (
            <LinkButton href={`/c/${projectId}/test`}>
              <FlaskConical aria-hidden />
              Test your model
            </LinkButton>
          ) : (
            <Button type="button" disabled>
              <FlaskConical aria-hidden />
              Test your model
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            disabled={dl.busy}
            onClick={() =>
              dl.run(async () => {
                const f = await downloadModel(projectId);
                saveFile(f.blob, f.filename);
              })
            }
          >
            <Download aria-hidden />
            {dl.busy ? "Downloading…" : "Download"}
          </Button>
        </div>
        <ErrorLine message={dl.error} />
        <EstimateNote>Measured on held-back test rows. An estimate, not a promise.</EstimateNote>
      </Card>
    </>
  );
}
