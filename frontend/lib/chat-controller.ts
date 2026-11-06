// State of the persistent project chat (one thread per project, shown on every step).
// No React in here, so it is easy to test. Cost rules (the model costs money):
//   - ONE POST /chat per user action (send, Approve, Send my goal again). Nothing polls, nothing retries by itself.
//   - Opening the page reads the stored messages (a GET). The goal is sent only on the first visit of a new project.
//   - Approve is a click: it sends {approve: [card.tool]} and no message. "Not now" sends nothing.
//   - After a reply the project is read again (a GET) so the page picks the step from the server status.
import {
  bootChat,
  chatError,
  fromStored,
  getMessages,
  itemsFromReply,
  postChat,
  userItem,
  type ChatCard,
  type ChatItem,
  type ChatReply,
  type FriendlyError,
  type StoredMessage,
} from "./chat";

export interface ChatState {
  items: ChatItem[] | null; // null while the history loads
  busy: boolean;
  error: FriendlyError | null;
  declined: boolean; // the user pressed "Not now" on the last card
  unavailable: boolean; // 503: the AI assistant is not set up, so the input is hidden
}

export interface ChatDeps {
  boot: (projectId: string, goal: string, sendGoal: boolean) => ReturnType<typeof bootChat>;
  getMessages: (projectId: string) => Promise<StoredMessage[]>;
  postChat: (projectId: string, body: { message?: string; approve?: string[] }) => Promise<ChatReply>;
}

export const liveDeps: ChatDeps = { boot: bootChat, getMessages, postChat };

export class ChatController {
  private state: ChatState = { items: null, busy: true, error: null, declined: false, unavailable: false };
  private listeners = new Set<() => void>();
  private opened = false;
  private sending = false;

  constructor(
    readonly projectId: string,
    private goal: string,
    private onChanged: () => void | Promise<void>,
    private deps: ChatDeps = liveDeps,
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

  // Open the thread once. `status` is the project status: only a brand-new project ("described") sends its goal.
  async open(status: string): Promise<void> {
    if (this.opened) return;
    this.opened = true;
    const b = await this.deps.boot(this.projectId, this.goal, status === "described");
    this.set({ items: b.items, error: b.error, unavailable: !!b.error?.unavailable, busy: false });
    if (b.items.some((i) => i.role === "assistant") ) void this.onChanged();
  }

  private async turn(body: { message?: string; approve?: string[] }, shown?: ChatItem): Promise<void> {
    if (this.sending) return; // a second click while one call is in flight does nothing
    this.sending = true;
    this.set({ busy: true, error: null, items: shown ? [...(this.state.items ?? []), shown] : this.state.items });
    try {
      const r = await this.deps.postChat(this.projectId, body);
      this.set({ items: [...(this.state.items ?? []), ...itemsFromReply(r)], declined: false });
      await this.onChanged(); // a GET: the status may have changed (data chosen, quote made, ...)
    } catch (e) {
      const f = chatError(e);
      this.set({ error: f, unavailable: f.unavailable ? true : this.state.unavailable });
    } finally {
      this.sending = false;
      this.set({ busy: false });
    }
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

  decline(): void {
    this.set({ declined: true });
  }

  // The goal went out but no answer came back: the user chooses to send it again.
  sendGoalAgain(): Promise<void> {
    this.set({ items: [] });
    return this.turn({ message: this.goal }, userItem(this.goal));
  }

  // 409 "still working": a GET only. Picks up the reply of a turn that was still running.
  async checkAgain(): Promise<void> {
    this.set({ busy: true });
    try {
      const m = await this.deps.getMessages(this.projectId);
      this.set({ items: m.length > 0 ? m.map(fromStored) : this.state.items, error: null });
      await this.onChanged();
    } catch (e) {
      this.set({ error: chatError(e) });
    } finally {
      this.set({ busy: false });
    }
  }

  // The goal went out and nothing answered (error, not a busy/503): offer "Send my goal again".
  goalUnanswered(): boolean {
    const { error, items } = this.state;
    return !!error && !error.busy && !error.unavailable && items?.length === 1 && items[0].role === "user";
  }
}
