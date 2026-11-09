import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge must know our token names, or it treats `text-title` as a
// colour and drops it next to `text-ink` (and the same for shadows and widths).
const twMerge = extendTailwindMerge({
  extend: {
    // gradient tokens are background images, not colours, so they must not replace a bg colour (or the reverse)
    classGroups: {
      "bg-image": [{ bg: ["grad-brand", "grad-brand-x", "grad-card", "grad-live", "grad-money", "grad-trace", "grad-trace-head"] }],
    },
    theme: {
      text: ["title", "section", "body", "small", "micro"],
      shadow: ["card", "popover", "drawer", "card-tight", "composer", "glow", "btn-primary", "btn-danger", "btn-neutral", "menu"],
      container: ["chat", "form", "page"],
    },
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
