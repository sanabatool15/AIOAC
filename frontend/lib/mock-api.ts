// Typed mock API. Function names mirror the planned backend client (see specs/frontend-integration.md).
// Dev helper: add ?mock=error | empty | slow to any URL to see those states.
import type {
  Agreement,
  AgreementOffer,
  AgreementTarget,
  ApiKey,
  BaselineRun,
  Budget,
  BatchResult,
  ProjectDetail,
  UsagePlan,
  PlanId,
  PlanOffer,
  BillingCycle,
  PayPlanInput,
  BillingData,
  BillingDetails,
  PaymentMethodsData,
  PlanReceipt,
  BudgetBreakdown,
  Chat,
  Job,
  KeyDetail,
  KeyProvider,
  LiveView,
  Message,
  ResearchRun,
  ShareRole,
  ShareState,
  Shell,
  PredictionInput,
  PredictionResult,
  PublicResult,
  ResultRun,
  TrainingRun,
  VerifiedRun,
} from "./types";
import { setFirstRun, setSession } from "./session";
import { API_BASE_URL, USE_MOCK_API } from "./config";

export class ApiError extends Error {
  retryable: boolean;
  constructor(message: string, retryable = true) {
    super(message);
    this.retryable = retryable;
  }
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

function mockMode(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("mock");
}

async function respond<T>(data: T): Promise<T> {
  if (!USE_MOCK_API) {
    throw new ApiError(
      `Real backend mode (${API_BASE_URL}) is not connected yet. Set NEXT_PUBLIC_USE_MOCK_API=true.`,
      false,
    );
  }
  const mode = mockMode();
  await sleep(mode === "slow" ? 2500 : 250);
  if (mode === "error") throw new ApiError("We could not reach the server.");
  return structuredClone(data);
}

const job1: Job = {
  id: "job-1",
  title: "Experiment 1",
  state: "running",
  stepIndex: 4,
  totalSteps: 6,
  steps: [
    {
      id: "s1",
      label: "Checked your data",
      status: "done",
      meta: "1 min",
      tool: "tools",
    },
    {
      id: "s2",
      label: "Baseline model: about 71% right when flagged",
      status: "done",
      meta: "3 min",
      tool: "training",
    },
    {
      id: "s3",
      label: "PayPal hold placed: $40.00",
      status: "done",
      meta: "now",
      tool: "payment",
    },
    {
      id: "s4",
      label: "Training model",
      status: "running",
      meta: "6 to 9 min left",
      tool: "training",
    },
    {
      id: "s5",
      label: "Verify on a locked test set",
      status: "pending",
      tool: "training",
    },
    {
      id: "s6",
      label: "Charge or release the hold",
      status: "pending",
      tool: "payment",
    },
  ],
  tools: {
    tools: "idle",
    browser: "idle",
    research: "idle",
    training: "running",
    payment: "idle",
  },
  eta: { minLow: 6, minHigh: 9, finishLabel: "11:42 PM", progress: 0.4 },
  stages: [
    { name: "Queued", status: "done" },
    { name: "Provision", status: "done" },
    { name: "Prepare", status: "done" },
    { name: "Training", status: "running" },
    { name: "Evaluate", status: "pending" },
    { name: "Save", status: "pending" },
  ],
  hold: {
    maxUsd: 40,
    note: "You are charged only if the independent test passes.",
    parts: [
      {
        id: "p1",
        label: "Experiment 1",
        tone: "primary",
        capUsd: 14,
        note: "up to $14 · $9.80 used",
      },
      {
        id: "p2",
        label: "Experiment 2",
        tone: "next",
        capUsd: 14,
        note: "locked until justified",
      },
      {
        id: "p3",
        label: "Safety buffer",
        tone: "buffer",
        capUsd: 12,
        note: "$12 · never spent by the AI",
      },
    ],
  },
  targets: [
    { metric: "Right when flagged", baseline: 71.0, target: 80 },
    { metric: "Leavers caught", baseline: 54.2, target: 60, qualifier: "min" },
  ],
  files: [
    {
      id: "f1",
      name: "churn_sample.csv",
      detail: "7,043 rows · read",
      kind: "data",
    },
    {
      id: "f2",
      name: "train_split.csv",
      detail: "5,634 rows · in use",
      kind: "data",
    },
    {
      id: "f3",
      name: "test_locked.csv",
      detail: "1,409 rows · answers hidden",
      kind: "data",
      locked: true,
    },
    {
      id: "f4",
      name: "baseline_model.pkl",
      detail: "Created by the free baseline",
      kind: "model",
    },
  ],
  links: [
    {
      id: "l1",
      url: "huggingface.co/datasets/telco-churn",
      detail: "Read via your HF token",
      access: "Read",
    },
    {
      id: "l2",
      url: "kaggle.com/datasets/blastchar/telco",
      detail: "Synced 2 min ago",
      access: "Read",
    },
  ],
};

const baselineRun: BaselineRun = {
  stepIndex: 2,
  totalSteps: 6,
  steps: [
    { id: "b1", label: "Read churn_sample.csv · 7,043 rows", seconds: 2 },
    { id: "b2", label: "Check data quality and leakage", seconds: 4 },
    { id: "b3", label: "Train free baseline", seconds: 9 },
  ],
  readiness: {
    grade: "B",
    title: "Data readiness: good to train",
    detail: "2% missing values, mild class imbalance. No leakage found.",
    tag: "Eligible for pay-on-success",
  },
  result: { precision: 71, recall: 58, targetPrecision: 80 },
};

const baselineMessages: Message[] = [
  {
    id: "bl-u",
    role: "user",
    text: "Predict which customers may stop buying next month.",
  },
  {
    id: "bl-a1",
    role: "agent",
    text: "On it. I will check your data first, then train a free baseline so you can see what is realistic before committing anything.",
    blocks: ["steps", "readiness"],
  },
  {
    id: "bl-a2",
    role: "agent",
    text: "Baseline is ready. It catches 58% of customers who really leave, and 71% of the customers it flags really do leave.",
    blocks: ["result"],
  },
];

const researchRun: ResearchRun = {
  stepIndex: 5,
  totalSteps: 8,
  steps: [
    {
      id: "r1",
      label: "Open Hugging Face dataset card",
      state: "done",
      meta: "4s",
    },
    {
      id: "r2",
      label: "Read benchmark results for churn tasks",
      state: "run",
      meta: "running",
    },
    { id: "r3", label: "Compare with your target", state: "pending" },
  ],
  tools: {
    tools: "idle",
    browser: "running",
    research: "running",
    training: "done",
    payment: "idle",
  },
};

const liveView: LiveView = {
  url: "huggingface.co/datasets/telco-churn",
  pageTitle: "Telco Customer Churn",
  lineWidths: [418, 352, 396, 264],
  highlight: "Typical result for this dataset: about 78 to 84 out of 100",
  notes: [
    "Public results reach about 78 to 84 out of 100.",
    "Your target is possible but not guaranteed.",
    "Catching more leavers usually means more wrong flags.",
  ],
  tools: researchRun.tools,
};

// GET /jobs/{id}/browser
export function getLiveView(chatId: string) {
  void chatId;
  return respond<LiveView>(liveView);
}

const trainingRun: TrainingRun = {
  stepIndex: 5,
  totalSteps: 8,
  precisionNow: 75,
  targetPrecision: 80,
  series: [59.7, 65.6, 70, 72.8, 75],
  eta: {
    headline: "about 7 to 10 min",
    detail: "Started 22:41 · estimated finish 22:55 · range narrows as it runs",
    progress: 42,
  },
  stages: [
    { id: "t1", label: "Queued", state: "done", time: "0:20" },
    { id: "t2", label: "Provisioning compute", state: "done", time: "0:48" },
    { id: "t3", label: "Preparing data", state: "done", time: "1:10" },
    { id: "t4", label: "Training", state: "run", time: "4:20 of about 9:00" },
    { id: "t5", label: "Evaluating", state: "pending", time: "about 1:00" },
    { id: "t6", label: "Saving results", state: "pending", time: "about 0:30" },
  ],
  tools: {
    tools: "done",
    browser: "idle",
    research: "idle",
    training: "running",
    payment: "idle",
  },
  decision:
    "Continue, change strategy, or stop. Based on gap to target, budget left and last gain. Backend approves any spend.",
};

const verifiedRun: VerifiedRun = {
  stepIndex: 7,
  totalSteps: 8,
  outcome: "met",
  heading: "Target met on locked test data",
  metrics: [
    {
      id: "precision",
      label: "RIGHT WHEN FLAGGED",
      value: 82.4,
      ruleLabel: "target 80%",
      met: true,
    },
    {
      id: "recall",
      label: "LEAVERS CAUGHT",
      value: 63.1,
      ruleLabel: "minimum 60%",
      met: true,
    },
  ],
  testSetNote: "Locked test set of 1,409 customers · tested once · no retries",
  tools: {
    tools: "done",
    browser: "idle",
    research: "idle",
    training: "done",
    payment: "running",
  },
  steps: [
    { id: "v1", label: "Experiment 1", state: "done" },
    { id: "v2", label: "Experiment 2 not needed", state: "done" },
    { id: "v3", label: "Verify on locked test set", state: "done" },
    { id: "v4", label: "Capture payment", state: "run" },
    { id: "v5", label: "Deliver model and receipt", state: "pending" },
  ],
  payment: {
    capturedUsd: 18.6,
    heldUsd: 40,
    releasedUsd: 21.4,
    note: "Release time depends on PayPal.",
  },
};

const missedRun: VerifiedRun = {
  stepIndex: 7,
  totalSteps: 8,
  outcome: "missed",
  heading: "Target not reached",
  metrics: [
    {
      id: "precision",
      label: "RIGHT WHEN FLAGGED",
      value: 77.9,
      ruleLabel: "target 80%",
      met: false,
    },
    {
      id: "recall",
      label: "LEAVERS CAUGHT",
      value: 61.2,
      ruleLabel: "minimum 60%",
      met: true,
    },
  ],
  testSetNote: "Locked test set of 1,409 customers · tested once · no retries",
  tools: {
    tools: "done",
    browser: "idle",
    research: "idle",
    training: "done",
    payment: "done",
  },
  steps: [
    { id: "x1", label: "Experiments 1 and 2", state: "done" },
    { id: "x2", label: "Verify on locked test set", state: "done" },
    { id: "x3", label: "Void PayPal hold", state: "done" },
    { id: "x4", label: "Save best model to project", state: "done" },
  ],
  banner: "Target missed. You pay only the compute used, no success fee. The rest of the hold was released.",
  bestModel: {
    title: "Best model so far: v1",
    tag: "SAVED IN PROJECT",
    detail:
      "about 77.9% right when flagged. It stays in your project until you delete it. Download unlocks once a target is met.",
  },
  recap: {
    heldUsd: 40,
    chargedUsd: 0,
    releasedUsd: 40,
    note: "Release timing depends on PayPal and your payment method.",
  },
};

const resultRun: ResultRun = {
  stepIndex: 8,
  totalSteps: 8,
  tools: {
    tools: "done",
    browser: "idle",
    research: "idle",
    training: "done",
    payment: "done",
  },
  defaults: { contract: "Month-to-month", months: 5, monthlyCharge: 79 },
  initial: {
    probability: 82,
    reasons: ["month-to-month contract", "short time as a customer"],
  },
  receipt: [
    { id: "r1", label: "PayPal hold", value: "$40.00" },
    { id: "r2", label: "Captured", value: "$18.60 (actual compute)" },
    { id: "r3", label: "Released", value: "$21.40" },
    {
      id: "r4",
      label: "Target / result",
      value: "P 80% / 82.4%, R 60% / 63.1%",
    },
    { id: "r5", label: "Experiments", value: "1 run, 0 retries" },
    { id: "r6", label: "PayPal reference", value: "SANDBOX-XXXXXXXX" },
  ],
  note: "Good to know: works best on customers similar to your data. About 1 in 5 flagged customers may not leave.",
  canDownloadModel: true,
  model: {
    name: "Model v1",
    badge: "VERIFIED",
    summary: "about 82.4% right when flagged · 4.1 MB",
    apiLines: [
      "POST https://api.aioac.app/v1/models/churn-8f2a/predict",
      "Authorization: Bearer YOUR_KEY",
      '{ "contract": "month-to-month", "tenure": 4 }',
    ],
    keyOn: true,
    usage: "0 calls this month · 1,000 free calls on Starter",
  },
  ways: [
    "Try one customer in chat",
    "Upload a CSV and get predictions back",
    "Call the API from your own app",
  ],
};

const agreementOffer: AgreementOffer = {
  stepIndex: 3,
  totalSteps: 6,
  baselinePrecision: 71,
  tiers: [
    { id: "safe", label: "SAFE", precision: 76, minRecall: 55, maxUsd: 25 },
    {
      id: "recommended",
      label: "RECOMMENDED",
      precision: 80,
      minRecall: 60,
      maxUsd: 40,
    },
    {
      id: "ambitious",
      label: "AMBITIOUS",
      precision: 85,
      minRecall: 65,
      maxUsd: 70,
    },
  ],
};

const shell: Shell = {
  user: {
    name: "David",
    email: "mwmfigma@gmail.com",
    plan: "Starter plan",
    usage: "2 of 3 projects used",
  },
  projects: [
    {
      id: "churn",
      name: "Churn prediction",
      dataFiles: 2,
      models: 2,
      status: "running",
      subtitle: "Experiment 1 · 12 min ago",
      members: 1,
      chats: [
        { id: "baseline", title: "Baseline run" },
        { id: "exp-1", title: "Experiment 1" },
        { id: "feature-check", title: "Feature check" },
      ],
    },
    {
      id: "loan",
      name: "Loan repayment",
      chats: [],
      status: "done",
      subtitle: "Target met · yesterday",
      members: 2,
    },
    {
      id: "lead",
      name: "Lead scoring",
      chats: [],
      status: "done",
      subtitle: "Target missed · model kept",
      members: 1,
    },
  ],
  sources: [
    { id: "hf", name: "Hugging Face", status: "Connected" },
    { id: "kaggle", name: "Kaggle", status: "Connected" },
    { id: "uploads", name: "Uploads", status: "3 files" },
  ],
  keys: [
    { id: "k1", name: "HF read token", enabled: true },
    { id: "k2", name: "Kaggle key", enabled: true },
    { id: "k3", name: "OpenRouter", enabled: false },
  ],
};

// GET /me + /budget + /projects + /integrations + /keys (combined for the sidebar)
export function getShell() {
  const sources = shell.sources.map((s) =>
    s.id === "uploads" ? { ...s, status: getUploadsLabel() } : s,
  );
  const user = {
    ...shell.user,
    plan: `${planOffers.find((p) => p.id === readPlan())!.name} plan`,
  };
  return respond({ ...shell, user, sources });
}

// GET /budget (per active chat in the mock; real API returns the account budget)
export function getBudget(chatId: string | null) {
  const budget: Budget =
    chatId === "round2"
      ? {
          headline: "Hold voided · $0",
          heldUsd: 0,
          usedUsd: 0,
          progress: 22,
          label: "New hold not placed yet",
        }
      : chatId === "ineligible"
        ? {
            headline: "Nothing held",
            heldUsd: 0,
            usedUsd: 0,
            label: "Quote not available yet",
          }
        : chatId === "exp-1" || chatId === "budget"
          ? {
              headline: "Held $40 · Used $9.80",
              heldUsd: 0,
              usedUsd: 0,
              progress: 22,
              label: "Experiment 1 running",
            }
          : chatId === "result" || chatId === "use-model"
            ? {
                headline: "Captured $18.60",
                heldUsd: 0,
                usedUsd: 0,
                progress: 22,
                label: "Released $21.40 · Done",
              }
            : chatId === "missed"
              ? {
                  headline: "Target missed · no success fee",
                  heldUsd: 0,
                  usedUsd: 0,
                  progress: 22,
                  label: "Target not met",
                }
              : chatId === "verified"
                ? {
                    headline: "Capturing $18.60 of $40",
                    heldUsd: 0,
                    usedUsd: 0,
                    progress: 22,
                    label: "Target met",
                  }
                : chatId === "page"
                  ? {
                      headline: "No funds held",
                      heldUsd: 0,
                      usedUsd: 0,
                      label: "You always pay for the compute used; the success fee applies only if the target is verified",
                    }
                  : chatId === "research"
                    ? {
                        headline: "Held $40 · Used $0",
                        heldUsd: 0,
                        usedUsd: 0,
                        progress: 22,
                        label: "Researching",
                      }
                    : chatId === "training"
                      ? {
                          headline: "Held $40 · Used $3.40",
                          heldUsd: 0,
                          usedUsd: 0,
                          progress: 22,
                          label: "Experiment 1 running",
                        }
                      : chatId === "agreement"
                        ? {
                            headline: "Max $40 · not held yet",
                            heldUsd: 0,
                            usedUsd: 0,
                            label: "Nothing authorized",
                          }
                        : chatId === "agreement:pay"
                          ? {
                              headline: "Authorizing up to $40",
                              heldUsd: 0,
                              usedUsd: 0,
                              label: "Nothing charged",
                            }
                          : chatId === "baseline" ||
                              (chatId && createdChats[chatId]?.baseline)
                            ? {
                                headline: "Free baseline · $0",
                                heldUsd: 0,
                                usedUsd: 0,
                                label: "Nothing charged",
                              }
                            : {
                                heldUsd: 0,
                                usedUsd: 0,
                                label: "Free baseline first",
                              };
  return respond(budget);
}

// GET /budget/breakdown (null = nothing held for this chat)
export async function getBudgetBreakdown(chatId: string | null) {
  const active = ["exp-1", "budget", "training", "research"];
  if (!chatId || !active.includes(chatId))
    return respond<BudgetBreakdown | null>(null);
  return respond<BudgetBreakdown | null>({
    maxHeldUsd: 40,
    usedUsd: 9.8,
    chargedTodayUsd: 0,
    rows: [
      {
        id: "b0",
        title: "Free baseline",
        detail: "We cover this cost",
        amountLabel: "$0",
        allocationUsd: 0,
        state: "done",
      },
      {
        id: "b1",
        title: "Experiment 1",
        detail: "Up to $14 · used $9.80",
        amountLabel: "$14",
        allocationUsd: 14,
        state: "running",
      },
      {
        id: "b2",
        title: "Experiment 2",
        detail: "Only if justified",
        amountLabel: "$14",
        allocationUsd: 14,
        state: "locked",
      },
      {
        id: "b3",
        title: "Safety buffer",
        detail: "Unallocated, never auto-used",
        amountLabel: "$12",
        allocationUsd: 12,
        state: "reserved",
      },
    ],
    rule: "If target is met you pay the actual use, never above $40. If missed you pay only the compute used, no success fee, and the rest of the hold is released.",
    policy:
      "The backend sets every allocation. The AI can request more, never approve it.",
  });
}

// POST /jobs/{id}/cancel (voids the PayPal hold)
export async function stopJob(chatId: string) {
  await respond(null);
  return { chatId, holdVoided: true };
}

// PATCH /keys/{id}
export async function setKeyEnabled(id: string, enabled: boolean) {
  const r = await respond({ id, enabled });
  const k = keysDb.find((x) => x.id === id);
  if (k) k.enabled = enabled;
  const row = shell.keys.find((x) => x.id === id);
  if (row) row.enabled = enabled;
  return r;
}

// ---------- API keys (screen 17) ----------
const keysDb: ApiKey[] = [
  {
    id: "k1",
    name: "HF read token",
    provider: "huggingface",
    enabled: true,
    last4: "8f2a",
    projects: "all",
  },
  {
    id: "k2",
    name: "Kaggle key",
    provider: "kaggle",
    enabled: true,
    last4: "c91d",
    projects: ["Churn prediction", "Loan repayment"],
  },
  {
    id: "k3",
    name: "OpenRouter",
    provider: "openrouter",
    enabled: false,
    last4: "77b1",
    projects: ["Churn prediction"],
  },
];

// GET /keys
export function getKeys() {
  return respond<ApiKey[]>(structuredClone(keysDb));
}

const keyMeta: Record<
  string,
  { created: string; lastUsed: string; used: Record<string, string> }
> = {
  k1: {
    created: "Oct 20, 2026",
    lastUsed: "2 min ago by Churn prediction",
    used: {
      "Churn prediction": "Used 2 min ago",
      "Loan repayment": "Used yesterday",
      "Lead scoring": "Never used",
    },
  },
  k2: {
    created: "Oct 12, 2026",
    lastUsed: "yesterday by Loan repayment",
    used: {
      "Churn prediction": "Used 3 days ago",
      "Loan repayment": "Used yesterday",
    },
  },
  k3: { created: "Oct 3, 2026", lastUsed: "Never used", used: {} },
};

function detailFor(k: ApiKey): KeyDetail {
  const meta = keyMeta[k.id] ?? {
    created: "Today",
    lastUsed: "Never used",
    used: {},
  };
  return {
    ...structuredClone(k),
    createdLabel: meta.created,
    lastUsedLabel: meta.lastUsed,
    access: shell.projects.map((p) => ({
      project: p.name,
      usedLabel: meta.used[p.name] ?? "Never used",
      allowed: k.projects === "all" || k.projects.includes(p.name),
    })),
  };
}

// GET /keys/{id}
export async function getKeyDetail(id: string) {
  await respond(null);
  const k = keysDb.find((x) => x.id === id);
  if (!k) throw new ApiError("That key no longer exists.", false);
  return detailFor(k);
}

// PUT /keys/{id}/projects ("all" also covers projects created later)
export async function setKeyAccess(id: string, projects: "all" | string[]) {
  await respond(null);
  const k = keysDb.find((x) => x.id === id);
  if (!k) throw new ApiError("That key no longer exists.", false);
  k.projects = projects;
  return detailFor(k);
}

// POST /keys (the value is encrypted server side and never returned)
export async function addKey(input: {
  name: string;
  provider: KeyProvider;
  value: string;
}) {
  await respond(null);
  const name = input.name.trim();
  if (!name) throw new ApiError("Give the key a name.", false);
  if (/\s/.test(name))
    throw new ApiError("Names cannot contain spaces.", false);
  if (keysDb.some((k) => k.name.toLowerCase() === name.toLowerCase()))
    throw new ApiError("You already have a key with that name.", false);
  if (input.value.trim().length < 8)
    throw new ApiError(
      "That key looks too short. Paste the full value.",
      false,
    );
  const key: ApiKey = {
    id: `k-${Date.now().toString(36)}`,
    name,
    provider: input.provider,
    enabled: true,
    last4: input.value.trim().slice(-4),
    projects: "all",
  };
  keysDb.push(key);
  shell.keys.push({ id: key.id, name: key.name, enabled: true });
  return structuredClone(key);
}

// POST /keys/{id}/reveal (mock returns a fake value; the real API re-checks the session and audit-logs it)
export async function revealKey(id: string) {
  await respond(null);
  const k = keysDb.find((x) => x.id === id);
  if (!k) throw new ApiError("Key not found.", false);
  return { id, value: `mock_${k.provider}_key_••••${k.last4}` };
}

const createdChats: Record<string, Chat> = {};

// POST /projects/{id}/chats + POST /chats/{id}/messages (first prompt from the home screen)
export async function startChat(text: string, opts: { sample?: boolean } = {}) {
  await respond(null);
  const id = `chat-${Date.now().toString(36)}`;
  createdChats[id] = {
    id,
    title: "New chat",
    projectName: "Churn prediction",
    baseline: opts.sample ? baselineRun : undefined,
    messages: opts.sample
      ? baselineMessages.map((m, i) =>
          i === 0
            ? { ...m, id: `${id}-u`, text }
            : { ...m, id: `${id}-${m.id}` },
        )
      : [
          { id: `${id}-u`, role: "user", text },
          {
            id: `${id}-a`,
            role: "agent",
            text: opts.sample
              ? "I loaded the sample telco churn data. I will check it and train a free baseline first."
              : "Got it. Add your data (attach, paste a link or connect an account) and I will check it and train a free baseline first.",
          },
        ],
  };
  return { id };
}

// GET /chats/{id}/messages (+ job)
export function getChat(chatId: string) {
  if (createdChats[chatId]) return respond(createdChats[chatId]);
  if (chatId === "use-model") {
    return respond<Chat>({
      id: "use-model",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      result: resultRun,
      messages: [
        {
          id: "um-a1",
          role: "agent",
          text: "Your model passed. You can download it, call it from your own app, or predict for a whole file.",
          blocks: ["ways"],
        },
      ],
    });
  }
  if (chatId === "round2") {
    return respond<Chat>({
      id: "round2",
      title: "Experiment 1",
      projectName: "Churn prediction",
      round2: {
        changes: [
          "Add features: customer tenure groups and service usage",
          "Fix class imbalance with weighted training",
          "Same locked test set, so results stay comparable",
        ],
        round1: {
          label: "ROUND 1 (best)",
          value: "77.9% / 61.2%",
          note: "Missed target",
        },
        goal: {
          label: "ROUND 2 GOAL",
          value: "80% / 60%",
          note: "New agreement",
        },
        terms: [
          ["Target", "about 80% right when flagged"],
          ["New PayPal hold", "$25.00 max"],
          ["If target missed", "Compute used is charged, no success fee"],
          ["Your model v1", "Kept in project"],
        ],
        target: { precision: 80, minRecall: 60, maxUsd: 25 },
      },
      messages: [
        {
          id: "r2-a",
          role: "agent",
          text: "Round 2. Your best model so far is v1: about 77.9% right when flagged. Here is what I would change.",
          blocks: ["round2"],
        },
      ],
    });
  }
  if (chatId === "ineligible") {
    return respond<Chat>({
      id: "ineligible",
      title: "Experiment 1",
      projectName: "Churn prediction",
      ineligible: {
        checkedLabel: "CHECKED FREE",
        reasons: [
          "Dataset is 4.2 GB. Your Starter plan allows up to 500 MB.",
          "Estimated cost is above your $40 maximum.",
        ],
        options: [
          {
            id: "sample",
            title: "Use a smart 500 MB sample",
            detail: "Keeps the quote available.",
            recommended: true,
          },
          {
            id: "target",
            title: "Lower the target",
            detail: "about 74% right when flagged, max $40",
          },
          {
            id: "upgrade",
            title: "Upgrade to Pro",
            detail: "Allows 10 GB and a $200 maximum",
          },
        ],
        footnote: "You are never charged for this check.",
      },
      messages: [
        {
          id: "in-a",
          role: "agent",
          text: "I looked at your data and I cannot quote this one as it is. Here is why, and how to fix it.",
          blocks: ["ineligible"],
        },
      ],
    });
  }
  if (chatId === "agreement") {
    return respond<Chat>({
      id: "agreement",
      title: "Agreement",
      projectName: "Churn prediction",
      agreement: agreementOffer,
      messages: [
        {
          id: "ag-a",
          role: "agent",
          text: "Here is the deal. I suggest the Recommended target: realistic for your data and a clear step up from the baseline.",
          blocks: ["agreement"],
        },
      ],
    });
  }
  if (chatId === "result") {
    return respond<Chat>({
      id: "result",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      result: resultRun,
      messages: [
        {
          id: "rs-a1",
          role: "agent",
          text: "Your model is ready. It passed the locked test: about 82.4% right when flagged. Try it on one customer below.",
          blocks: ["prediction", "quick-replies"],
        },
      ],
    });
  }
  if (chatId === "missed") {
    return respond<Chat>({
      id: "missed",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      verified: missedRun,
      messages: [
        {
          id: "ms-a1",
          role: "agent",
          text: "Training finished. Here is the final check on data the model has never seen.",
          blocks: ["verification", "banner", "model"],
        },
      ],
    });
  }
  if (chatId === "verified") {
    return respond<Chat>({
      id: "verified",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      verified: verifiedRun,
      messages: [
        {
          id: "vf-a1",
          role: "agent",
          text: "Training finished. Now the final check on data the model has never seen.",
          blocks: ["verification"],
        },
        {
          id: "vf-a2",
          role: "agent",
          text: "Both conditions are met. Capturing the actual compute cost of $18.60. The rest of the hold is released.",
        },
      ],
    });
  }
  if (chatId === "training") {
    return respond<Chat>({
      id: "training",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      training: trainingRun,
      messages: [
        {
          id: "tr-a1",
          role: "agent",
          text: "Experiment 1 is training. The test score is climbing: 75% so far, target is 80%.",
          blocks: ["chart"],
        },
        {
          id: "tr-a2",
          role: "agent",
          text: "After this finishes I decide: continue, change strategy, or stop. I will explain why either way.",
        },
      ],
    });
  }
  if (chatId === "budget") {
    return respond<Chat>({
      id: "budget",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      activity: {
        stepIndex: 5,
        totalSteps: 8,
        steps: [
          {
            id: "a1",
            label: "Provision SageMaker training job",
            state: "done",
            meta: "48s",
          },
          {
            id: "a2",
            label: "Train model (Experiment 1)",
            state: "run",
            meta: "running",
          },
        ],
        tools: {
          tools: "done",
          browser: "idle",
          research: "idle",
          training: "running",
          payment: "idle",
        },
      },
      messages: [
        {
          id: "bd-a1",
          role: "agent",
          text: "Experiment 1 is running. Open the budget any time to see where the money can go.",
          blocks: ["research"],
        },
      ],
    });
  }
  if (chatId === "research") {
    return respond<Chat>({
      id: "research",
      title: "Experiment 1",
      projectName: "Churn prediction",
      job: job1,
      research: researchRun,
      messages: [
        {
          id: "rs-a1",
          role: "agent",
          text: "While Experiment 1 trains, I am checking similar public datasets to see what is realistic for your target.",
          blocks: ["research"],
        },
      ],
    });
  }
  if (chatId === "baseline") {
    return respond<Chat>({
      id: "baseline",
      title: "Baseline run",
      projectName: "Churn prediction",
      messages: baselineMessages,
      baseline: baselineRun,
    });
  }
  if (chatId !== "exp-1") {
    const title =
      shell.projects.flatMap((p) => p.chats).find((c) => c.id === chatId)
        ?.title ?? "New chat";
    return respond<Chat>({
      id: chatId,
      title,
      projectName: "Churn prediction",
      messages: [],
    });
  }
  const chat: Chat = {
    id: "exp-1",
    title: "Experiment 1",
    projectName: "Churn prediction",
    job: job1,
    messages: [
      {
        id: "m1",
        role: "user",
        text: "Train a churn model. I want at least 80% right when flagged, and I will pay up to $40.",
      },
      {
        id: "m2",
        role: "agent",
        text: "The free baseline was about 71% right when flagged. I placed your $40 PayPal hold and started Experiment 1. You can leave this page open or come back later.",
      },
    ],
  };
  if (mockMode() === "empty")
    return respond<Chat>({ ...chat, messages: [], job: undefined });
  return respond(chat);
}

// POST /chats/{id}/messages
export async function sendMessage(chatId: string, text: string) {
  await sleep(150);
  return { id: `m-${Date.now()}`, chatId, role: "user" as const, text };
}

// POST /auth/login | /auth/signup | /auth/oauth/{google|github} (dummy: any valid input signs in the demo user)
export async function login(email: string, password: string) {
  await respond(null);
  if (!email.includes("@") || password.length === 0)
    throw new ApiError("Enter a valid email and password.", false);
  setSession(true);
  return { user: shell.user };
}

export async function signup(email: string, password: string) {
  await respond(null);
  if (!email.includes("@"))
    throw new ApiError("Enter a valid email address.", false);
  if (password.length < 8)
    throw new ApiError("Use at least 8 characters for your password.", false);
  setSession(true);
  setFirstRun(true);
  return { user: shell.user };
}

export async function oauthLogin(provider: "google" | "github") {
  await respond(null);
  setSession(true);
  return { provider, user: shell.user };
}

// POST /auth/logout
export async function logout() {
  await respond(null);
  setSession(false);
  return { ok: true };
}

// POST /auth/forgot
export async function forgotPassword(email: string) {
  await respond(null);
  if (!email.includes("@"))
    throw new ApiError("Enter your email first.", false);
  return { ok: true };
}

// ---------- Add data (screens 3a / 3b / 3c) ----------
let uploadsCount = 3;

export function validateDataFile(file: File): string | null {
  if (!/\.(csv|parquet|xls|xlsx)$/i.test(file.name))
    return "Use a CSV, Parquet or Excel file.";
  if (file.size > 200 * 1024 * 1024) return "That file is over 200 MB.";
  return null;
}

// POST /uploads/presign -> PUT to S3 with progress (simulated here)
export async function uploadFile(
  file: File,
  onProgress: (pct: number) => void,
  signal: AbortSignal,
) {
  await respond(null);
  for (let p = 0; p < 100; p += 8) {
    if (signal.aborted) throw new DOMException("Aborted", "AbortError");
    onProgress(p);
    await sleep(120);
  }
  onProgress(100);
  return {
    id: `ds-${Date.now().toString(36)}`,
    name: file.name,
    sizeBytes: file.size,
  };
}

export interface DetectedDataset {
  provider: "huggingface" | "kaggle" | "url";
  title: string;
  subtitle: string;
  rows: string;
  columns: string;
  size: string;
  target: string;
}

// POST /projects/{id}/datasets/from-link (detect step). Stats are fixed demo values.
export async function detectLink(raw: string): Promise<DetectedDataset> {
  await respond(null);
  let u: URL;
  try {
    u = new URL(raw.trim());
  } catch {
    throw new ApiError("That does not look like a link.", false);
  }
  if (u.protocol !== "https:" && u.protocol !== "http:")
    throw new ApiError("That does not look like a link.", false);
  const parts = u.pathname.split("/").filter(Boolean);
  const demo = { rows: "7,043", columns: "21", size: "84 MB", target: "Churn" };
  if (
    u.hostname.endsWith("huggingface.co") &&
    parts[0] === "datasets" &&
    parts.length >= 3
  ) {
    return {
      provider: "huggingface",
      title: "Hugging Face dataset detected",
      subtitle: `${parts[1]}/${parts[2]} · public`,
      ...demo,
    };
  }
  if (
    u.hostname.endsWith("kaggle.com") &&
    parts[0] === "datasets" &&
    parts.length >= 3
  ) {
    return {
      provider: "kaggle",
      title: "Kaggle dataset detected",
      subtitle: `${parts[1]}/${parts[2]} · public`,
      ...demo,
    };
  }
  if (/\.(csv|parquet)$/i.test(u.pathname)) {
    return {
      provider: "url",
      title: "File link detected",
      subtitle: `${u.hostname}/${parts[parts.length - 1]}`,
      rows: "checked on add",
      columns: "checked on add",
      size: "unknown",
      target: "chosen next",
    };
  }
  throw new ApiError(
    "We could not find a dataset at that link. Try a Hugging Face, Kaggle or CSV/Parquet link.",
    false,
  );
}

// POST /projects/{id}/datasets (register)
export async function addDatasets(kind: "upload" | "link", count: number) {
  await respond(null);
  if (kind === "upload") uploadsCount += count;
  return { added: count };
}

export interface Integration {
  id: "huggingface" | "kaggle" | "gdrive" | "dropbox" | "s3" | "database";
  name: string;
  description: string;
  state: "connected" | "syncing" | "expired" | "disconnected" | "soon";
  syncPct?: number;
}

const integrations: Integration[] = [
  {
    id: "huggingface",
    name: "Hugging Face",
    description: "2 datasets · synced 2 min ago",
    state: "connected",
  },
  {
    id: "kaggle",
    name: "Kaggle",
    description: "Fetching telco-churn.csv (84 MB)",
    state: "syncing",
    syncPct: 62,
  },
  {
    id: "gdrive",
    name: "Google Drive",
    description: "Permission needed to read files",
    state: "expired",
  },
  {
    id: "dropbox",
    name: "Dropbox",
    description: "Read files from your Dropbox",
    state: "disconnected",
  },
  {
    id: "s3",
    name: "Amazon S3",
    description: "Buckets and signed links",
    state: "soon",
  },
  {
    id: "database",
    name: "Database",
    description: "Postgres, MySQL",
    state: "soon",
  },
];

// GET /integrations
export function getIntegrations() {
  return respond(integrations);
}

// POST /integrations/{hf|kaggle|gdrive}/connect (dummy OAuth)
export async function connectIntegration(id: Integration["id"]) {
  await respond(null);
  const row = integrations.find((i) => i.id === id);
  if (!row || row.state === "soon")
    throw new ApiError("This source is not available yet.", false);
  row.state = "connected";
  row.description = "0 datasets · synced just now";
  return structuredClone(row);
}

// Sync finished (the real backend pushes this over SSE)
export function markSynced(id: Integration["id"]) {
  const row = integrations.find((i) => i.id === id);
  if (row) {
    row.state = "connected";
    row.description = "1 dataset · synced just now";
    row.syncPct = undefined;
  }
}

export function getUploadsLabel() {
  return `${uploadsCount} ${uploadsCount === 1 ? "file" : "files"}`;
}

// ---------- Agreement + PayPal hold (screens 5 / 6) ----------
// Money rules live on the real backend: PayPal Sandbox only, AUTHORIZE (hold) on agreement,
// capture only after independent verification and never above max, void on miss/cancel.
const agreements: Record<string, Agreement> = {};

// POST /agreements
export async function createAgreement(chatId: string, target: AgreementTarget) {
  await respond(null);
  if (!(target.maxUsd > 0) || target.maxUsd > 500)
    throw new ApiError("Max price must be between $1 and $500.", false);
  if (
    target.precision <= 0 ||
    target.precision >= 100 ||
    target.minRecall <= 0 ||
    target.minRecall >= 100
  )
    throw new ApiError(
      "Both targets must be between 1% and 99%.",
      false,
    );
  const id = `agr-${Date.now().toString(36)}`;
  agreements[id] = { id, chatId, target, state: "draft" };
  return structuredClone(agreements[id]);
}

// POST /agreements/{id}/hold -> PayPal order (intent AUTHORIZE) -> approval_url
export async function holdAgreement(id: string) {
  await respond(null);
  const a = agreements[id];
  if (!a) throw new ApiError("Agreement not found.", false);
  a.state = "awaiting_approval";
  return { approvalUrl: `/c/${a.chatId}/pay?a=${id}` };
}

// GET /agreements/{id}
export async function getAgreement(id: string) {
  await respond(null);
  const a = agreements[id];
  if (!a) throw new ApiError("Agreement not found.", false);
  return structuredClone(a);
}

// PayPal return URL -> backend authorizes the order -> chat resumes and the job starts
export async function authorizeHold(id: string) {
  await respond(null);
  const a = agreements[id];
  if (!a) throw new ApiError("Agreement not found.", false);
  a.state = "held";
  return { nextChatId: "exp-1" };
}

// Cancel and return: nothing held
export async function cancelHold(id: string) {
  const a = agreements[id];
  if (a) a.state = "cancelled";
  return { chatId: a?.chatId ?? "agreement" };
}

// DELETE /projects/{id}/models/{modelId}
export async function deleteModel(modelId: string) {
  await sleep(200);
  if (mockMode() === "error")
    throw new ApiError("Could not delete the model. Try again.");
  return { id: modelId, deleted: true };
}

// POST /models/{id}/predict (mock: a simple deterministic rule so the demo feels alive)
export async function predictChurn(
  input: PredictionInput,
): Promise<PredictionResult> {
  await sleep(350);
  if (mockMode() === "error")
    throw new ApiError("The prediction service did not answer.");
  const base =
    input.contract === "Month-to-month"
      ? 0.55
      : input.contract === "One year"
        ? 0.25
        : 0.1;
  const tenure = 0.3 * (1 - Math.min(Math.max(input.months, 0), 36) / 36);
  const charge = ((input.monthlyCharge - 70) / 100) * 0.1;
  const probability = Math.round(
    Math.min(0.97, Math.max(0.03, base + tenure + charge)) * 100,
  );
  const reasons: string[] = [];
  if (input.contract === "Month-to-month")
    reasons.push("month-to-month contract");
  if (input.months < 12) reasons.push("short time as a customer");
  if (input.monthlyCharge > 90) reasons.push("high monthly charge");
  if (reasons.length === 0)
    reasons.push("long contract and long time as a customer");
  return { probability, reasons };
}

// GET /public/results/{shareId}  (no auth: the view-only share link)
export async function getPublicResult(shareId: string): Promise<PublicResult> {
  await respond(null);
  if (shareId !== "demo")
    throw new ApiError(
      "This shared result was not found. The link may have been turned off.",
      false,
    );
  return {
    shareId,
    title: "Churn prediction",
    byline: "Trained by David · Oct 24, 2026 · 7,043 customers",
    badge: "TARGET MET",
    verification: {
      heading: "Target reached on unseen data",
      metrics: [
        {
          id: "precision",
          label: "RIGHT WHEN FLAGGED",
          value: 82.4,
          ruleLabel: "target 80%",
          met: true,
        },
        {
          id: "recall",
          label: "LEAVERS CAUGHT",
          value: 63.1,
          ruleLabel: "minimum 60%",
          met: true,
        },
      ],
      testSetNote:
        "Locked test set of 1,409 customers · tested once · no retries",
    },
    money: {
      heldUsd: 40,
      chargedUsd: 18.6,
      releasedUsd: 21.4,
      note: "The owner was only charged because the independent test passed.",
    },
    checks: [
      {
        id: "c1",
        label: "Agreed target before training: about 80% right when flagged",
      },
      { id: "c2", label: "Model tested once on 1,409 customers it never saw" },
      { id: "c3", label: "Charge captured only after the test passed" },
    ],
    privacyNote:
      "This page shows results only. Data files, API keys and chat history stay private to the owner.",
  };
}

// DELETE /projects/{id}  (receipts stay in Billing)
// PATCH /projects/{id}
export async function renameProject(projectId: string, name: string) {
  await respond(null);
  const clean = name.trim();
  if (!clean) throw new ApiError("Give the project a name.", false);
  const p = shell.projects.find((x) => x.id === projectId);
  if (p) p.name = clean;
  return { id: projectId, name: clean };
}

// ---------- Share (screen 16) ----------
const shares: Record<string, ShareState> = {};
function shareFor(projectName: string): ShareState {
  return (shares[projectName] ??= {
    projectName,
    members: [
      { id: "me", name: "David (you)", role: "owner" },
      {
        id: "sana",
        name: "sana@example.com",
        role: "editor",
        status: "invite sent",
      },
    ],
    link: {
      enabled: true,
      url: `aioac.app/r/${projectName.split(" ")[0].toLowerCase()}-8f2a91`,
    },
  });
}

// GET /projects/{id}/share
export function getShare(projectName: string) {
  return respond<ShareState>(structuredClone(shareFor(projectName)));
}

// POST /projects/{id}/invites
export async function inviteMember(
  projectName: string,
  email: string,
  role: ShareRole,
) {
  await respond(null);
  const e = email.trim().toLowerCase();
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e))
    throw new ApiError("Enter a valid email address.", false);
  const st = shareFor(projectName);
  if (st.members.some((m) => m.name === e))
    throw new ApiError("That person already has access.", false);
  st.members.push({
    id: `m-${Date.now()}`,
    name: e,
    role,
    status: "invite sent",
  });
  return structuredClone(st);
}

