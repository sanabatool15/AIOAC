// Real-backend calls for the demo path. One function per endpoint the screens use (specs/api.md section A).
// The only data path of the app: calls to the FastAPI backend (login, projects, payments).
import {
  api,
  ApiError,
  detailMessage,
  type BAccountPayment,
  type BActivityItem,
  type BUsage,
  type BFixProposal,
  type BFixResult,
  type BForecast,
  type BBatch,
  type BHistory,
  type BPublicResult,
  type BShare,
  type BModel,
  type BModelVersion,
  type BPredict,
  type BOrder,
  type BProject,
  type BQuote,
  type BReceipt,
  type BTraining,
} from "./api";
import { API_BASE_URL } from "./config";
import { clearRealUser, setRealUser, type SessionUser } from "./session";

// ---- small browser memory (never the source of truth; every value can be recovered from the server) ----
const PAY_KEY = "aioac.pay"; // sessionStorage: {paymentId, projectId}, kept across the PayPal round trip
const LAST_KEY = "aioac.lastProject"; // localStorage: last project id, to recover after storage loss

interface PayMemory {
  paymentId: string;
  projectId: string;
}

export function rememberPayment(m: PayMemory) {
  try {
    sessionStorage.setItem(PAY_KEY, JSON.stringify(m));
  } catch {
    /* storage blocked: recovered from the server instead */
  }
  rememberProject(m.projectId);
}
export function recallPayment(): PayMemory | null {
  try {
    const m = JSON.parse(sessionStorage.getItem(PAY_KEY) ?? "null") as PayMemory | null;
    return m && m.paymentId && m.projectId ? m : null;
  } catch {
    return null;
  }
}
export function forgetPayment() {
  try {
    sessionStorage.removeItem(PAY_KEY);
  } catch {
    /* ignore */
  }
}
export function rememberProject(id: string) {
  try {
    localStorage.setItem(LAST_KEY, id);
  } catch {
    /* ignore */
  }
}
export function recallProject(): string | null {
  try {
    return localStorage.getItem(LAST_KEY);
  } catch {
    return null;
  }
}

// ---- projects ----
export async function startChat(text: string): Promise<{ id: string }> {
  const r = await api<{ id: string; status: string }>("/projects", { body: { goal: text } });
  rememberProject(r.id);
  return { id: r.id };
}
// Testing shortcut: a chat already at the price step. The server answers 404 unless demo chats are switched on.
export async function startDemoChat(): Promise<{ id: string }> {
  const r = await api<{ id: string; status: string }>("/projects/demo", { method: "POST" });
  rememberProject(r.id);
  return { id: r.id };
}
export const getProject = (id: string) => api<BProject>(`/projects/${id}`);
export const listProjects = () =>
  api<{ id: string; goal: string; status: string; created_at: string }[]>("/projects");

// ---- project detail (specs/api.md section D) ----
export const getHistory = (id: string) => api<BHistory>(`/projects/${id}/history`);
export const getActivity = (id: string) => api<BActivityItem[]>(`/projects/${id}/activity`);

// ---- account totals (specs/api.md section D) ----
export const getUsage = () => api<BUsage>("/account/usage");
export const getAccountPayments = () => api<BAccountPayment[]>("/account/payments");

// ---- sharing: the owner side needs login, the public page does not ----
export const getShare = (id: string) => api<BShare>(`/projects/${id}/share`);
export const createShare = (id: string) =>
  api<{ token: string; url_path: string; created_at: string }>(`/projects/${id}/share`, { method: "POST" });
export const revokeShare = (id: string) =>
  api<{ enabled: boolean }>(`/projects/${id}/share`, { method: "DELETE" });
export const getPublicResult = (token: string) =>
  api<BPublicResult>(`/public/results/${encodeURIComponent(token)}`);

// ---- the trained model (free: no gate, no money) ----
// `modelId` picks a saved version; leave it out for the version in use.
const withModel = (path: string, modelId?: string) => (modelId ? `${path}?model_id=${encodeURIComponent(modelId)}` : path);
export const getModel = (id: string, modelId?: string) => api<BModel>(withModel(`/projects/${id}/model`, modelId));
export const getModelVersions = (id: string) => api<BModelVersion[]>(`/projects/${id}/model/versions`);
export const switchModelVersion = (id: string, modelId: string) =>
  api<{ model_id: string; version_no: number; is_current: boolean }>(`/projects/${id}/model/${encodeURIComponent(modelId)}/use`, { method: "POST" });
