"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { ApiError, type BProject } from "@/lib/api";
import { getProject, rememberProject } from "@/lib/api-real";
import { isSettling, screenFor, stepIndex } from "@/lib/status";
import { ChatComposer, ChatThread, useProjectChat } from "./project-chat";
import { BudgetButton } from "./budget-panel";
import { PayPrompt } from "./pay-prompt";
import { AddDataDialog, type AddDataKind } from "./data-dialog";
import { DataPicker } from "./data-picker";
import { InlineChatFrame } from "./inline-chat";
import { ModelPanel } from "./model-panel";
import { ProjectPanel } from "./project-panel";
import { stepChanged } from "./chat-layout";
import { StepArea } from "./step-area";
import { PROJECTS_CHANGED } from "./sidebar";
import { useFollowChat } from "./use-follow-chat";

// Route body for /c/[chatId]: the screen comes from the project status (lib/status.ts), loaded from the server on every
// visit. The project chat is on every status; a chat reply that may change things makes the page read the project again.
export function ChatScreen({ chatId }: { chatId: string }) {
  const [project, setProject] = useState<BProject | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const lastStatus = useRef<string | null>(null);

  const load = useCallback(async () => {
    try {
      const p = await getProject(chatId);
      if (lastStatus.current && lastStatus.current !== p.status) window.dispatchEvent(new Event(PROJECTS_CHANGED)); // the sidebar shows the new status
      lastStatus.current = p.status;
      setProject(p);
      setError(null);
      rememberProject(chatId);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Could not load this project."));
    }
  }, [chatId]);

  useEffect(() => {
    const t = setTimeout(() => void load(), 0);
    return () => clearTimeout(t);
  }, [load]);

  // While a run or a release is in motion, keep the page in step with the server.
  const settling = isSettling(project?.status);
  useEffect(() => {
    if (!settling) return;
    const id = setInterval(() => void load(), 3000);
    return () => clearInterval(id);
  }, [settling, load]);

  if (!project) {
    return error ? (
      <div className="flex min-w-0 flex-1 items-center justify-center">
        <ErrorState message={error.message} onRetry={() => void load()} />
      </div>
    ) : (
      <div className="flex min-w-0 flex-1 flex-col gap-4 p-8" aria-busy="true" aria-label="Loading project">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-40 w-full max-w-form" />
      </div>
    );
  }
  return <Project project={project} error={error} reload={load} />;
}

function Project({ project, error, reload }: { project: BProject; error: Error | null; reload: () => Promise<void> }) {
  const pc = useProjectChat(project.id, project.goal, project.status, reload);
  const screen = screenFor(project);
  const idx = stepIndex(screen);
  const onData = screen === "data";
  const bottom = useRef<HTMLDivElement>(null);
  const stepRef = useRef<HTMLDivElement>(null);
  const lastScreen = useRef<string | null>(null);
  const items = pc.state.items;
  // A new chat has nothing to show yet, so the right panel starts closed and opens once the process starts.
  // After the reader opens or closes it themselves, their choice stays.
  const [panelChoice, setPanelChoice] = useState<boolean | null>(null);
  const panelOpen = panelChoice ?? !onData; // closed until the process starts, then it opens by itself
  // Attach (the clip) and dropping a file on the chat both open "Add data". Only while no data is chosen yet.
  const [adding, setAdding] = useState<AddDataKind | null>(null);
  const [attached, setAttached] = useState<File | null>(null); // a CSV waiting under the text in the box
  const [pendingText, setPendingText] = useState("");
  const lastIsUser = items?.[items.length - 1]?.role === "user";
  // The newest chat message (or the live steps) stays next to the composer. A reader who scrolled up is not moved.
  useFollowChat(bottom, `${items?.length ?? 0}:${pc.state.busy}:${pc.state.liveSteps.length}`, !!lastIsUser, items !== null);
  // A new step brings its card into view (the first render is left alone: the page opens from the top).
  useEffect(() => {
    if (stepChanged(lastScreen.current, screen)) stepRef.current?.scrollIntoView?.({ block: "start" });
    lastScreen.current = screen;
  }, [screen]);

  return (
    <InlineChatFrame
      projectName={project.goal.length > 48 ? `${project.goal.slice(0, 48)}…` : project.goal}
      composer={
        <ChatComposer
          pc={pc}
          onPickFile={onData ? setAttached : undefined}
          attachment={onData ? attached : null}
          onRemoveAttachment={() => setAttached(null)}
          onSendWithFile={(text) => {
            setPendingText(text);
            setAdding("upload");
          }}
        />
      }
      onDropFile={
        onData
          ? (f) => setAttached(f)
          : undefined
      }
      extraActions={<BudgetButton project={project} />}
      panelOpen={panelOpen}
      onTogglePanel={() => setPanelChoice(!panelOpen)}
      canvas={
        <ProjectPanel project={project} index={onData ? -1 : idx} showTarget={["quote", "pay", "paid", "training"].includes(screen)} onChanged={reload}>
          {!onData && (
            <div ref={stepRef} data-region="step" aria-label="Current step" className="flex scroll-mt-4 flex-col gap-4">
              <StepArea screen={screen} project={project} onChanged={reload} />
            </div>
          )}
        </ProjectPanel>
      }
    >
      {error && (
        <p role="alert" className="flex items-center gap-3 text-body text-danger">
          {error.message}
          <Button variant="outline" onClick={() => void reload()}>
            Try again
          </Button>
        </p>
      )}
      <div data-region="conversation" className="flex flex-col gap-4">
        {onData && <DataPicker projectId={project.id} pc={pc} onChanged={reload} />}
        <ChatThread pc={pc} projectStatus={project.status} />
        {project.run && project.status === "done" && (
          <div className="pl-9">
            <ModelPanel projectId={project.id} />
          </div>
        )}
      </div>
      {(screen === "quote" || screen === "pay") && (
        <PayPrompt project={project} />
      )}
      <div ref={bottom} aria-hidden />
      <AddDataDialog
        projectId={project.id}
        kind={adding}
        file={attached}
        onClose={() => setAdding(null)}
        onChanged={async () => {
          await reload();
          setAttached(null);
          if (pendingText) void pc.chat.send(pendingText);
          setPendingText("");
        }}
      />
    </InlineChatFrame>
  );
}
