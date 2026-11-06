// "Not now" on an approval card must survive a reload. Kept in this browser (localStorage), per project, in try/catch:
// without storage everything still works, the card just asks again after a reload. No network, no model call.
import type { ChatCard, ChatItem } from "./chat";

export interface KV {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserStore(): KV | null {
  try {
    return typeof localStorage === "undefined" ? null : localStorage;
  } catch {
    return null;
  }
}

const storageKey = (projectId: string) => `aioac.declined.${projectId}`;

export function loadDeclined(projectId: string, kv: KV | null = browserStore()): string[] {
  try {
    const raw = kv?.getItem(storageKey(projectId));
    const v: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

export function saveDeclined(projectId: string, keys: string[], kv: KV | null = browserStore()): void {
  try {
    kv?.setItem(storageKey(projectId), JSON.stringify(keys));
  } catch {
    /* storage full or blocked: the choice just lasts until the page is reloaded */
  }
}

// What a card is about: the tool and the dataset (or its arguments). Not the message id: a card that arrives in a reply
// gets a temporary id, and after a reload it has the stored one.
function cardKey(card: ChatCard): string {
  const id = card.args?.candidate_id;
  return `${card.tool}:${typeof id === "string" ? id : JSON.stringify(card.args ?? {})}`;
}

// A stable key for one card in the thread: its subject plus how many cards about the same subject came before it,
// so asking again about the same dataset later gives a NEW card that is not already "declined".
export function declineKey(items: ChatItem[], itemId: string): string | null {
  const seen = new Map<string, number>();
  for (const it of items) {
    if (!it.card) continue;
    const k = cardKey(it.card);
    const n = seen.get(k) ?? 0;
    seen.set(k, n + 1);
    if (it.id === itemId) return `${k}#${n}`;
  }
  return null;
}
