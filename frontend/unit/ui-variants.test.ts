import test from "node:test";
import assert from "node:assert/strict";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Card, resolveCardVariant } from "../components/ui/card";
import { Tag, resolveTagVariant } from "../components/ui/tag";
import { Button, LinkButton, resolveButtonStyle } from "../components/ui/button";
import { EmptyState, ErrorState } from "../components/ui/state";
import { EstimateNote } from "../components/ui/estimate-note";
import { PageHeader } from "../components/ui/page-header";
import { StatusChip } from "../components/ui/status-chip";
import { FolderOpen } from "lucide-react";

test("old card names map to the new variants", () => {
  const map = { violet: "highlight", blue: "plain", peach: "plain", mint: "plain", green: "success", red: "danger", amber: "warning" } as const;
  for (const [old, now] of Object.entries(map)) assert.equal(resolveCardVariant(old as keyof typeof map), now);
  for (const v of ["plain", "success", "warning", "danger", "highlight"] as const) assert.equal(resolveCardVariant(v), v);
  assert.equal(resolveCardVariant(undefined), "plain");
});

test("card variants render distinct flat classes, never a gradient", () => {
  const out = (v: Parameters<typeof Card>[0]["variant"]) => renderToStaticMarkup(h(Card, { variant: v }, "x"));
  assert.match(out("success"), /bg-success-soft/);
  assert.match(out("warning"), /bg-warning-soft/);
  assert.match(out("danger"), /bg-danger-soft/);
  assert.match(out("highlight"), /bg-brand-soft/);
  assert.match(out("plain"), /bg-card/);
  assert.match(out("amber"), /bg-warning-soft/, "deprecated name still renders");
  assert.doesNotMatch(out("peach"), /surface-|gradient/);
});

test("old tag names map and the five variants render", () => {
  assert.equal(resolveTagVariant("muted"), "neutral");
  assert.equal(resolveTagVariant("dashed"), "neutral");
  assert.equal(resolveTagVariant(undefined), "neutral");
  const cls: Record<string, string> = { neutral: "bg-surface", brand: "bg-brand-tint", success: "bg-success-soft", warning: "bg-warning-soft", danger: "bg-danger-soft" };
  for (const [v, c] of Object.entries(cls)) assert.match(renderToStaticMarkup(h(Tag, { variant: v as "neutral" }, "t")), new RegExp(c));
});

test("button size scale, deprecated names and block", () => {
  assert.deepEqual(resolveButtonStyle({}), { variant: "primary", size: "md", block: false });
  assert.equal(resolveButtonStyle({ size: "action" }).size, "lg");
  assert.equal(resolveButtonStyle({ size: "default" }).size, "sm");
  assert.equal(resolveButtonStyle({ variant: "icon" }).variant, "ghost");
  assert.match(renderToStaticMarkup(h(Button, { size: "icon", "aria-label": "x" })), /size-9/);
  assert.match(renderToStaticMarkup(h(Button, { block: true }, "Go")), /w-full/);
  assert.match(renderToStaticMarkup(h(Button, null, "Go")), /type="button"/);
});

test("LinkButton: internal path is a link, external gets rel when it opens a tab", () => {
  const a = renderToStaticMarkup(h(LinkButton, { href: "/projects", variant: "outline" }, "Open"));
  assert.match(a, /<a [^>]*href="\/projects"/);
  assert.match(a, /border-border/);
  const b = renderToStaticMarkup(h(LinkButton, { href: "https://example.com", target: "_blank" }, "Out"));
  assert.match(b, /rel="noopener noreferrer"/);
});

test("empty and error states use real icons and keep retry", () => {
  const e = renderToStaticMarkup(h(EmptyState, { icon: FolderOpen, title: "None", body: "Nothing here" }));
  assert.match(e, /<svg/);
  assert.doesNotMatch(e, /·/);
  assert.match(renderToStaticMarkup(h(EmptyState, { title: "None", body: "b" })), /<svg/, "default icon");
  const r = renderToStaticMarkup(h(ErrorState, { message: "boom", onRetry: () => {} }));
  assert.match(r, /role="alert"/);
  assert.match(r, /Try again/);
});

test("EstimateNote, PageHeader and StatusChip", () => {
  assert.match(renderToStaticMarkup(h(EstimateNote)), /estimates, not promises/);
  const hd = renderToStaticMarkup(h(PageHeader, { title: "Goal", subtitle: "sub", actions: "A", clampTitle: true }));
  assert.equal((hd.match(/<h1/g) ?? []).length, 1);
  assert.match(hd, /line-clamp-2/);
  const chip = renderToStaticMarkup(h(StatusChip, { tone: "danger", children: "Failed" }));
  assert.match(chip, /Failed/);
  assert.match(chip, /bg-danger-soft/);
});
