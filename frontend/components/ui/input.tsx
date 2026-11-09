import * as React from "react";
import { cn } from "@/lib/utils";

// Every text control shows the same visible focus: brand border plus a soft ring.
const control =
  "w-full rounded-md border border-border bg-card px-3.5 py-2.5 text-body text-ink outline-none placeholder:text-muted focus-visible:border-brand focus-visible:ring-2 focus-visible:ring-brand-edge aria-[invalid=true]:border-danger disabled:opacity-50";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(control, className)} {...props} />
));
Input.displayName = "Input";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(control, "resize-y", className)} {...props} />
));
Textarea.displayName = "Textarea";

/**
 * A box that holds an input plus buttons (the chat composer). The inner input
 * should drop its own border; the whole box shows focus through `focus-within`.
 */
export function FieldShell({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("field-shell", className)} {...props} />;
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: React.ReactNode;
  htmlFor: string;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="flex w-full flex-col gap-1.5">
      <label htmlFor={htmlFor} className="text-small font-medium text-ink-2">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-small text-muted">{hint}</p>}
      {error && <p className="text-small text-danger">{error}</p>}
    </div>
  );
}
