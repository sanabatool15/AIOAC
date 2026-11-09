import * as React from "react";
import Link from "next/link";
import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

const baseButtonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded-md text-body font-medium whitespace-nowrap transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-grad-brand text-on-brand shadow-btn-primary hover:brightness-95",
        outline: "border border-border bg-card text-ink shadow-btn-neutral hover:bg-surface",
        ghost: "bg-transparent text-ink-2 hover:bg-surface hover:text-ink",
        destructive: "bg-danger text-on-brand hover:brightness-95",
      },
      size: {
        sm: "h-8 px-3 text-small",
        md: "h-9 px-4",
        lg: "h-11 px-5 text-section",
        icon: "size-9 p-0",
      },
      block: { true: "w-full", false: "" },
    },
    defaultVariants: { variant: "primary", size: "md", block: false },
  },
);

type Variant = "primary" | "outline" | "ghost" | "destructive";
type Size = "sm" | "md" | "lg" | "icon";

interface StyleProps {
  /** @deprecated "icon" is now "ghost". Migrate the call site. */
  variant?: Variant | "icon";
  /** @deprecated "default" is now "sm" or "md", "action" is now "lg". Migrate the call site. */
  size?: Size | "default" | "action";
  /** Full width. Replaces the old full-width `size="lg"`. */
  block?: boolean;
}

// Old names keep working and map onto the new scale (listed in docs/ui-pass-notes.md).
const VARIANT_ALIAS: Record<string, Variant> = { icon: "ghost" };
const SIZE_ALIAS: Record<string, Size> = { default: "sm", action: "lg" };

export function resolveButtonStyle({ variant, size, block }: StyleProps) {
  const v = (variant && (VARIANT_ALIAS[variant] ?? variant)) as Variant | undefined;
  const s = (size && (SIZE_ALIAS[size] ?? size)) as Size | undefined;
  return { variant: v ?? "primary", size: s ?? "md", block: block ?? false };
}

/** Class string for anything styled as a button. Prefer `LinkButton` for links. */
export function buttonVariants(props: StyleProps = {}) {
  return baseButtonVariants(resolveButtonStyle(props));
}

function classes(props: StyleProps, className?: string) {
  return cn(buttonVariants(props), className);
}

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, StyleProps {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, block, type = "button", ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={classes({ variant, size, block }, className)}
      {...props}
    />
  ),
);
Button.displayName = "Button";

export interface LinkButtonProps
  extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href">, StyleProps {
  href: string;
}

/** A link that looks like a button. Internal paths use the router, everything else a plain anchor. */
export function LinkButton({ href, className, variant, size, block, target, rel, ...props }: LinkButtonProps) {
  const cls = classes({ variant, size, block }, className);
  const internal = href.startsWith("/") && !href.startsWith("//") && !props.download && target !== "_blank";
  if (internal) return <Link href={href} className={cls} {...props} />;
  const safeRel = target === "_blank" ? (rel ?? "noopener noreferrer") : rel;
  return <a href={href} target={target} rel={safeRel} className={cls} {...props} />;
}
