"use client";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input, Field } from "@/components/ui/input";

interface ConfirmDialogProps {
  title: string;
  body: string;
  confirmLabel: string;
  onConfirm: () => Promise<void>;
  onCancel: () => void;
  /** Type-to-confirm: the user must type this exact text before the button enables. */
  requireText?: { label: string; value: string };
  /** "I understand" checkbox that must be ticked before the button enables. */
  requireCheck?: string;
}

// Destructive confirm dialog shared by delete project / model / key (screen 31).
export function ConfirmDialog({
  title,
  body,
  confirmLabel,
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
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e: KeyboardEvent) =>
      e.key === "Escape" && !busy && onCancel();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onCancel, busy]);

  const ready =
    (!requireText || typed === requireText.value) && (!requireCheck || checked);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await onConfirm();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Something went wrong. Try again.",
      );
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-overlay p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${uid}-t`}
        aria-describedby={`${uid}-d`}
        className="flex w-[400px] max-w-full flex-col gap-3 rounded-2xl bg-white p-6"
      >
        <h2
          id={`${uid}-t`}
          className="text-xl font-semibold leading-[normal] text-ink"
        >
          {title}
        </h2>
        <p id={`${uid}-d`} className="text-sm leading-5 text-muted">
          {body}
        </p>
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
          <Checkbox
            id={`${uid}-ck`}
            checked={checked}
            onCheckedChange={setChecked}
            quiet
          >
            {requireCheck}
          </Checkbox>
        )}
        {error && (
          <p role="alert" className="text-sm leading-[normal] text-danger">
            {error}
          </p>
        )}
        <div className="flex items-start justify-end gap-2">
          <Button
            ref={cancelRef}
            variant="outline"
            size="md"
            onClick={onCancel}
            disabled={busy}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
            size="md"
            className="rounded-[9px]"
            onClick={confirm}
            disabled={!ready || busy}
          >
            {busy ? "Deleting…" : confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
