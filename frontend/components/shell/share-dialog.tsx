"use client";
import { useState } from "react";
import { Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { Tag } from "@/components/ui/tag";
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
      <Button variant="outline" onClick={() => setOpen(true)}>
        <Share2 aria-hidden />
        Share
      </Button>
      {open && <ShareDialog projectId={projectId} onClose={() => setOpen(false)} />}
    </>
  );
}

// Share the finished result as a read-only link. The link shows results only: no money, no email, no ids.
export function ShareDialog({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const toast = useToast();
  const { data, error, loading, retry } = useAsync(() => getShare(projectId), projectId);
  const [token, setToken] = useState<string | null | undefined>(undefined); // undefined: use the loaded value
  const [confirming, setConfirming] = useState(false);
  const { busy, error: actionError, run } = useAction();

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
    <>
      <Modal
        open
        onClose={onClose}
        title="Share this result"
        description="Anyone with the link sees the goal, the data name and the results, with no payments, email or private details."
      >
        {loading && !data ? (
          <div className="flex flex-col gap-3" aria-busy="true" aria-label="Loading sharing">
            <Skeleton className="h-10" />
            <Skeleton className="h-10" />
          </div>
        ) : error && !data ? (
          <ErrorState message={error.message} onRetry={retry} />
        ) : (
          <>
            {current ? (
              <>
                <div className="flex items-center gap-2">
                  <Tag variant="success">Sharing is on</Tag>
                </div>
                <div className="flex items-center gap-2">
                  <Input aria-label="Share link" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
                  <Button onClick={() => void copy()}>Copy link</Button>
                </div>
                <div>
                  <Button variant="outline" onClick={() => setConfirming(true)}>
                    Stop sharing
                  </Button>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2">
                  <Tag>Sharing is off</Tag>
                </div>
                <div>
                  <Button
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
      </Modal>
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
    </>
  );
}