// DELETE /projects/{id}/members/{memberId}
export async function removeMember(projectName: string, memberId: string) {
  await respond(null);
  const st = shareFor(projectName);
  st.members = st.members.filter(
    (m) => m.id !== memberId || m.role === "owner",
  );
  return structuredClone(st);
}

// PUT /projects/{id}/result-link (view only: results and receipt, no data files, keys or chat history)
export async function setResultLink(projectName: string, enabled: boolean) {
  await respond(null);
  const st = shareFor(projectName);
  st.link.enabled = enabled;
  return structuredClone(st);
}

export async function deleteProject(projectId: string) {
  await sleep(250);
  if (mockMode() === "error")
    throw new ApiError("Could not delete the project. Try again.");
  const i = shell.projects.findIndex((p) => p.id === projectId);
  if (i >= 0) shell.projects.splice(i, 1);
  return { id: projectId, deleted: true };
}

// DELETE /keys/{id}
export async function deleteKey(keyId: string) {
  await sleep(250);
  if (mockMode() === "error")
    throw new ApiError("Could not delete the key. Try again.");
  const i = shell.keys.findIndex((k) => k.id === keyId);
  if (i >= 0) shell.keys.splice(i, 1);
  const j = keysDb.findIndex((k) => k.id === keyId);
  if (j >= 0) keysDb.splice(j, 1);
  return { id: keyId, deleted: true };
}

