import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

export const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-[10px] text-sm font-medium leading-5 whitespace-nowrap transition-[filter,background-color] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary:
          "bg-brand-gradient text-white shadow-btn-primary hover:brightness-105",
        outline:
          "border border-border bg-white text-ink shadow-btn-neutral hover:bg-surface",
        destructive:
          "bg-danger-gradient text-white shadow-btn-danger hover:brightness-105",
        icon: "bg-white text-ink-2 hover:bg-surface",
      },
      size: {
        default: "px-2.5 py-1.5",
        md: "rounded-lg px-3.5 py-2 font-semibold leading-[normal]",
        action: "rounded-lg px-[22px] py-3 font-semibold leading-[normal]",
        lg: "w-full rounded-lg px-[22px] py-3 font-semibold leading-[normal]",
        icon: "min-h-8 min-w-8 p-2",
      },
    },
    defaultVariants: { variant: "primary", size: "default" },
  },
);

export interface ButtonProps
  extends
    React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";
