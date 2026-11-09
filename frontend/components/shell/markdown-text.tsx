import { Fragment } from "react";
import { parseMarkdown, type Inline } from "@/lib/markdown";

function Inlines({ xs }: { xs: Inline[] }) {
  return (
    <>
      {xs.map((x, i) => {
        switch (x.t) {
          case "text":
            return <Fragment key={i}>{x.v}</Fragment>;
          case "br":
            return <br key={i} />;
          case "strong":
            return (
              <strong key={i} className="font-semibold">
                <Inlines xs={x.c} />
              </strong>
            );
          case "em":
            return (
              <em key={i}>
                <Inlines xs={x.c} />
              </em>
            );
          case "code":
            return (
              <code key={i} className="rounded bg-surface px-1 py-0.5 font-mono text-[0.9em] text-ink-2">
                {x.v}
              </code>
            );
          case "link":
            return (
              <a key={i} href={x.href} target="_blank" rel="noopener noreferrer" className="text-brand-ink underline underline-offset-2">
                <Inlines xs={x.c} />
              </a>
            );
        }
      })}
    </>
  );
}

// Assistant text only. User bubbles stay plain text. No dangerouslySetInnerHTML anywhere.
export function MarkdownText({ text }: { text: string }) {
  const blocks = parseMarkdown(text);
  return (
    <div className="flex flex-col gap-2 text-body leading-6 text-ink">
      {blocks.map((b, i) =>
        b.t === "p" ? (
          <p key={i}>
            <Inlines xs={b.c} />
          </p>
        ) : b.t === "ul" ? (
          <ul key={i} className="list-disc pl-5">
            {b.items.map((it, j) => (
              <li key={j}>
                <Inlines xs={it} />
              </li>
            ))}
          </ul>
        ) : (
          <ol key={i} start={b.start} className="list-decimal pl-5">
            {b.items.map((it, j) => (
              <li key={j}>
                <Inlines xs={it} />
              </li>
            ))}
          </ol>
        ),
      )}
    </div>
  );
}
