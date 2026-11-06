"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/state";
import { ApiError, type BProject } from "@/lib/api";
import { getProject, rememberProject } from "@/lib/api-real";
import { isSettling, screenFor, STEP_LABELS, stepIndex } from "@/lib/status";
import { ChatComposer, ChatThread, useProjectChat } from "./project-chat";
import { UploadPanel } from "./data-upload";
import { InlineChatFrame } from "./inline-chat";
import { Stepper } from "./step-parts";
import { StepArea } from "./step-area";
import { PROJECTS_CHANGED } from "./sidebar";

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
        <Skeleton className="h-40 w-full max-w-[640px]" />
      </div>
    );
  }
  return <Project project={project} error={error} reload={load} />;
}

function Project({ project, error, reload }: { project: BProject; error: Error | null; reload: () => Promise<void> }) {
  const pc = useProjectChat(project.id, project.goal, project.status, reload);
  const [uploadOpen, setUploadOpen] = useState(false);
  const screen = screenFor(project);
  const idx = stepIndex(screen);
  const onData = screen === "data";
  const bottom = useRef<HTMLDivElement>(null);
  const itemCount = pc.state.items?.length ?? 0;
  // Keep the newest message and the current step in view (chat first, then what to do next).
  useEffect(() => {
    bottom.current?.scrollIntoView?.({ block: "end" });
  }, [itemCount, pc.state.busy, project.status]);

  return (
    <InlineChatFrame
      projectName={project.goal.length > 48 ? `${project.goal.slice(0, 48)}…` : project.goal}
      stepLabel={`Step ${idx + 1} of ${STEP_LABELS.length}: ${STEP_LABELS[idx]}`}
      wide
      composer={<ChatComposer pc={pc} onAttach={onData ? () => setUploadOpen(true) : undefined} />}
    >
      <Stepper index={idx} />
      {error && (
        <p role="alert" className="flex items-center gap-3 text-sm text-danger">
          {error.message}
          <Button variant="outline" onClick={() => void reload()}>
            Try again
          </Button>
        </p>
      )}
      <ChatThread pc={pc} projectStatus={project.status} />
      {!onData && <StepArea screen={screen} project={project} onChanged={reload} />}
      {onData && (
        <div className="flex flex-col gap-3">
          <Button
            variant="outline"
            className="w-fit"
            aria-expanded={uploadOpen}
            onClick={() => setUploadOpen((o) => !o)}
          >
            {uploadOpen ? <ChevronUp aria-hidden /> : <ChevronDown aria-hidden />}
            {uploadOpen ? "Hide the upload option" : "Or upload my own CSV"}
          </Button>
          {uploadOpen && <UploadPanel projectId={project.id} onChanged={reload} />}
        </div>
      )}
      <div ref={bottom} />
    </InlineChatFrame>
  );
}
