import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { toActivity } from "../lib/screens";

// Guard: screens never print raw cents or hand-formatted decimals. Money goes through dollars() in lib/adapters.ts.
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : p.endsWith(".tsx") ? [p] : [];
  });
}

test("components only show cents through dollars()", () => {
  const bad: string[] = [];
  // File sizes and animation values are not money; these three files format them with toFixed.
  const SIZE_OR_ANIMATION = ["composer.tsx", "data-upload.tsx", "thinking-orbs.tsx"];
  for (const f of files("components").filter((f) => !SIZE_OR_ANIMATION.some((n) => f.endsWith(n)))) {
    readFileSync(f, "utf8")
      .split("\n")
      .forEach((line, i) => {
        if (/\.toFixed\(/.test(line)) bad.push(`${f}:${i + 1} toFixed`);
        if (/\b\w*_cents\b/.test(line) && !/dollars\(/.test(line) && !/^\s*(const \w+ = [\w.?]+;|\/\/)/.test(line)) {
          bad.push(`${f}:${i + 1} ${line.trim()}`);
        }
      });
  }
  assert.deepEqual(bad, []);
});

test("an activity line with a redacted marker is shown as it is", () => {
  const rows = toActivity([{ kind: "tool", when: "2026-11-06T10:00:00Z", text: "Called a tool with key [redacted:key]" }]);
  assert.equal(rows[0].text, "Called a tool with key [redacted:key]");
});
