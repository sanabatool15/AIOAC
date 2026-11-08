"use client";
import { createContext, useCallback, useContext, useRef, useState } from "react";
import { CircleCheck, TriangleAlert, X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error";
interface ToastItem {
  id: number;
  text: string;
  tone: ToastTone;
}

const ToastContext = createContext<((text: string, tone?: ToastTone) => void) | null>(null);

export function useToast() {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside <ToastProvider>");
  return show;
}

function ToastCard({ item, onClose }: { item: ToastItem; onClose: () => void }) {
  const error = item.tone === "error";
  return (
    <div
      className={cn(
        "pointer-events-auto flex max-w-[calc(100vw-2rem)] items-center gap-2 rounded-lg border bg-card px-4 py-2.5 text-body font-medium text-ink shadow-popover motion-safe:animate-toast-in",
        error ? "border-danger-line" : "border-border",
      )}
    >
      {error ? (
        <TriangleAlert aria-hidden className="size-4 shrink-0 text-danger" />
      ) : (
        <CircleCheck aria-hidden className="size-4 shrink-0 text-success" />
      )}
      <span>{item.text}</span>
      {error && (
        <button type="button" aria-label="Dismiss" onClick={onClose} className="-mr-1 rounded-sm p-1 text-muted hover:text-ink">
          <X aria-hidden className="size-4" />
        </button>
      )}
    </div>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const close = useCallback((id: number) => setItems((list) => list.filter((t) => t.id !== id)), []);

  const show = useCallback(
    (text: string, tone: ToastTone = "success") => {
      const id = nextId.current++;
      setItems((list) => [...list, { id, text, tone }]);
      // errors stay longer: people need time to read them
      setTimeout(() => close(id), tone === "error" ? 8000 : 4000);
    },
    [close],
  );

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-6 z-[60] flex flex-col items-center gap-2">
        {/* two live regions: errors are announced at once, other messages politely */}
        <div role="status" aria-live="polite" className="flex flex-col items-center gap-2">
          {items.filter((t) => t.tone !== "error").map((t) => (
            <ToastCard key={t.id} item={t} onClose={() => close(t.id)} />
          ))}
        </div>
        <div role="alert" className="flex flex-col items-center gap-2">
          {items.filter((t) => t.tone === "error").map((t) => (
            <ToastCard key={t.id} item={t} onClose={() => close(t.id)} />
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  );
}
