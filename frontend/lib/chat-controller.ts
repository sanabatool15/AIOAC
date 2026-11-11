// State of the persistent project chat (one thread per project, shown on every step).
// No React in here, so it is easy to test. Cost rules (the model costs money):
//   - ONE POST /chat per user action (send, Approve, Send my goal again). Nothing retries by itself.
//   - While a turn runs, GET /activity is polled every 2 s (free, no model call) to show the steps live. It never POSTs,
//     never overlaps itself, ignores its own errors, and stops when the turn ends.
//   - Opening the page reads the stored messages (a GET). The goal is sent only on the first visit of a new project.
//   - Approve is a click: it sends {approve: [card.tool]} and no message. "Not now" sends nothing.
//   - After a reply the project is read again (a GET) so the page picks the step from the server status.
import { declineKey, loadDeclined, saveDeclined, type KV } from "./declined";
import {
  bootChat,
  chatError,
  fromStored,
  getActivity,
  getMessages,
  itemsFromReply,
  postChat,
  userItem,
  type ChatCard,
  type ChatItem,
  type ActivityLine,
  type ChatReply,
  type FriendlyError,
  type StoredMessage,
} from "./chat";

export interface ChatState {
  items: ChatItem[] | null; // null while the history loads
  busy: boolean;
  error: FriendlyError | null;
  busySince: number | null; // when the current /chat call started (ms), for the thinking timer
  declined: string[]; // keys of the cards the user answered with "Not now" (kept in this browser, see declined.ts)
  unavailable: boolean; // 503: the AI assistant is not set up, so the input is hidden
  lastSteps: string[]; // the steps of the turn that just finished, kept so the thread can show what the assistant did
  liveSteps: string[]; // plain lines of what the assistant is doing right now (newest last, at most MAX_LIVE); empty when idle
}

export const POLL_MS = 2000;
export const MAX_LIVE = 5;
const HIDDEN_KINDS = new Set(["you", "reply"]); // the user's own words and the final reply are already in the thread

export interface ChatDeps {
  boot: (projectId: string, goal: string, sendGoal: boolean, onGoalSent?: (goal: ChatItem) => void) => ReturnType<typeof bootChat>;
  getMessages: (projectId: string) => Promise<StoredMessage[]>;
  getActivity: (projectId: string) => Promise<ActivityLine[]>;
  postChat: (projectId: string, body: { message?: string; approve?: string[]; choice?: boolean }) => Promise<ChatReply>;
}

export const liveDeps: ChatDeps = { boot: bootChat, getMessages, getActivity, postChat };

export class ChatController {
  private state: ChatState = { items: null, busy: true, busySince: null, error: null, declined: [], unavailable: false, liveSteps: [], lastSteps: [] };
  private listeners = new Set<() => void>();
  private opened = false;
  private sending = false;
  private timer: ReturnType<typeof setInterval> | null = null;
  private polling = false; // a GET /activity is in flight: the next tick is skipped
  private pollRun = 0; // changes on every start/stop, so a late answer of an old poll is thrown away

  constructor(
    readonly projectId: string,
    private goal: string,
    private onChanged: () => void | Promise<void>,
    private deps: ChatDeps = liveDeps,
    private store?: KV | null, // undefined = this browser's localStorage
  ) {}

  // The screen reloads the project with a function that changes between renders; keep the latest one.
  setOnChanged(fn: () => void | Promise<void>) {
    this.onChanged = fn;
  }

