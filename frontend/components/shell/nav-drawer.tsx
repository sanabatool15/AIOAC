"use client";
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FOCUSABLE, lockScroll, nextFocusIndex, unlockScroll } from "@/components/ui/modal-stack";

// Navigation drawer for screens narrower than `lg`. A modal dialog: Esc and the dark area close it, Tab stays inside,
// the page behind does not scroll, and focus goes back to the button that opened it.
export function NavDrawer({
  id,
  open,
  onClose,
  children,
}: {
  id: string;
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  });

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    lockScroll(document.body);
    const el = panel.current;
    (el?.querySelector<HTMLElement>("[data-autofocus]") ?? el)?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented) {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab" || !el) return;
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const at = items.indexOf(document.activeElement as HTMLElement);
      if (at < 0 || (e.shiftKey && at === 0) || (!e.shiftKey && at === items.length - 1)) {
        e.preventDefault();
        items[nextFocusIndex(at, items.length, e.shiftKey)].focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      unlockScroll(document.body);
      if (opener?.isConnected) opener.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-40 bg-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        id={id}
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
        className="relative flex h-full w-72 max-w-[85vw] flex-col bg-surface shadow-drawer outline-none"
      >
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close navigation"
          data-autofocus
          onClick={onClose}
          className="absolute right-2 top-2 z-10"
        >
          <X aria-hidden />
        </Button>
        {children}
      </div>
    </div>
  );
}
