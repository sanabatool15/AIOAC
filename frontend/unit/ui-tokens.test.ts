import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { cn } from "../lib/utils";

const css = readFileSync(join(__dirname, "../app/globals.css"), "utf8");
const root = css.slice(css.indexOf(":root"), css.indexOf("}", css.indexOf(":root")));

function token(name: string): string {
  const m = root.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`));
  assert.ok(m, `token --${name} must be a #rrggbb colour in :root`);
  return m[1];
}
function lum(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function ratio(a: string, b: string) {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// every text token on every surface it is used on
const PAIRS: [string, string][] = [
  ["ink", "card"], ["ink", "bg"], ["ink", "surface"],
  ["ink-2", "card"], ["ink-2", "surface"], ["ink-2", "bg"],
  ["muted", "card"], ["muted", "bg"], ["muted", "surface"], ["muted", "brand-tint"],
  ["pending", "card"], ["pending", "surface"],
  ["brand", "card"], ["brand", "bg"], ["brand", "brand-soft"],
  ["brand-ink", "brand-tint"], ["brand-ink", "brand-soft"], ["brand-ink", "card"],
  ["on-brand", "brand"], ["on-brand", "brand-hover"], ["on-brand", "danger"], ["on-brand", "success"],
  ["success", "card"], ["success", "success-soft"],
  ["warning", "card"], ["warning", "warning-soft"],
  ["danger", "card"], ["danger", "danger-soft"],
];

for (const [fg, bg] of PAIRS) {
  test(`contrast ${fg} on ${bg} is at least 4.5:1`, () => {
    const r = ratio(token(fg), token(bg));
    assert.ok(r >= 4.5, `${fg} on ${bg} is ${r.toFixed(2)}:1`);
  });
}

test("no gradients or purple glow left in globals.css", () => {
  assert.doesNotMatch(css, /linear-gradient|radial-gradient/);
  assert.doesNotMatch(css, /rgb\(91 33 182|rgb\(124 58 237/);
});

test("scrim token exists", () => {
  assert.match(css, /--scrim:\s*rgb\(15 23 42 \/ 0\.55\)/);
});

test("type, radius and width tokens exist", () => {
  for (const t of ["--text-title:", "--text-section:", "--text-body:", "--text-small:", "--text-micro:"]) assert.ok(css.includes(t), t);
  assert.match(css, /--radius-sm:\s*6px/);
  assert.match(css, /--radius-md:\s*8px/);
  assert.match(css, /--radius-lg:\s*12px/);
  assert.match(css, /--radius-xl:\s*16px/);
  for (const t of ["--width-chat:", "--width-form:", "--width-page:"]) assert.ok(css.includes(t), t);
});

test("components/ui has no raw hex and no Tailwind palette colours", () => {
  const dir = join(__dirname, "../components/ui");
  const palette = /\b(?:bg|text|border|ring|outline|fill|stroke|from|to|via|divide)-(?:red|rose|pink|fuchsia|purple|violet|indigo|blue|sky|cyan|teal|emerald|green|lime|yellow|amber|orange|stone|slate|gray|zinc|neutral|white|black)(?:-\d{2,3})?\b/;
  for (const f of readdirSync(dir)) {
    const src = readFileSync(join(dir, f), "utf8");
    assert.doesNotMatch(src, /#[0-9a-fA-F]{3,8}\b/, `${f} has a raw hex colour`);
    assert.doesNotMatch(src, palette, `${f} has a raw palette colour`);
    assert.doesNotMatch(src, /\b(?:text|rounded|max-w|w)-\[\d+px\]/, `${f} has an arbitrary px size`);
  }
});

test("cn keeps token text sizes next to token text colours", () => {
  assert.equal(cn("text-title", "text-ink"), "text-title text-ink");
  assert.equal(cn("text-body", "text-small"), "text-small");
  assert.equal(cn("shadow-card", "shadow-popover"), "shadow-popover");
  assert.equal(cn("max-w-chat", "max-w-form"), "max-w-form");
});
