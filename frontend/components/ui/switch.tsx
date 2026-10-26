import { cn } from "@/lib/utils";

interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  size?: "sm" | "lg"; // lg = 40x22 (share dialog)
  disabled?: boolean;
}

export function Switch({
  checked,
  onCheckedChange,
  label,
  size = "sm",
  disabled,
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        size === "lg" ? "h-[22px] w-10" : "h-3.5 w-6",
        "relative shrink-0 disabled:opacity-50 rounded-full transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand",
        checked ? "bg-brand" : "bg-switch-off",
      )}
    >
      <span
        className={cn(
          "absolute rounded-full bg-white transition-all",
          size === "lg"
            ? cn(
                "top-[2px] size-[18px]",
                checked ? "right-[2px]" : "left-[2px]",
              )
            : cn("top-px h-3 w-3", checked ? "right-[1.5px]" : "left-px"),
        )}
      />
    </button>
  );
}