// POST /models/{id}/predict-batch (mock: any CSV returns a fixed-size result)
export async function predictBatch(file: {
  name: string;
}): Promise<BatchResult> {
  await sleep(600);
  if (mockMode() === "error")
    throw new ApiError("The batch prediction did not finish. Try again.");
  if (!/\.csv$/i.test(file.name))
    throw new ApiError("Only .csv files are supported.", false);
  return {
    fileName: file.name.replace(/\.csv$/i, "") + "_predictions.csv",
    rows: 1204,
    flagged: 231,
  };
}

// GET /projects/{id}
const projectDetails: Record<string, ProjectDetail> = {
  churn: {
    id: "churn",
    name: "Churn prediction",
    subtitle: "Flag customers who may stop buying. about 80% right when flagged.",
    badge: "ROUND 2 RUNNING",
    openChatId: "exp-1",
    runs: [
      {
        id: "r2",
        round: "Round 2",
        date: "Oct 25",
        target: "P 80% / R 60%",
        result: "Running...",
        cost: "$0 so far",
        status: "running",
      },
      {
        id: "r1",
        round: "Round 1",
        date: "Oct 24",
        target: "P 80% / R 60%",
        result: "77.9% / 61.2%",
        cost: "$0.00",
        status: "missed",
      },
      {
        id: "b0",
        round: "Baseline",
        date: "Oct 24",
        target: "Free",
        result: "71.0% / 54.2%",
        cost: "$0.00",
        status: "done",
      },
    ],
    versions: [
      { id: "v1", name: "v1", metrics: "77.9% / 61.2%", best: true },
      { id: "baseline", name: "Baseline", metrics: "71.0% / 54.2%" },
    ],
    chats: [
      { id: "baseline", title: "Baseline run" },
      { id: "exp-1", title: "Experiment 1" },
      { id: "feature-check", title: "Feature check" },
    ],
    downloadNote: "Download unlocks when a target is met.",
  },
  loan: {
    id: "loan",
    name: "Loan repayment",
    subtitle:
      "Predict which loans will be repaid late. about 80% right when flagged.",
    openChatId: "baseline",
    runs: [
      {
        id: "l1",
        round: "Round 1",
        date: "Oct 24",
        target: "P 80% / R 60%",
        result: "82.1% / 63.4%",
        cost: "$14.20",
        status: "met",
      },
    ],
    versions: [{ id: "lv1", name: "v1", metrics: "82.1% / 63.4%", best: true }],
    chats: [],
    downloadNote: "Your model is ready to download.",
  },
  lead: {
    id: "lead",
    name: "Lead scoring",
    subtitle: "Score new leads. about 85% right when flagged.",
    openChatId: "baseline",
    runs: [],
    versions: [],
    chats: [],
    downloadNote: "Download unlocks when a target is met.",
  },
};

