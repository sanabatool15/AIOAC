import { Box, FileSpreadsheet } from "lucide-react";
import { Tag } from "@/components/ui/tag";
import { EmptyState } from "@/components/ui/state";
import type { Job } from "@/lib/types";
import { ToolStrip } from "./tool-strip";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold leading-[normal] whitespace-nowrap text-muted">
      {children}
    </p>
  );
}

// Screen 8: what the agent is allowed to touch (files and linked data sources).
export function FilesTab({ job }: { job: Job }) {
  return (
    <>
      <ToolStrip tools={job.tools} />

      <SectionLabel>FILES THE AGENT CAN USE</SectionLabel>
      {job.files.length === 0 ? (
        <EmptyState
          icon={<Box />}
          title="No files yet"
          body="Files the agent reads or creates show up here."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {job.files.map((f) => (
            <li
              key={f.id}
              className="flex items-center gap-3 overflow-clip rounded-[10px] border border-border bg-white p-3"
            >
              <div
                aria-hidden
                className="flex size-[30px] shrink-0 items-center justify-center rounded-[7px] border border-border bg-surface text-ink-2"
              >
                {f.kind === "model" ? (
                  <Box size={16} />
                ) : (
                  <FileSpreadsheet size={16} />
                )}
              </div>
              <div className="flex min-w-px flex-1 flex-col gap-px overflow-clip leading-[normal]">
                <p className="truncate text-sm font-semibold text-ink">
                  {f.name}
                </p>
                <p className="truncate text-xs text-muted">{f.detail}</p>
              </div>
              {f.locked && <Tag variant="brand">LOCKED</Tag>}
            </li>
          ))}
        </ul>
      )}

      <SectionLabel>DATA LINKS</SectionLabel>
      {job.links.length === 0 ? (
        <EmptyState
          icon={<Box />}
          title="No linked data"
          body="Connect or paste a link from Add data."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {job.links.map((l) => (
            <li
              key={l.id}
              className="flex items-center gap-3 overflow-clip rounded-[10px] border border-border bg-white p-3"
            >
              <div className="flex min-w-px flex-1 flex-col gap-px overflow-clip leading-[normal]">
                <a
                  href={`https://${l.url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="truncate text-sm font-semibold text-ink hover:underline"
                >
                  {l.url}
                </a>
                <p className="truncate text-xs text-muted">{l.detail}</p>
              </div>
              <Tag>{l.access}</Tag>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
