import { Circle, CircleCheck, LoaderCircle } from "lucide-react";
import type { StepStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const config = {
  done: { Icon: CircleCheck, className: "text-success", label: "Done" },
  running: {
    Icon: LoaderCircle,
    className: "text-brand motion-safe:animate-spin",
    label: "In progress",
  },
  pending: { Icon: Circle, className: "text-pending", label: "Pending" },
} as const;

// Never color alone: shape differs (check / spinner / empty circle) and there is a screen-reader label.
export function StatusIcon({
  status,
  size = 18,
  className,
}: {
  status: StepStatus;
  size?: number;
  className?: string;
}) {
  const { Icon, className: tone, label } = config[status];
  return (
    <>
      <Icon
        aria-hidden
        size={size}
        className={cn("shrink-0", tone, className)}
      />
      <span className="sr-only">{label}</span>
    </>
  );
}
