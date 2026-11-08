export interface TabItem {
  id: string;
  label: string;
  disabled?: boolean;
}

/** Which tab a key moves to. Wraps around, skips disabled tabs. Returns null for other keys. */
export function nextTabId(tabs: TabItem[], currentId: string, key: string): string | null {
  const enabled = tabs.filter((t) => !t.disabled);
  if (enabled.length === 0) return null;
  const at = enabled.findIndex((t) => t.id === currentId);
  switch (key) {
    case "ArrowRight":
    case "ArrowDown":
      return enabled[(at + 1) % enabled.length].id;
    case "ArrowLeft":
    case "ArrowUp":
      return enabled[(at <= 0 ? enabled.length : at) - 1].id;
    case "Home":
      return enabled[0].id;
    case "End":
      return enabled[enabled.length - 1].id;
    default:
      return null;
  }
}
