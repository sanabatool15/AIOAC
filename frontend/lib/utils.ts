import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// tailwind-merge must know our token names, or it treats `text-title` as a
// colour and drops it next to `text-ink` (and the same for shadows and widths).
const twMerge = extendTailwindMerge({
  extend: {
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
