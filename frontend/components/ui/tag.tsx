import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Small label (Verified, Connected, Token expired). Soft fill, 1px line, readable text.
const tagVariants = cva(
  "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-md border px-2 py-0.5 text-micro font-medium",
  {
    variants: {
      variant: {
        neutral: "border-border bg-surface text-ink-2",
        brand: "border-brand-line bg-brand-tint text-brand-ink",
        success: "border-success-line bg-success-soft text-success",
        warning: "border-warning-line bg-warning-soft text-warning",
        danger: "border-danger-line bg-danger-soft text-danger",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

type TagVariant = "neutral" | "brand" | "success" | "warning" | "danger";
/** @deprecated Old names. "muted" and "dashed" are now "neutral". Use "warning" or "danger" for failures. */
type DeprecatedTagVariant = "muted" | "dashed";

export const TAG_ALIAS: Record<DeprecatedTagVariant, TagVariant> = {
  muted: "neutral",
  dashed: "neutral",
};

export function resolveTagVariant(variant: TagVariant | DeprecatedTagVariant | null | undefined): TagVariant {
  if (!variant) return "neutral";
  return variant in TAG_ALIAS ? TAG_ALIAS[variant as DeprecatedTagVariant] : (variant as TagVariant);
}

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: TagVariant | DeprecatedTagVariant;
}

export function Tag({ className, variant, ...props }: TagProps) {
  return <span className={cn(tagVariants({ variant: resolveTagVariant(variant) }), className)} {...props} />;
}
