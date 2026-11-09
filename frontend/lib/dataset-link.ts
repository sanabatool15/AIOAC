// A first, friendly check of a pasted dataset address before it is sent. The server is the real gate (backend
// integrations/datasets/links.py); this only saves a round trip and gives a plain message. Pure, no network.
export const LINK_HELP =
  "Paste the page address of a dataset on Hugging Face (huggingface.co/datasets/owner/name), UCI (archive.ics.uci.edu/dataset/number) or OpenML (openml.org/d/number).";

export function checkLink(text: string): { ok: true; url: string } | { ok: false; message: string } {
  const url = text.trim();
  if (!url) return { ok: false, message: "Paste a link first." };
  let u: URL;
  try {
    u = new URL(url);
  } catch {
    return { ok: false, message: LINK_HELP };
  }
  const host = u.hostname.toLowerCase();
  const known =
    (host === "huggingface.co" && /^\/datasets\/[^/]+\/[^/]+\/?$/.test(u.pathname)) ||
    (host === "archive.ics.uci.edu" && /^\/dataset\/\d+(\/[^/]*)?\/?$/.test(u.pathname)) ||
    ((host === "openml.org" || host === "www.openml.org") && /^\/d\/\d+\/?$/.test(u.pathname));
  if (u.protocol !== "https:" || u.username || u.password || !known) return { ok: false, message: LINK_HELP };
  return { ok: true, url };
}

export function guessAnswerColumn(cols: string[], suggested?: string): string {
  if (suggested && cols.includes(suggested)) return suggested;
  return cols.find((c) => /^(target|label|class|churn|outcome|y)$/i.test(c)) ?? cols[cols.length - 1] ?? "";
}
