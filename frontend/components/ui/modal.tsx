"use client";
import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import {
  FOCUSABLE,
  isTopModal,
  lockScroll,
  nextFocusIndex,
  popModal,
  pushModal,
  unlockScroll,
} from "./modal-stack";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  /** "alertdialog" for confirmations that need an answer. */
  role?: "dialog" | "alertdialog";
  /** Clicking the dark area closes the modal. Default: true for dialog, false for alertdialog. */
  closeOnBackdrop?: boolean;
  /** Hide the corner close button (confirmations have their own buttons). */
  hideClose?: boolean;
  size?: "sm" | "md" | "lg";
  footer?: React.ReactNode;
  children?: React.ReactNode;
}

const SIZE = { sm: "max-w-sm", md: "max-w-form", lg: "max-w-2xl" } as const;

export function Modal({
  open,
  onClose,
  title,
  description,
  role = "dialog",
  closeOnBackdrop,
  hideClose,
  size = "md",
  footer,
  children,
}: ModalProps) {
  const id = useId();
  const titleId = `${id}-title`;
  const descId = `${id}-desc`;
  const panel = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });
  const backdropCloses = closeOnBackdrop ?? role === "dialog";

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    pushModal(id);
    lockScroll(document.body);

    const el = panel.current;
    const first = el?.querySelector<HTMLElement>("[data-autofocus]") ?? el?.querySelector<HTMLElement>(FOCUSABLE);
    (first ?? el)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isTopModal(id) && !e.defaultPrevented) {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !isTopModal(id) || !el) return;
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) {
        e.preventDefault();
        el.focus();
        return;
      }
      const at = items.indexOf(document.activeElement as HTMLElement);
      const next = nextFocusIndex(at, items.length, e.shiftKey);
      // let the browser move focus unless we are at an edge or focus escaped
      if (at < 0 || (e.shiftKey && at === 0) || (!e.shiftKey && at === items.length - 1)) {
        e.preventDefault();
        items[next].focus();
      }
    };
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("keydown", onKey);
      popModal(id);
      unlockScroll(document.body);
      if (opener?.isConnected) opener.focus();
    };
  }, [open, id]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center overflow-y-auto bg-scrim p-4 sm:items-center"
      onMouseDown={(e) => {
        if (backdropCloses && e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          "relative flex w-full flex-col gap-4 rounded-xl border border-border bg-card p-6 shadow-popover outline-none motion-safe:animate-modal-in",
          SIZE[size],
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 id={titleId} className="text-section text-ink">
              {title}
            </h2>
            {description && (
              <p id={descId} className="mt-1 text-body text-muted">
                {description}
              </p>
            )}
          </div>
          {!hideClose && (
            <Button variant="ghost" size="icon" aria-label="Close" onClick={onClose} className="-mr-2 -mt-2 shrink-0">
              <X aria-hidden />
            </Button>
          )}
        </div>
        {children}
        {footer && <div className="flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