export async function getProject(projectId: string) {
  await respond(null);
  const p = projectDetails[projectId];
  if (!p) throw new ApiError("Project not found.", false);
  return structuredClone(p);
}

// DELETE /projects/{id}/models/{modelId} (keeps the project page in sync)
export async function deleteProjectVersion(
  projectId: string,
  versionId: string,
) {
  await deleteModel(versionId);
  const p = projectDetails[projectId];
  if (p) p.versions = p.versions.filter((v) => v.id !== versionId);
  return { id: versionId, deleted: true };
}

// GET /account/usage (billing overview). Read-only; money state comes from the backend later.
const usagePlan: UsagePlan = {
  plan: {
    name: "Starter",
    badge: "ACTIVE",
    blurb:
      "$0 per month. Free baseline on every project. You pay only when a target is verified.",
  },
  meters: [
    { id: "projects", label: "Projects", used: 2, limit: 3, text: "2 of 3" },
    {
      id: "data",
      label: "Data stored",
      used: 184,
      limit: 500,
      text: "184 MB of 500 MB",
    },
    {
      id: "jobs",
      label: "Experiment jobs",
      used: 3,
      limit: 5,
      text: "3 of 5",
    },
  ],
  card: {
    label: "Visa ending 4242",
    expires: "Expires 08/28 · used for PayPal holds",
    isDefault: true,
  },
  heldUsd: 0,
  heldNote:
    "No active holds. When a job starts, the agreed maximum is held, then captured or released.",
  activity: [
    {
      id: "a1",
      date: "Oct 22, 2026",
      type: "Job receipt",
      description: "Loan repayment · target met",
      amount: "$27.40",
      status: "captured",
    },
    {
      id: "a2",
      date: "Oct 18, 2026",
      type: "Job receipt",
      description: "Lead scoring · target missed",
      amount: "$0.00",
      status: "voided",
    },
  ],
};