  getState = (): ChatState => this.state;
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  };
  private set(patch: Partial<ChatState>) {
    this.state = { ...this.state, ...patch };
    this.listeners.forEach((l) => l());
  }

  // Poll the activity feed while a turn runs. The browser clock is never used: the feed's own length when the turn
  // starts is the baseline (the feed is oldest first and only grows), and only lines after it are shown.
  private startPoll() {
    this.stopPoll();
    const run = ++this.pollRun;
    let baseline: number | null = null;
    const once = () => {
      if (this.polling) return; // never two at once
      this.polling = true;
      this.deps
        .getActivity(this.projectId)
        .then((lines) => {
          if (run !== this.pollRun) return; // the turn ended while this was on its way
          if (baseline === null) {
            baseline = lines.length; // what was already there before this turn
            return;
          }
          const fresh = lines
            .slice(baseline)
            .filter((l) => !HIDDEN_KINDS.has(l.kind))
            .map((l) => l.text)
            .slice(-MAX_LIVE);
          const same = fresh.length === this.state.liveSteps.length && fresh.every((t, i) => t === this.state.liveSteps[i]);
          if (!same) this.set({ liveSteps: fresh });
        })
        .catch(() => {}) // e.g. SQLite "database is locked" for a moment: say nothing, try again in 2 s
        .finally(() => {
          this.polling = false;
        });
    };
    once(); // the baseline, taken at once from the server's own feed
    this.timer = setInterval(once, POLL_MS);
  }

  // The screen is leaving: stop the timer and drop any answer still on its way.
  dispose() {
    this.stopPoll();
  }

  private stopPoll() {
    this.pollRun++;
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    this.polling = false;
  }

  // Open the thread once. `status` is the project status: only a brand-new project ("described") sends its goal.
  async open(status: string): Promise<void> {
    if (this.opened) return;
    this.opened = true;
    this.set({ declined: this.store === undefined ? loadDeclined(this.projectId) : loadDeclined(this.projectId, this.store) });
    // The goal is sent right away on a new project; show it and start the thinking timer from that first second.
    let b: Awaited<ReturnType<ChatDeps["boot"]>>;
    try {
      b = await this.deps.boot(this.projectId, this.goal, status === "described", (goalItem) => {
        const now = Date.now();
        this.set({ items: [goalItem], busy: true, busySince: now });
        this.startPoll();
      });
    } finally {
      this.stopPoll();
    }
    this.set({ items: b.items, error: b.error, unavailable: !!b.error?.unavailable, busy: false, busySince: null, liveSteps: [], lastSteps: this.state.liveSteps.length ? this.state.liveSteps : this.state.lastSteps });
    if (b.items.some((i) => i.role === "assistant") ) void this.onChanged();
  }

  private async turn(body: { message?: string; approve?: string[]; choice?: boolean }, shown?: ChatItem): Promise<void> {
    if (this.sending) return; // a second click while one call is in flight does nothing
    this.sending = true;
    const since = Date.now();
    this.set({ busy: true, busySince: since, error: null, items: shown ? [...(this.state.items ?? []), shown] : this.state.items });
    this.startPoll();
    try {
      const r = await this.deps.postChat(this.projectId, body);
      this.set({ items: [...(this.state.items ?? []), ...itemsFromReply(r)] });
      await this.onChanged(); // a GET: the status may have changed (data chosen, quote made, ...)
    } catch (e) {
      const f = chatError(e);
      this.set({ error: f, unavailable: f.unavailable ? true : this.state.unavailable });
    } finally {
      this.sending = false;
      this.stopPoll();
      this.set({ busy: false, busySince: null, liveSteps: [], lastSteps: this.state.liveSteps.length ? this.state.liveSteps : [] });
    }
  }

  // A click on an answer button the model offered. The server marks it so it never counts as the user's own typed words
  // (target accuracy, "I have no data"); it is still shown as the user's message.
  choose(text: string): Promise<void> {
    const t = text.trim();
    if (!t || this.sending) return Promise.resolve();
    return this.turn({ message: t, choice: true }, userItem(t));
  }

  send(text: string): Promise<void> {
    const t = text.trim();
    if (!t || this.sending) return Promise.resolve();
    return this.turn({ message: t }, userItem(t));
  }

  // Only a click calls this. The action name is the card's own tool name (specs/api.md A2).
  approve(card: ChatCard): Promise<void> {
    return this.turn({ approve: [card.tool] });
  }

  // "Not now": nothing is sent. The choice is remembered so a reload shows the same calm state.
  decline(itemId: string): void {
    const key = declineKey(this.state.items ?? [], itemId);
    if (!key || this.state.declined.includes(key)) return;
    const declined = [...this.state.declined, key];
    this.set({ declined });
    if (this.store === undefined) saveDeclined(this.projectId, declined);
    else saveDeclined(this.projectId, declined, this.store);
  }

  isDeclined(itemId: string): boolean {
    const key = declineKey(this.state.items ?? [], itemId);
    return !!key && this.state.declined.includes(key);
  }

  // The goal went out but no answer came back: the user chooses to send it again.
  sendGoalAgain(): Promise<void> {
    this.set({ items: [] });
    return this.turn({ message: this.goal }, userItem(this.goal));
  }

  // 409 "still working": a GET only. Picks up the reply of a turn that was still running.
  async checkAgain(): Promise<void> {
    const since = Date.now();
    this.set({ busy: true, busySince: since });
    this.startPoll();
    try {
      const m = await this.deps.getMessages(this.projectId);
      this.set({ items: m.length > 0 ? m.map(fromStored) : this.state.items, error: null });
      await this.onChanged();
    } catch (e) {
      this.set({ error: chatError(e) });
    } finally {
      this.stopPoll();
      this.set({ busy: false, busySince: null, liveSteps: [] });
    }
  }

  // The goal went out and nothing answered (error, not a busy/503): offer "Send my goal again".
  goalUnanswered(): boolean {
    const { error, items } = this.state;
    return !!error && !error.busy && !error.unavailable && items?.length === 1 && items[0].role === "user";
  }
}
