import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const chipVariants = cva(
  "inline-flex items-center whitespace-nowrap px-3.5 py-[7px] text-sm font-medium leading-[normal] transition-[filter,background-color] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        outline:
          "rounded-2xl border border-border bg-white text-ink shadow-btn-neutral hover:bg-surface",
        primary:
          "rounded-[20px] bg-brand-gradient text-white shadow-btn-primary hover:brightness-105",
      },
    },
    defaultVariants: { variant: "outline" },
  },
);

export interface ChipProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof chipVariants> {}

export function Chip({
  className,
  variant,
  type = "button",
  ...props
}: ChipProps) {
  return (
    <button
      type={type}
      className={cn(chipVariants({ variant }), className)}
      {...props}
    />
  );
}