export async function getUsage() {
  await respond(null);
  const u = structuredClone(usagePlan);
  if (readPlan() !== "starter") {
    u.plan = {
      name: planOffers.find((p) => p.id === readPlan())!.name,
      badge: "ACTIVE",
      blurb:
        "Billed through your PayPal account. Training is still pay-per-result.",
    };
  }
  if (mockMode() === "empty") {
    u.activity = [];
    u.card = null;
  }
  return u;
}

// Billing wizard. Real flow: backend creates a PayPal order/subscription and confirms by webhook.
// The mock never receives a card number; the form keeps only brand + last 4.
// The mock keeps the plan in localStorage so it survives reloads, like the real account would.
function readPlan(): PlanId {
  try {
    const v = localStorage.getItem("aioac.plan");
    return v === "pro" || v === "team" ? v : "starter";
  } catch {
    return "starter";
  }
}
function writePlan(id: PlanId) {
  try {
    localStorage.setItem("aioac.plan", id);
  } catch {
    /* storage unavailable: plan stays Starter */
  }
}
let invoiceSeq = 14;

export const planOffers: PlanOffer[] = [
  {
    id: "starter",
    name: "Starter",
    blurb: "For trying it out.",
    monthlyUsd: 0,
    features: [
      "3 projects",
      "Free baseline on every project",
      "Max $40 held per job",
      "500 MB data",
      "Community support",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    blurb: "For people who ship models regularly.",
    monthlyUsd: 29,
    badge: "MOST POPULAR",
    features: [
      "Unlimited projects",
      "Max $200 held per job",
      "Experiment 2 unlocked by default",
      "10 GB data",
      "Priority training queue",
      "Email invites for teammates",
    ],
  },
  {
    id: "team",
    name: "Team",
    blurb: "For small teams working together.",
    monthlyUsd: 99,
    features: [
      "Everything in Pro",
      "Up to 10 members",
      "Shared API keys and projects",
      "Spending limits per member",
      "Invoices with company details",
    ],
  },
];

export function planPrice(plan: PlanId, cycle: BillingCycle) {
  const monthly = planOffers.find((p) => p.id === plan)!.monthlyUsd;
  return cycle === "yearly"
    ? {
        perMonth: +(monthly * 0.8).toFixed(2),
        due: +(monthly * 0.8 * 12).toFixed(2),
      }
    : { perMonth: monthly, due: monthly };
}

// GET /billing/plans
export async function getPlans() {
  await respond(null);
  return { current: readPlan(), plans: structuredClone(planOffers) };
}

// POST /billing/subscribe (idempotency key per attempt in the real API)
export async function payPlan(input: PayPlanInput): Promise<PlanReceipt> {
  await respond(null);
  const offer = planOffers.find((p) => p.id === input.plan);
  if (!offer || offer.monthlyUsd === 0)
    throw new ApiError("That plan cannot be bought.", false);
  writePlan(input.plan);
  invoiceSeq += 1;
  return {
    invoice: `INV-2026-${String(invoiceSeq).padStart(4, "0")}`,
    date: "Oct 24, 2026",
    planLabel: `${offer.name}, ${input.cycle}`,
    paidWith:
      input.method === "paypal"
        ? "PayPal account"
        : `${input.cardBrand ?? "Card"} ending ${input.cardLast4 ?? "4242"}`,
    totalUsd: planPrice(input.plan, input.cycle).due,
    email: "mwmfigma@gmail.com",
    renewal: input.cycle === "yearly" ? "Oct 24, 2027" : "Nov 24, 2026",
  };
}

// GET /account/billing: plan invoices + job receipts (money rows come from the backend ledger).
const billingData: BillingData = {
  selectedId: "r2",
  rows: [
    {
      id: "r1",
      date: "Oct 24, 2026",
      type: "plan",
      typeLabel: "Plan invoice",
      description: "Pro, monthly",
      amount: "$29.00",
      status: "paid",
    },
    {
      id: "r2",
      date: "Oct 22, 2026",
      type: "job",
      typeLabel: "Job receipt",
      description: "Loan repayment · target met",
      amount: "$27.40",
      status: "captured",
    },
    {
      id: "r3",
      date: "Oct 18, 2026",
      type: "job",
      typeLabel: "Job receipt",
      description: "Lead scoring · target missed",
      amount: "$0.00",
      status: "voided",
    },
    {
      id: "r4",
      date: "Oct 15, 2026",
      type: "job",
      typeLabel: "Job receipt",
      description: "Churn prediction · experiment 1",
      amount: "$0.00",
      status: "released",
    },
    {
      id: "r5",
      date: "Sep 24, 2026",
      type: "plan",
      typeLabel: "Plan invoice",
      description: "Starter, free",
      amount: "$0.00",
      status: "free",
    },
  ],
  details: {
    r1: {
      title: "Pro plan",
      subtitle: "Oct 24, 2026 · INV-2026-0014",
      strong: "Total paid",
      rows: [
        ["Plan", "Pro, monthly"],
        ["Paid with", "Visa ending 4242"],
        ["Next renewal", "Nov 24, 2026"],
        ["Total paid", "$29.00"],
      ],
    },
    r2: {
      title: "Loan repayment",
      subtitle: "Oct 22, 2026 · REC-2026-0031",
      strong: "Charged",
      rows: [
        ["Agreed target", "P 80%, R 60%"],
        ["Verified", "82.1% / 63.4%"],
        ["Max held", "$40.00"],
        ["Charged", "$27.40"],
        ["Released", "$12.60"],
      ],
    },
    r3: {
      title: "Lead scoring",
      subtitle: "Oct 18, 2026 · REC-2026-0029",
      strong: "Charged",
      rows: [
        ["Agreed target", "P 80%, R 60%"],
        ["Verified", "77.9% / 61.2%"],
        ["Max held", "$40.00"],
        ["Charged", "$0.00"],
        ["Released", "$40.00"],
      ],
    },
    r4: {
      title: "Churn prediction",
      subtitle: "Oct 15, 2026 · REC-2026-0024",
      strong: "Charged",
      rows: [
        ["Agreed target", "P 80%, R 60%"],
        ["Verified", "Not run"],
        ["Max held", "$40.00"],
        ["Charged", "$0.00"],
        ["Released", "$40.00"],
      ],
    },
    r5: {
      title: "Starter plan",
      subtitle: "Sep 24, 2026 · INV-2026-0009",
      strong: "Total paid",
      rows: [
        ["Plan", "Starter, free"],
        ["Paid with", "None"],
        ["Total paid", "$0.00"],
      ],
    },
  },
};

export async function getBilling() {
  await respond(null);
  const b = structuredClone(billingData);
  if (mockMode() === "empty") {
    b.rows = [];
    b.details = {};
    b.selectedId = "";
  }
  return b;
}

// Payment methods + billing details. Real API: PayPal vault tokens; AIOAC stores brand/last4/expiry only.
const methodsState: PaymentMethodsData = {
  methods: [
    {
      id: "pm-visa",
      title: "Visa ending 4242",
      detail: "Expires 08/28 · David",
      isDefault: true,
    },
    {
      id: "pm-mc",
      title: "Mastercard ending 0099",
      detail: "Expires 11/26 · David",
      isDefault: false,
      expiresSoon: true,
    },
    {
      id: "pm-pp",
      title: "PayPal",
      detail: "mwmfigma@gmail.com",
      isDefault: false,
    },
  ],
  details: {
    name: "David",
    email: "mwmfigma@gmail.com",
    country: "Pakistan",
    taxId: "",
  },
};

export async function getPaymentMethods() {
  await respond(null);
  const d = structuredClone(methodsState);
  if (mockMode() === "empty") d.methods = [];
  return d;
}
export async function makeDefaultMethod(id: string) {
  await respond(null);
  methodsState.methods.forEach((m) => (m.isDefault = m.id === id));
  return { id };
}
export async function removeMethod(id: string) {
  await respond(null);
  const m = methodsState.methods.find((x) => x.id === id);
  if (m?.isDefault)
    throw new ApiError(
      "Choose another default method before removing this one.",
      false,
    );
  methodsState.methods = methodsState.methods.filter((x) => x.id !== id);
  return { id, removed: true };
}
export async function saveBillingDetails(details: BillingDetails) {
  await respond(null);
  if (!/^\S+@\S+\.\S+$/.test(details.email))
    throw new ApiError("Enter a valid email for invoices.", false);
  if (!details.name.trim()) throw new ApiError("Enter a name.", false);
  methodsState.details = { ...details };
  return methodsState.details;
}
