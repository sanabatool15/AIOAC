"use client";
import { useEffect, useId, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Skeleton } from "@/components/ui/state";

// Charts and diagrams the agent asks for. The server has already cut them to a safe size; colours come from the tokens.
const PALETTE = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];
// The same chart always gets the same colour, and different charts usually get different ones.
function colourFor(title: string): string {
  let h = 0;
  for (let i = 0; i < title.length; i++) h = (h * 31 + title.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

export function ChartBlock({ title, kind, labels, values, unit }: { title?: string; kind?: string; labels: string[]; values: number[]; unit?: string }) {
  const data = labels.map((name, i) => ({ name, value: values[i] ?? 0 }));
  const colour = colourFor(`${title ?? ''}${labels.join('')}`);
  const tip = { background: "var(--card)", border: "1px solid var(--border)", borderRadius: 8, boxShadow: "none", fontSize: 13, padding: "6px 10px" };
  const axis = { fontSize: 12, fill: "var(--muted)" };
  const common = { data, margin: { top: 8, right: 8, bottom: 0, left: -12 } };
  return (
    <figure aria-label={title ?? "Chart"} className="flex flex-col gap-2 rounded-lg border border-border bg-card p-4">
      {title && <figcaption className="text-body font-semibold text-ink">{title}{unit ? ` (${unit})` : ""}</figcaption>}
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {kind === "line" ? (
            <LineChart {...common}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
              <YAxis tick={axis} tickLine={false} axisLine={false} />
              <Tooltip cursor={{ stroke: "var(--border)" }} contentStyle={tip} labelStyle={{ color: "var(--ink)", fontWeight: 600 }} itemStyle={{ color: "var(--ink-2)" }} formatter={(v) => [unit ? `${v} ${unit}` : String(v), ""]} separator="" />
              <Line type="monotone" dataKey="value" stroke={colour} strokeWidth={2} dot={{ r: 3, fill: colour }} />
            </LineChart>
          ) : (
            <BarChart {...common}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="name" tick={axis} tickLine={false} axisLine={false} />
              <YAxis tick={axis} tickLine={false} axisLine={false} />
              <Tooltip cursor={false} contentStyle={tip} labelStyle={{ color: "var(--ink)", fontWeight: 600 }} itemStyle={{ color: "var(--ink-2)" }} formatter={(v) => [unit ? `${v} ${unit}` : String(v), ""]} separator="" />
              <Bar dataKey="value" fill={colour} radius={[4, 4, 0, 0]} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

// Mermaid is loaded only when a diagram is shown, and runs in strict mode (no scripts, no links).
export function DiagramBlock({ title, source }: { title?: string; source: string }) {
  const id = `m${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [svg, setSvg] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: "base",
          fontFamily: css("--font-sans") || "sans-serif",
          themeVariables: {
            primaryColor: css("--brand-tint"),
            primaryBorderColor: css("--brand-edge"),
            primaryTextColor: css("--ink"),
            lineColor: css("--muted"),
            secondaryColor: css("--surface"),
            tertiaryColor: css("--card"),
          },
        });
        const out = await mermaid.render(id, source);
        if (live) setSvg(out.svg);
      } catch {
        if (live) setFailed(true);
      }
    })();
    return () => {
      live = false;
    };
  }, [id, source]);
  return (
    <figure aria-label={title ?? "Diagram"} className="flex flex-col gap-2 overflow-x-auto rounded-lg border border-border bg-card p-4">
      {title && <figcaption className="text-body font-semibold text-ink">{title}</figcaption>}
      {failed ? (
        <p className="text-body text-muted">This diagram could not be drawn.</p>
      ) : svg ? (
        <div dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <Skeleton className="h-32" />
      )}
    </figure>
  );
}
