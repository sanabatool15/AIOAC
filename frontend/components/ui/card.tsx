import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// violet = plan/summary, blue = running/ETA, peach = money, mint = receipts,
// green = verified, red = failure, amber = warning. Most cards stay plain (white).
const cardVariants = cva("flex w-full flex-col rounded-xl border shadow-card", {
  variants: {
    variant: {
      plain: "border-border bg-card",
      violet: "surface-violet",
      blue: "surface-blue",
      peach: "surface-peach",
      mint: "surface-mint",
      green: "surface-green",
      red: "surface-red",
      amber: "surface-amber",
    },
  },
  defaultVariants: { variant: "plain" },
});

export interface CardProps
  extends
    React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {}

export function Card({ className, variant, ...props }: CardProps) {
  return (
    <div
      className={cn(cardVariants({ variant }), "gap-3.5 p-5", className)}
      {...props}
    />
  );
}
