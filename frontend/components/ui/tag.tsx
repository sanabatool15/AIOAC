import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// Small rounded label (FOUND, Connected, COMING SOON, Token expired).
const tagVariants = cva(
  "inline-flex shrink-0 items-center overflow-clip whitespace-nowrap rounded-[10px] px-2.5 py-1 text-xs font-semibold leading-[normal]",
  {
    variants: {
      variant: {
        brand: "bg-brand-gradient text-white",
        success: "bg-success-gradient text-white",
        muted: "border border-border bg-surface text-muted",
        dashed: "border border-dashed border-border bg-surface text-muted",
      },
    },
    defaultVariants: { variant: "muted" },
  },
);

export interface TagProps
  extends
    React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof tagVariants> {}

export function Tag({ className, variant, ...props }: TagProps) {
  return (
    <span className={cn(tagVariants({ variant }), className)} {...props} />
  );
}
