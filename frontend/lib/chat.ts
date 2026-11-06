// Chat on the describe step (real mode). Pure logic plus three endpoint calls (specs/api.md section A2).
// Cost rule: ONE POST /chat per user action. Nothing here polls, retries or resends on its own.
import { api, ApiError } from "./api";

// Set by the server for select_dataset (null fields when the candidate is unknown). Absent on other cards.
export interface CardDetail {
  name: string | null;
  source: string | null;
  rows: number | null;
  columns: number | null;
  license: string | null;
  target: string | null;
  target_meaning?: string | null; // optional: what the answer column means in plain words (may be absent)
}

export interface ChatCard {
  what: string;
  level: number;
  tool: string;
  args: Record<string, unknown>;
  detail?: CardDetail | null;
}

// A dataset name that is only an id ("350", "uci:350", "hf:...", a long hex id) tells the user nothing.
export function looksLikeId(name: string): boolean {
  const n = name.trim();
  return !n || /^\d+$/.test(n) || /^(hf|uci|oml|openml|kaggle|local|sample|bundled):/i.test(n) || /^[0-9a-f]{16,}$/i.test(n);
}

// Title of the approval card: the dataset name, or the card's own plain sentence when the name is missing or an id.
export function cardTitle(card: ChatCard): string {
  const n = card.detail?.name;
  return n && !looksLikeId(n) ? n.trim() : card.what;
}

// The small facts grid under the title. Only facts the server sent; License is always there ("not stated" if unknown).
export function cardFacts(card: ChatCard): { label: string; value: string; note?: string }[] {
  const d = card.detail;
  if (!d || d.name === null) return [];
  const out: { label: string; value: string; note?: string }[] = [];
  if (d.source) out.push({ label: "Source", value: d.source });
  if (d.rows !== null) out.push({ label: "Rows", value: d.rows.toLocaleString("en-US") });
  if (d.columns !== null) out.push({ label: "Columns", value: String(d.columns) });
  if (d.target) out.push({ label: "Answer column", value: d.target, note: d.target_meaning?.trim() || undefined });
  out.push({ label: "License", value: d.license || "not stated" });
  return out;
}

// Typed blocks built by the server from tool results (specs/api.md A2). Unknown types are ignored by the screen.
export type ChatBlock =
  | { type: "readiness"; grade: string; findings: { kind: string; text: string }[]; trust: string | null }
  | { type: "baseline"; accuracy: number; simple_guess_accuracy: number; trust: string | null }
  | {
      type: "quote";
      quote_id: string;
      estimate_cents: number;
      low_cents: number;
      high_cents: number;
      cap_cents: number;
      success_fee_cents: number;
      is_estimate: boolean;
    }
  | { type: "pay"; payment_id: string; approve_url: string | null; hold_cents: number }
  | { type: string; [k: string]: unknown };

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  kind: string; // chat | note | card
  blocks: ChatBlock[];
  card?: ChatCard;
  created_at?: string;
}

export interface ChatReply {
  status: "reply" | "awaiting_approval" | "limit" | "error";
  text: string;
  card: ChatCard | null;
  blocks: ChatBlock[];
}

export interface ChatItem {
  id: string;
  role: "user" | "assistant";
  text: string;
  card?: ChatCard;
  blocks: ChatBlock[];
}

export const getMessages = (projectId: string) =>
  api<StoredMessage[]>(`/projects/${projectId}/messages`);

// The only function that talks to the model. `approve` carries the card's tool name and nothing else.
export const postChat = (projectId: string, body: { message?: string; approve?: string[] }) =>
  api<ChatReply>(`/projects/${projectId}/chat`, { body });

export function fromStored(m: StoredMessage): ChatItem {
  return { id: m.id, role: m.role, text: m.text, card: m.kind === "card" ? m.card : undefined, blocks: m.blocks ?? [] };
}

let seq = 0;
const localId = () => `local-${++seq}`;

// Items to add after a turn: the assistant's words and, if one is waiting, its approval card.
export function itemsFromReply(r: ChatReply): ChatItem[] {
  const out: ChatItem[] = [];
  if (r.text?.trim() || r.blocks?.length) {
    out.push({ id: localId(), role: "assistant", text: r.text ?? "", blocks: r.blocks ?? [] });
  }
  if (r.card) out.push({ id: localId(), role: "assistant", text: r.card.what, card: r.card, blocks: [] });
  return out;
}
export const userItem = (text: string): ChatItem => ({ id: localId(), role: "user", text, blocks: [] });

// A card still waits for the user only if it is the last thing said and the project has not moved on.
export function pendingCard(items: ChatItem[], projectStatus: string): ChatItem | null {
  if (projectStatus !== "described") return null;
  const last = items[items.length - 1];
  return last?.card ? last : null;
}

export interface FriendlyError {
  text: string;
  unavailable?: boolean; // the assistant is not set up: fall back to the upload form
  busy?: boolean; // a turn is already running: wait, do not resend
}

export function chatError(e: unknown): FriendlyError {
  if (e instanceof ApiError) {
    if (e.status === 503) {
      return { text: "The AI assistant is not set up on this server yet. You can still upload your own CSV file.", unavailable: true };
    }
    if (e.status === 409) {
      return { text: "The assistant is still working on your last message. Give it a moment, then check again.", busy: true };
    }
    if (e.status === 0) return { text: e.message };
    if (e.status >= 500) return { text: "The assistant had a problem. Nothing was charged. Please try again." };
    return { text: e.message };
  }
  return { text: "Something went wrong. Please try again." };
}

export interface Boot {
  items: ChatItem[];
  error: FriendlyError | null;
}

// First visit: read the stored messages (a GET). Only if there are none, send the goal ONCE.
// Two calls for the same project at the same time (React strict mode, a quick remount) share one promise.
const booting = new Map<string, Promise<Boot>>();
// `sendGoal` is false on later steps: an empty history there is not a reason to talk to the model.
export function bootChat(projectId: string, goal: string, sendGoal = true): Promise<Boot> {
  const running = booting.get(projectId);
  if (running) return running;
  const p = (async (): Promise<Boot> => {
    let stored: StoredMessage[];
    try {
      stored = await getMessages(projectId);
    } catch (e) {
      return { items: [], error: chatError(e) };
    }
    if (stored.length > 0) return { items: stored.map(fromStored), error: null };
    if (!sendGoal) return { items: [], error: null };
    const first = userItem(goal);
    try {
      const r = await postChat(projectId, { message: goal });
      return { items: [first, ...itemsFromReply(r)], error: null };
    } catch (e) {
      // No retry here. The user decides (the screen offers a button).
      return { items: [first], error: chatError(e) };
    }
  })().finally(() => booting.delete(projectId));
  booting.set(projectId, p);
  return p;
}
