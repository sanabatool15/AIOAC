import test from "node:test";
import assert from "node:assert/strict";
import { parseInline, parseMarkdown, safeHref, type Inline } from "../lib/markdown";

const flat = (xs: Inline[]): string =>
  xs.map((x) => (x.t === "text" || x.t === "code" ? x.v : x.t === "br" ? "\n" : flat(x.c))).join("");

test("bold, italic and code become nodes with no markers left", () => {
  const n = parseInline("Use **German credit** and *this* with `col_a`.");
  assert.deepEqual(n.map((x) => x.t), ["text", "strong", "text", "em", "text", "code", "text"]);
  assert.equal(flat(n), "Use German credit and this with col_a.");
});

test("paragraphs, line breaks and lists", () => {
  const b = parseMarkdown("Hello\nthere\n\n- one\n- two\n\n1. a\n2. b");
  assert.deepEqual(b.map((x) => x.t), ["p", "ul", "ol"]);
  assert.deepEqual((b[0] as { c: Inline[] }).c.map((x) => x.t), ["text", "br", "text"]);
  assert.equal((b[1] as { items: Inline[][] }).items.length, 2);
  assert.equal(flat((b[2] as { items: Inline[][] }).items[1]), "b");
});

test("snake_case and lone asterisks stay plain", () => {
  assert.equal(flat(parseInline("my_column_name and 3 * 4")), "my_column_name and 3 * 4");
  assert.ok(parseInline("my_column_name").every((x) => x.t === "text"));
});

test("raw HTML stays text (React escapes it)", () => {
  const src = "<script>alert(1)</script> <img src=x onerror=alert(1)> &lt;b&gt;";
  const n = parseInline(src);
  assert.ok(n.every((x) => x.t === "text"));
  assert.equal(flat(n), src);
});

test("only http(s) links are kept", () => {
  assert.equal(safeHref("https://example.com/a?b=1"), "https://example.com/a?b=1");
  for (const bad of ["javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "data:text/html,x", "//evil.com", "/x", "mailto:a@b.c", "vbscript:x"]) {
    assert.equal(safeHref(bad), null, bad);
  }
  assert.deepEqual(parseInline("[site](https://example.com)").map((x) => x.t), ["link"]);
  const bad = parseInline("[click](javascript:alert(1))");
  assert.ok(bad.every((x) => x.t !== "link"));
  assert.equal(flat(bad), "click");
});

test("images produce no image node", () => {
  const n = parseInline("![x](https://e.com/a.png)");
  assert.ok(!JSON.stringify(n).includes("img"));
});

test("unclosed markers are left as text and never throw", () => {
  assert.equal(flat(parseInline("**oops and `tick")), "**oops and `tick");
  assert.doesNotThrow(() => parseMarkdown("*".repeat(500) + "_".repeat(500) + "[".repeat(200)));
});

test("headings become bold paragraphs", () => {
  assert.deepEqual(parseMarkdown("## Next step"), [{ t: "p", c: [{ t: "strong", c: [{ t: "text", v: "Next step" }] }] }]);
});
