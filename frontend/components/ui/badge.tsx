import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center justify-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-semibold leading-4",
  {
    variants: {
      variant: {
        secondary: "bg-secondary text-secondary-fg",
        brand: "border border-brand-edge bg-brand-tint text-brand-ink",
        solid: "bg-brand text-white",
        outline: "border border-border bg-white text-ink",
      },
    },
    defaultVariants: { variant: "secondary" },
  },
);

export interface BadgeProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
