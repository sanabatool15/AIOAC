"use client";
import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Field } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";

interface ConfirmDialogProps {
  title: string;
  body: string;
  confirmLabel: string;
  busyLabel?: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  /** Type-to-confirm: the user must type this exact text before the button enables. */
  requireText?: { label: string; value: string };
  /** "I understand" checkbox that must be ticked before the button enables. */
  requireCheck?: string;
}

// Destructive confirm dialog shared by delete project / model / key and by Stop/Cancel run. Render it only while it is
// open (same as before); it sits on the shared Modal (scrim, focus trap, Esc, focus restore). Cancel gets focus first.
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
  busyLabel = "Deleting…",
  onConfirm,
  onCancel,
  requireText,
  requireCheck,
}: ConfirmDialogProps) {
  const uid = useId();
  const [typed, setTyped] = useState("");
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = (!requireText || typed === requireText.value) && (!requireCheck || checked);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={() => {
        if (!busy) onCancel();
      }}
      title={title}
      description={body}
      role="alertdialog"
      size="sm"
      hideClose
      footer={
        <>
          <Button data-autofocus variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant="destructive" onClick={confirm} disabled={!ready || busy}>
            {busy ? busyLabel : confirmLabel}
          </Button>
        </>
      }
    >
      {requireText && (
        <Field label={requireText.label} htmlFor={`${uid}-in`}>
          <Input
            id={`${uid}-in`}
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireText.value}
            autoComplete="off"
          />
        </Field>
      )}
      {requireCheck && (
        <Checkbox id={`${uid}-ck`} checked={checked} onCheckedChange={setChecked} quiet>
          {requireCheck}
        </Checkbox>
      )}
      {error && (
        <p role="alert" className="text-body text-danger">
          {error}
        </p>
      )}
    </Modal>
  );
}
