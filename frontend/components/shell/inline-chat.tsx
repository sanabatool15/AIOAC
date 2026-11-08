"use client";
import { Composer } from "./composer";
import { MarkdownText } from "./markdown-text";
import { ShareButton } from "./share-dialog";
import { TopBar } from "./top-bar";

// Shared frame for the project chat: top bar, one centred column that scrolls, the composer under it.
export function InlineChatFrame({
  projectName,
  projectId,
  onSend,
  composer,
  children,
}: {
  projectName: string;
  projectId?: string; // shows the Share button
  onSend?: (text: string) => void;
  composer?: React.ReactNode; // replaces the default composer (the project chat brings its own)
  children: React.ReactNode;
}) {
  return (
    <section aria-label="Chat" className="flex h-full min-w-0 flex-1 flex-col bg-bg">
      <TopBar
        left={<h1 className="whitespace-pre text-small font-normal text-muted">{`${projectName}  /  Chat`}</h1>}
        actions={projectId ? <ShareButton projectId={projectId} /> : undefined}
      />
      <div className="flex min-h-0 flex-1 justify-center overflow-y-auto px-4 pb-2.5 pt-6 sm:px-6">
        <div className="flex h-fit w-full max-w-chat flex-col gap-6">{children}</div>
      </div>
      <div className="flex shrink-0 justify-center px-4 pb-5 pt-2 sm:px-6">
        <div className="w-full max-w-chat">
          {composer ??
            (onSend && <Composer onSend={onSend} placeholder="Ask AIOAC anything, or describe what to predict..." />)}
        </div>
      </div>
    </section>
  );
}

export function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-xl bg-surface px-4 py-2.5">
        <p className="max-w-sm text-body text-ink">
          {text}
        </p>
      </div>
    </div>
  );
}

export function AgentRow({ text, children }: { text: string; children?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      <div
        aria-hidden
        className="size-6 shrink-0 rounded-full bg-brand"
      />
      <div className="flex min-w-px flex-1 flex-col gap-3">
        {text && <MarkdownText text={text} />}
        {children}
      </div>
    </div>
  );
}
