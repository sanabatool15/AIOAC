"use client";
import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
} from "react";
import { CircleCheck, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error";
interface ToastItem {
  id: number;
  text: string;
  tone: ToastTone;
}

const ToastContext = createContext<
  ((text: string, tone?: ToastTone) => void) | null
>(null);

export function useToast() {
  const show = useContext(ToastContext);
  if (!show) throw new Error("useToast must be used inside <ToastProvider>");
  return show;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const show = useCallback((text: string, tone: ToastTone = "success") => {
    const id = nextId.current++;
    setItems((list) => [...list, { id, text, tone }]);
    setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 4000);
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-6 z-[60] flex flex-col items-center gap-2"
      >
        {items.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto flex items-center gap-2 rounded-xl border bg-card px-4 py-2.5 text-sm font-medium text-ink shadow-card",
              t.tone === "error" ? "border-danger" : "border-border",
            )}
          >
            {t.tone === "error" ? (
              <TriangleAlert aria-hidden size={16} className="text-danger" />
            ) : (
              <CircleCheck aria-hidden size={16} className="text-success" />
            )}
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
