import { cn } from "@/lib/utils";

// Screen 19: motion and micro-interaction spec for code. A reference sheet, not a product screen.
// The values below are the starting timings the animated parts of the app should use.

const toolStates = [
  {
    name: "Idle",
    note: "Outline, muted text.",
    chip: "rounded-[14.5px] border border-border bg-white text-muted shadow-btn-neutral",
  },
  {
    name: "Running",
    note: "Dark fill, soft glow ring that breathes (2 s loop).",
    chip: "rounded-2xl border-4 border-border bg-brand-gradient text-white shadow-btn-primary",
  },
  {
    name: "Done",
    note: "Light fill, dark outline, quick settle.",
    chip: "rounded-2xl border border-brand bg-surface text-ink",
  },
  {
    name: "Error",
    note: "Dashed outline, one small shake (240 ms).",
    chip: "rounded-[14.5px] border border-dashed border-brand bg-brand-tint text-ink shadow-btn-neutral",
  },
];

const whileRunning: [string, string][] = [
  ["Tools", "Icon turns one notch every 600 ms"],
  ["Browser", "Small cursor glides across the chip"],
  ["Research", "Three dots scan left to right"],
  ["Training", "Shimmer sweeps across, 1.6 s"],
  ["Payment", "Lock icon, turns to a check on success"],
];

const stages: {
  name: string;
  note: string;
  dot: "done" | "run" | "pending";
}[] = [
  { name: "Queued", note: "Three dots pulse in sequence", dot: "done" },
  { name: "Provisioning", note: "Stacked bars fill upward", dot: "done" },
  { name: "Preparing data", note: "File tiles slide into a grid", dot: "done" },
  {
    name: "Training",
    note: "Line draws as points arrive, shimmer on bar",
    dot: "run",
  },
  {
    name: "Evaluating",
    note: "A scan line sweeps the test set",
    dot: "pending",
  },
  { name: "Saving results", note: "Check stamps in", dot: "pending" },
];

const etaRules = [
  "Always show a range, never one exact number.",
  "The range narrows as the job runs.",
  'If slower than 1.5 times the estimate, switch to "taking longer than expected".',
  "Show start time and estimated finish time.",
];

const timings: [string, string][] = [
  ["Canvas slides in", "280 ms ease-out"],
  ["Chat shrinks", "Same 280 ms, in sync"],
  ["Active tool glow", "2 s breathing loop"],
  ["Step ring pulse", "1.6 s loop"],
  ["Numbers count up", "700 ms"],
  ["MET tag stamp", "180 ms, 120 ms stagger"],
  ["Sync bar", "Real time from backend"],
  ["Error shake", "240 ms, once"],
  ["Success check", "220 ms"],
  ["Toast", "Slide 200 ms, stay 3 s"],
];

const h2 = "text-xl font-semibold leading-[normal] text-ink";
const lead = "text-sm leading-[normal] text-muted";

export function MotionSpec() {
  return (
    <div className="flex min-h-full items-start gap-8 bg-bg p-10">
      <section
        aria-label="Tool strip states"
        className="flex w-[420px] shrink-0 flex-col gap-3.5"
      >
        <h2 className={h2}>Tool strip states</h2>
        <p className={lead}>
          The agent is never silent. The tool it uses lights up.
        </p>
        {toolStates.map((s) => (
          <div key={s.name} className="flex items-center gap-3.5 py-1.5">
            <div className="w-[110px] shrink-0">
              <span
                className={cn(
                  "inline-flex px-3 py-1.5 text-sm font-semibold leading-[normal]",
                  s.chip,
                )}
              >
                Training
              </span>
            </div>
            <div className="flex min-w-px flex-1 flex-col gap-px text-sm">
              <p className="font-semibold leading-[normal] text-ink">
                {s.name}
              </p>
              <p className="text-[14px] leading-[17px] text-muted">{s.note}</p>
            </div>
          </div>
        ))}
        <h3 className="text-sm font-semibold leading-[normal] text-ink">
          What each tool does while running
        </h3>
        <dl>
          {whileRunning.map(([k, v]) => (
            <div
              key={k}
              className="flex items-start gap-2.5 border-b border-border py-2 text-sm leading-[normal]"
            >
              <dt className="w-20 shrink-0 font-semibold text-ink">{k}</dt>
              <dd className="min-w-px flex-1 text-muted">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section
        aria-label="Training stages and ETA"
        className="flex w-[420px] shrink-0 flex-col gap-3.5"
      >
        <h2 className={h2}>Training stages and ETA</h2>
        <p className={lead}>
          Each stage has its own small animation so waiting feels alive.
        </p>
        <ul>
          {stages.map((s) => (
            <li
              key={s.name}
              className="flex items-center gap-3 border-b border-border py-2"
            >
              <span
                aria-hidden
                className={cn(
                  "size-[18px] shrink-0 rounded-full",
                  s.dot === "done" && "bg-brand-gradient",
                  s.dot === "run" && "border-4 border-brand bg-white",
                  s.dot === "pending" &&
                    "border border-dashed border-border bg-white",
                )}
              />
              <div className="flex min-w-px flex-1 flex-col gap-px text-sm leading-[normal]">
                <p className="font-semibold text-ink">{s.name}</p>
                <p className="text-muted">{s.note}</p>
              </div>
            </li>
          ))}
        </ul>
        <h3 className="text-sm font-semibold leading-[normal] text-ink">
          ETA rules
        </h3>
        <ul className="flex flex-col gap-3.5">
          {etaRules.map((r) => (
            <li key={r} className="flex items-start gap-2.5">
              <span
                aria-hidden
                className="mt-1.5 size-1.5 shrink-0 rounded-[3px] bg-brand-gradient"
              />
              <p className="min-w-px flex-1 text-sm leading-[18px] text-ink">
                {r}
              </p>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-label="Timing reference"
        className="flex w-[420px] shrink-0 flex-col gap-3.5"
      >
        <h2 className={h2}>Timing reference</h2>
        <p className={lead}>Starting values for code. Tune by feel.</p>
        <div className="overflow-clip rounded-xl border border-border bg-white shadow-card-tight">
          <table className="w-full border-collapse text-left text-sm leading-[normal]">
            <caption className="sr-only">Timing reference</caption>
            <thead className="bg-surface text-muted">
              <tr>
                <th
                  scope="col"
                  className="w-[180px] px-3.5 py-[13px] font-semibold"
                >
                  Moment
                </th>
                <th scope="col" className="px-3.5 py-[13px] font-semibold">
                  Timing
                </th>
              </tr>
            </thead>
            <tbody>
              {timings.map(([m, t]) => (
                <tr
                  key={m}
                  className="border-b border-border text-ink last:border-b-0"
                >
                  <td className="px-3.5 py-[13px]">{m}</td>
                  <td className="px-3.5 py-[13px]">{t}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-sm leading-[18px] text-muted">
          Respect &quot;reduce motion&quot;: replace movement with simple fades.
        </p>
      </section>
    </div>
  );
}
