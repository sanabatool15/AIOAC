"use client";
import { useEffect, useId, useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { useToast } from "@/components/ui/toast";
import { createShare, getShare, revokeShare } from "@/lib/api-real";
import { useAsync } from "@/lib/hooks";
import { shareLink } from "@/lib/screens";
import { ConfirmDialog } from "./confirm-dialog";
import { ErrorLine, useAction } from "./step-parts";

// "Share" button for a project's top bar. Opens the dialog below.
export function ShareButton({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="outline" size="md" onClick={() => setOpen(true)}>
        <Share2 aria-hidden />
        Share
      </Button>
      {open && <ShareDialog projectId={projectId} onClose={() => setOpen(false)} />}
    </>
  );
}

// Share the finished result as a read-only link. The link shows results only: no money, no email, no ids.
export function ShareDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const uid = useId();
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getShare(projectId), projectId);
  const [token, setToken] = useState<string | null | undefined>(undefined); // undefined: use the loaded value
  const [confirming, setConfirming] = useState(false);
  const { busy, error: actionError, run } = useAction();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !confirming && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, confirming]);

  const current = token === undefined ? (data?.enabled ? data.token : null) : token;
  const link = current ? shareLink(window.location.origin, current) : "";

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      toast("Link copied.");
    } catch {
      toast("Could not copy. Select the link and copy it yourself.", "error");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-overlay p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${uid}-t`}
        className="flex w-[520px] max-w-full flex-col gap-3.5 rounded-2xl bg-white p-6"
      >
        <div className="flex items-center justify-between leading-[normal]">
          <h2 id={`${uid}-t`} className="text-xl font-semibold text-ink">
            Share this result
          </h2>
          <button type="button" onClick={onClose} className="text-sm text-muted hover:text-ink">
            Close
          </button>
        </div>
        {loading && !data ? (
          <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading sharing">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : error && !data ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : (
          <>
            <p className="text-sm leading-5 text-ink-2">
              Anyone with the link can see the goal, the data name, and the results. They cannot sign in as you, and they
              see no payments, email or private details. Results are estimates, not promises.
            </p>
            {current ? (
              <>
                <p className="text-xs font-semibold text-muted">SHARING IS ON</p>
                <div className="flex items-center gap-2">
                  <Input aria-label="Share link" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
                  <Button size="md" onClick={() => void copy()}>
                    Copy link
                  </Button>
                </div>
                <div>
                  <Button variant="outline" size="md" onClick={() => setConfirming(true)}>
                    Stop sharing
                  </Button>
                </div>
              </>
            ) : (
              <>
                <p className="text-xs font-semibold text-muted">SHARING IS OFF</p>
                <div>
                  <Button
                    size="md"
                    disabled={busy}
                    onClick={() =>
                      run(async () => {
                        const r = await createShare(projectId);
                        setToken(r.token);
                      })
                    }
                  >
                    {busy ? "Creating…" : "Create a link"}
                  </Button>
                </div>
              </>
            )}
            <ErrorLine message={actionError} />
          </>
        )}
      </div>
      {confirming && (
        <ConfirmDialog
          title="Stop sharing?"
          body="The link will stop working for everyone. You can create a new link later."
          confirmLabel="Stop sharing"
          busyLabel="Stopping…"
          onCancel={() => setConfirming(false)}
          onConfirm={async () => {
            await revokeShare(projectId);
            setToken(null);
            setConfirming(false);
            toast("Sharing stopped.");
          }}
        />
      )}
    </div>
  );
}
