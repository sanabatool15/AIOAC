import { cva } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Colour carries meaning, never position: success = verified or done, warning =
// needs attention, danger = failed, highlight = the one thing to look at.
const cardVariants = cva("flex w-full flex-col rounded-xl border shadow-card", {
  variants: {
    variant: {
      plain: "border-border bg-card",
      success: "border-success-line bg-success-soft",
      warning: "border-warning-line bg-warning-soft",
      danger: "border-danger-line bg-danger-soft",
      highlight: "border-brand-line bg-brand-soft",
    },
  },
  defaultVariants: { variant: "plain" },
});

type CardVariant = "plain" | "success" | "warning" | "danger" | "highlight";
/** @deprecated Old pastel names. They map to the new variants, see CARD_ALIAS. Migrate the call site. */
type DeprecatedCardVariant = "violet" | "blue" | "peach" | "mint" | "green" | "red" | "amber";

// violet = plan, so highlight. blue, peach and mint carried position only, so plain.
export const CARD_ALIAS: Record<DeprecatedCardVariant, CardVariant> = {
  violet: "highlight",
  blue: "plain",
  peach: "plain",
  mint: "plain",
  green: "success",
  red: "danger",
  amber: "warning",
};

export function resolveCardVariant(variant: CardVariant | DeprecatedCardVariant | null | undefined): CardVariant {
  if (!variant) return "plain";
  return variant in CARD_ALIAS ? CARD_ALIAS[variant as DeprecatedCardVariant] : (variant as CardVariant);
}

export interface CardProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "color"> {
  variant?: CardVariant | DeprecatedCardVariant;
}

export function Card({ className, variant, ...props }: CardProps) {
  return (
    <div
      className={cn(cardVariants({ variant: resolveCardVariant(variant) }), "gap-3.5 p-5", className)}
      {...props}
    />
  );
}