export const predictOne = (id: string, record: Record<string, string | number | null>, modelId?: string) =>
  api<BPredict>(withModel(`/projects/${id}/predict`, modelId), { body: { record } });
export const predictBatch = (id: string, csvText: string, modelId?: string) =>
  api<BBatch>(withModel(`/projects/${id}/predict-batch`, modelId), { body: { csv_text: csvText } });
// The saved model as a file. Returns the bytes and the scikit-learn version it needs (from X-Requires-Scikit-Learn).
export async function downloadModel(id: string, modelId?: string): Promise<{ blob: Blob; sklearn: string | null; filename: string }> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${withModel(`/projects/${id}/model/download`, modelId)}`, { credentials: "include" });
  } catch {
    throw new ApiError("We could not reach the server. Check that it is running, then try again.", 0);
  }
  if (!res.ok) {
    let body: unknown = null;
    try {
      body = await res.json();
    } catch {
      /* not JSON */
    }
    throw new ApiError(detailMessage(body, res.status), res.status);
  }
  const cd = res.headers.get("Content-Disposition") ?? "";
  const filename = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? `model-${id.slice(0, 8)}.joblib`;
  return { blob: await res.blob(), sklearn: res.headers.get("X-Requires-Scikit-Learn"), filename };
}

// ---- data, checks, free test ----
export const uploadCsv = (id: string, name: string, csvText: string) =>
  api<{ candidate_id: string; rows: number }>(`/projects/${id}/data`, {
    body: { name, csv_text: csvText },
  });
// A pasted Hugging Face, UCI or OpenML page address. The server refuses every other address (specs/api.md A0).
export const addDatasetLink = (id: string, url: string) =>
  api<{ candidate_id: string; rows: number; columns: string[]; suggested_target?: string }>(`/projects/${id}/data/link`, {
    body: { url },
  });
// `target` is left out for groups and unusual records: they have no answer column.
export const selectDataset = (id: string, candidateId: string, target?: string) =>
  api<{ rows: number; target: string | null; status: string }>(
    `/projects/${id}/data/${candidateId}/select`,
    { body: target ? { target } : {} },
  );
// What kind of prediction this is. Free, and only before a dataset is chosen.
export const setTaskType = (id: string, taskType: string) =>
  api<{ task_type: string; plain_name: string; needs_target: boolean; pays_success_fee: boolean }>(
    `/projects/${id}/task-type`,
    { body: { task_type: taskType } },
  );
export const runReadiness = (id: string) =>
  api<{ grade: string; findings: { kind: string; text: string }[]; status: string }>(
    `/projects/${id}/readiness`,
    { method: "POST" },
  );
export const runBaseline = (id: string) =>
  api<{ accuracy: number; simple_guess_accuracy: number; trust_level: string; status: string }>(
    `/projects/${id}/baseline`,
    { method: "POST" },
  );

// ---- pilot, forecast, quote ----
// A yes/no or group answer sends a target (0 to 1). A number or a forecast sends the most the user accepts being off by,
// in the answer's own units; the server turns it into a score. Groups and unusual records send nothing.
export const runPilot = (id: string, goal: number | { typicalError: number } | null) =>
  api<BForecast>(`/chats/${id}/pilot`, {
    body: goal === null ? {} : typeof goal === "number" ? { target: goal } : { typical_error: goal.typicalError },
    timeoutMs: 150_000, // the free pilot is bounded; if nothing came back by now, show a plain message instead of spinning forever
  });
// A guided data fix. Propose is free and changes nothing; apply is the user's click.
export const proposeFix = (id: string) => api<BFixProposal>(`/chats/${id}/fix/propose`, { method: "POST" });
export const applyFix = (id: string, versionId: string) =>
  api<BFixResult>(`/chats/${id}/fix/apply`, { body: { version_id: versionId } });
export const createQuote = (id: string) =>
  api<BQuote>(`/agreements/${id}/quote`, { method: "POST" });
const approveQuote = (id: string) =>
  api<{ approved: boolean; cap_cents: number }>(`/projects/${id}/quote/approve`, {
    method: "POST",
  });

// ---- payment ----
export const createOrder = (projectId: string) =>
  api<BOrder>("/payments/orders", { body: { project_id: projectId } });
export const authorizePayment = (paymentId: string) =>
  api<{ held: boolean; state: string }>(`/payments/${paymentId}/authorize`, { method: "POST" });
export const getProjectPayment = (projectId: string) =>
  api<BReceipt>(`/projects/${projectId}/payment`);
export const retrySettle = (projectId: string) =>
  api<{ payment_state: string; status: string }>(`/projects/${projectId}/settle/retry`, {
    method: "POST",
  });

// "Pay": approve the quote, create the hold order, remember the ids, then go to PayPal.
// Returns the PayPal link; the screen sends the browser there. Nothing is charged by this step.
export async function startPayment(projectId: string): Promise<string> {
  await approveQuote(projectId);
  const order = await createOrder(projectId);
  rememberPayment({ paymentId: order.payment_id, projectId });
  if (!order.approve_url) {
    throw new ApiError("PayPal did not give us a link to continue. Nothing was charged. Please try again.", 502);
  }
  return order.approve_url;
}

// Find payment + project ids after a PayPal return, even if sessionStorage was lost.
export async function recoverPayment(): Promise<PayMemory | null> {
  const mem = recallPayment();
  if (mem) return mem;
  let pid = recallProject();
  if (!pid) {
    const all = await listProjects();
    pid = all.find((p) => p.status === "awaiting_payment" || p.status === "paid")?.id ?? null;
  }
  if (!pid) return null;
  try {
    const r = await getProjectPayment(pid);
    return { paymentId: r.payment_id, projectId: pid };
  } catch {
    return null;
  }
}

// ---- training ----
export const startTraining = (id: string) =>
  api<{ run_id: string; status: string }>(`/projects/${id}/train`, { method: "POST" });
export const getTraining = (id: string) => api<BTraining>(`/projects/${id}/training`);
export const stopTraining = (id: string) =>
  api<{ run_id: string; stop_requested: boolean }>(`/projects/${id}/training/stop`, {
    method: "POST",
  });
export const cancelHold = (id: string) =>
  api<{ payment_state: string; status: string }>(`/projects/${id}/cancel`, { method: "POST" });

// ---- login (specs/api.md auth section). The cookie is httpOnly; the browser keeps no token. ----
export function authMessage(e: unknown): string {
  if (!(e instanceof ApiError)) return "Something went wrong. Please try again.";
  switch (e.status) {
    case 401:
      return "Wrong email or password.";
    case 409:
      return "That email is already registered. Try logging in instead.";
    case 422:
      return "Use a valid email and a password of at least 8 characters.";
    case 429:
      return "Too many tries. Wait a few minutes, then try again.";
    case 503:
      return "Login is not set up on this server yet.";
    case 404:
      return "That sign-in option is not available on this server.";
    default:
      return e.message;
  }
}
async function enter(path: string, body: unknown): Promise<{ user: SessionUser }> {
  try {
    const r = await api<{ user: SessionUser }>(path, { method: "POST", body });
    setRealUser(r.user);
    return r;
  } catch (e) {
    throw new Error(authMessage(e));
  }
}
export const login = (email: string, password: string) => enter("/auth/login", { email, password });
export const signup = (email: string, password: string) => enter("/auth/signup", { email, password });
export const demoLogin = () => enter("/auth/demo", {});
export async function logout(): Promise<{ ok: boolean }> {
  try {
    return await api<{ ok: boolean }>("/auth/logout", { method: "POST" });
  } finally {
    clearRealUser(); // even if the call failed, this browser forgets the user
  }
}
// Who is signed in? Updates the session state; null when signed out. A network failure leaves the state unknown.
export async function me(): Promise<SessionUser | null> {
  try {
    const r = await api<{ user: SessionUser }>("/auth/me");
    setRealUser(r.user);
    return r.user;
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      clearRealUser();
      return null;
    }
    throw e;
  }
}
