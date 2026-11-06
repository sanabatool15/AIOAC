// View types of the polished screens that are not rewired yet (plan steps 4 to 9 replace them with views from lib/adapters.ts).
// Backend shapes live in lib/api.ts; do not add new types here.

export type StepStatus = "done" | "running" | "pending";

export type ToolId = "tools" | "browser" | "research" | "training" | "payment";

export type ToolState = "idle" | "running" | "done" | "error";

export interface Step {
  id: string;
  label: string;
  status: StepStatus;
  meta?: string;
  tool: ToolId;
}

export interface Stage {
  name: string;
  status: StepStatus;
}

export interface HoldPart {
  id: string;
  label: string;
  tone: "primary" | "next" | "buffer";
  capUsd: number;
  note: string;
}

export interface TargetMetric {
  metric: string;
  baseline: number; // percent
  target: number; // percent
  qualifier?: string; // e.g. "min"
}

export interface JobFile {
  id: string;
  name: string;
  detail: string;
  kind: "data" | "model";
  locked?: boolean; // the verification test set: the agent never sees its answers
}

export interface JobLink {
  id: string;
  url: string; // shown without the scheme
  detail: string;
  access: "Read" | "Write";
}

export interface Job {
  id: string;
  title: string;
  state: "running" | "done" | "failed" | "cancelled";
  stepIndex: number;
  totalSteps: number;
  steps: Step[];
  tools: Record<ToolId, ToolState>;
  eta: {
    minLow: number;
    minHigh: number;
    finishLabel: string;
    progress: number;
  };
  stages: Stage[];
  hold: { maxUsd: number; parts: HoldPart[]; note: string };
  targets: TargetMetric[];
  files: JobFile[];
  links: JobLink[];
}

// Inline visuals an agent message can carry (screen 4).
export type MessageBlock =
  | "steps"
  | "readiness"
  | "result"
  | "agreement"
  | "summary"
  | "chart"
  | "verification"
  | "banner"
  | "model"
  | "prediction"
  | "quick-replies"
  | "research"
  | "ineligible"
  | "round2"
  | "ways";

export interface Message {
  id: string;
  role: "user" | "agent";
  text: string;
  blocks?: MessageBlock[];
}

export interface BaselineRun {
  stepIndex: number;
  totalSteps: number;
  steps: { id: string; label: string; seconds: number }[];
  readiness: { grade: string; title: string; detail: string; tag: string };
  result: { precision: number; recall: number; targetPrecision: number };
}

export interface Chat {
  id: string;
  title: string;
  projectName: string;
  messages: Message[];
  job?: Job;
  baseline?: BaselineRun;
  training?: TrainingRun;
  research?: ResearchRun;
  activity?: ResearchRun; // inline tool calls only (screen 11)
  verified?: VerifiedRun;
  result?: ResultRun;
  agreement?: AgreementOffer;
  ineligible?: IneligibleCheck; // screen 28
  round2?: Round2Plan; // screen 29
}

export interface TrainingStage {
  id: string;
  label: string;
  state: "done" | "run" | "pending";
  time: string;
}

// Screen 10: a running training experiment (live chart, ETA, stages, next decision).
export interface TrainingRun {
  stepIndex: number;
  totalSteps: number;
  precisionNow: number; // percent
  targetPrecision: number; // percent
  series: number[]; // validation precision samples, percent
  eta: { headline: string; detail: string; progress: number };
  stages: TrainingStage[];
  tools: Record<ToolId, ToolState>;
  decision: string;
}

// Screen 12: independent verification passed, payment being captured.
export interface VerifiedRun {
  stepIndex: number;
  totalSteps: number;
  outcome: "met" | "missed";
  heading: string;
  metrics: {
    id: string;
    label: string;
    value: number;
    ruleLabel: string;
    met: boolean;
  }[];
  testSetNote: string;
  tools: Record<ToolId, ToolState>;
  steps: { id: string; label: string; state: "done" | "run" | "pending" }[];
  payment?: {
    capturedUsd: number;
    heldUsd: number;
    releasedUsd: number;
    note: string;
  };
  // Screen 13 (target missed): hold voided, best model kept.
  banner?: string;
  bestModel?: { title: string; tag: string; detail: string };
  recap?: {
    heldUsd: number;
    chargedUsd: number;
    releasedUsd: number;
    note: string;
  };
}

export interface PredictionInput {
  contract: "Month-to-month" | "One year" | "Two year";
  months: number;
  monthlyCharge: number;
}

export interface PredictionResult {
  probability: number; // percent likely to stop buying
  reasons: string[];
}

// Screen 14: result, live prediction and receipt.
export interface ResultRun {
  stepIndex: number;
  totalSteps: number;
  tools: Record<ToolId, ToolState>;
  defaults: PredictionInput;
  initial: PredictionResult;
  receipt: { id: string; label: string; value: string }[];
  note: string;
  canDownloadModel: boolean; // unlocks once a target is met
  model: ModelUse; // screen 30
  ways: string[]; // screen 30 thread card
}

export type TierId = "safe" | "recommended" | "ambitious";

export interface AgreementTier {
  id: TierId;
  label: string;
  precision: number; // percent
  minRecall: number; // percent
  maxUsd: number;
}

export interface AgreementOffer {
  stepIndex: number;
  totalSteps: number;
  baselinePrecision: number;
  tiers: AgreementTier[];
}

export interface AgreementTarget {
  precision: number;
  minRecall: number;
  maxUsd: number;
}

export interface Budget {
  progress?: number; // optional bar under the headline (0-100)
  headline?: string; // replaces the amount line when nothing is held (e.g. "Free baseline · $0")
  heldUsd: number;
  usedUsd: number;
  label: string;
}

// Screen 9: agent researching while the experiment trains (chat column).
export interface ResearchRun {
  stepIndex: number;
  totalSteps: number;
  steps: {
    id: string;
    label: string;
    state: "done" | "run" | "pending";
    meta?: string;
  }[];
  tools: Record<ToolId, ToolState>;
}

// Screen 11: GET /budget/breakdown. The backend sets every allocation; the AI can only request more.
export interface BudgetBreakdown {
  maxHeldUsd: number;
  usedUsd: number;
  chargedTodayUsd: number;
  rows: {
    id: string;
    title: string;
    detail: string;
    amountLabel: string; // "$0", "$14"
    allocationUsd: number; // drives the split bar; 0 = not in the bar
    state: "done" | "running" | "locked" | "reserved";
  }[];
  rule: string;
  policy: string;
}

// Screen 28: the free check says the guarantee is not available as-is, with ways to fix it.
export interface IneligibleOption {
  id: "sample" | "target" | "upgrade";
  title: string;
  detail: string;
  recommended?: boolean;
}

export interface IneligibleCheck {
  checkedLabel: string;
  reasons: string[];
  options: IneligibleOption[];
  footnote: string;
}

// Screen 29: improve round 2 (keep v1, try new things, new agreement + new hold).
export interface Round2Plan {
  changes: string[];
  round1: { label: string; value: string; note: string };
  goal: { label: string; value: string; note: string };
  terms: [string, string][];
  target: AgreementTarget;
}

// Screen 30: use your model (download, API, batch).
export interface ModelUse {
  name: string;
  badge: string;
  summary: string;
  apiLines: string[];
  keyOn: boolean;
  usage: string;
}
