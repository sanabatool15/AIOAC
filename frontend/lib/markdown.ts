// A tiny, SAFE markdown reader for assistant text. It returns plain data (no HTML strings); the screen renders it
// with React elements, so raw HTML in the text is shown as text and never run. No images. Links only for http(s).
// Supported: paragraphs, line breaks, **bold**, *italic*, `code`, "-"/"*" lists, "1." lists, [text](https://...).

export type Inline =
  | { t: "text"; v: string }
  | { t: "strong"; c: Inline[] }
  | { t: "em"; c: Inline[] }
  | { t: "code"; v: string }
  | { t: "br" }
  | { t: "link"; href: string; c: Inline[] };

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "ul"; items: Inline[][] }
  | { t: "ol"; items: Inline[][] };

// Only http(s) links survive. Anything else (javascript:, data:, mailto:, relative) is shown as its label.
export function safeHref(raw: string): string | null {
  const s = raw.trim();
  if (!/^https?:\/\//i.test(s)) return null;
  try {
    const u = new URL(s);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

export function parseInline(src: string, depth = 0): Inline[] {
  const out: Inline[] = [];
  let buf = "";
  const flush = () => {
    if (buf) out.push({ t: "text", v: buf });
    buf = "";
  };
  let i = 0;
  while (i < src.length) {
    const ch = src[i];
    if (ch === "`") {
      const end = src.indexOf("`", i + 1);
      if (end > i + 1) {
        flush();
        out.push({ t: "code", v: src.slice(i + 1, end) });
        i = end + 1;
        continue;
      }
    }
    if (depth < 4 && src.startsWith("**", i)) {
      const end = src.indexOf("**", i + 2);
      if (end > i + 2) {
        flush();
        out.push({ t: "strong", c: parseInline(src.slice(i + 2, end), depth + 1) });
        i = end + 2;
        continue;
      }
    }
    if (depth < 4 && (ch === "*" || ch === "_") && !src.startsWith(ch + ch, i)) {
      const end = src.indexOf(ch, i + 1);
      const inner = end > i + 1 ? src.slice(i + 1, end) : "";
      // "_" only at word edges so snake_case stays plain; "*" must hug its text.
      const boundaryOk = ch === "*" || ((i === 0 || /\W/.test(src[i - 1])) && (end + 1 >= src.length || /\W/.test(src[end + 1])));
      if (inner && !/^\s|\s$/.test(inner) && boundaryOk) {
        flush();
        out.push({ t: "em", c: parseInline(inner, depth + 1) });
        i = end + 1;
        continue;
      }
    }
    if (depth < 4 && ch === "[") {
      const m = /^\[([^\]\n]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)/.exec(src.slice(i));
      if (m) {
        flush();
        const href = safeHref(m[2]);
        const label = parseInline(m[1], depth + 1);
        if (href) out.push({ t: "link", href, c: label });
        else out.push(...label);
        i += m[0].length;
        continue;
      }
    }
    buf += ch;
    i++;
  }
  flush();
  return out;
}

function withBreaks(lines: string[]): Inline[] {
  const out: Inline[] = [];
  lines.forEach((l, i) => {
    if (i > 0) out.push({ t: "br" });
    out.push(...parseInline(l.trim()));
  });
  return out;
}

const UL = /^\s*[-*•]\s+(.*)$/;
const OL = /^\s*\d+[.)]\s+(.*)$/;
const HEAD = /^\s*#{1,6}\s+(.*)$/;

export function parseMarkdown(src: string): Block[] {
  const lines = (src ?? "").replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let para: string[] = [];
  let list: { kind: "ul" | "ol"; items: Inline[][] } | null = null;
  const endPara = () => {
    if (para.length) blocks.push({ t: "p", c: withBreaks(para) });
    para = [];
  };
  const endList = () => {
    if (list) blocks.push({ t: list.kind, items: list.items });
    list = null;
  };
  for (const line of lines) {
    if (!line.trim()) {
      endPara();
      endList();
      continue;
    }
    const ul = UL.exec(line);
    const ol = ul ? null : OL.exec(line);
    const hit = ul ?? ol;
    if (hit) {
      endPara();
      const kind = ul ? "ul" : "ol";
      if (list && list.kind !== kind) endList();
      list ??= { kind, items: [] };
      list.items.push(parseInline(hit[1].trim()));
      continue;
    }
    const h = HEAD.exec(line);
    if (h) {
      endPara();
      endList();
      blocks.push({ t: "p", c: [{ t: "strong", c: parseInline(h[1].trim()) }] });
      continue;
    }
    endList();
    para.push(line);
  }
  endPara();
  endList();
  return blocks;
}
