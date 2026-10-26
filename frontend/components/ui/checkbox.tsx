"use client";
import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

interface CheckboxProps {
  id: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  children: React.ReactNode;
  quiet?: boolean; // neutral border (confirm dialogs) instead of the brand border
}

// Native checkbox (keyboard + screen readers) with the Figma 18px box.
export function Checkbox({
  id,
  checked,
  onCheckedChange,
  children,
  quiet,
}: CheckboxProps) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-center gap-2.5 text-sm leading-[normal] text-ink"
    >
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(e) => onCheckedChange(e.target.checked)}
        className="peer sr-only"
      />
      <span
        aria-hidden
        className={cn(
          "flex size-[18px] shrink-0 items-center justify-center rounded-[5px] border peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand",
          quiet ? "border-border" : "border-brand",
          checked ? "bg-brand text-white" : "bg-white",
        )}
      >
        {checked && <Check size={12} strokeWidth={3} />}
      </span>
      {children}
    </label>
  );
}
