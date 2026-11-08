import type { ReactNode, RefObject } from "react";

// The one order of the project page, the same on every step: progress, the current step, then the conversation (oldest
// first, newest last, right above the composer). Step cards never move to the other side of the thread.
export const CHAT_REGIONS = ["progress", "step", "conversation"] as const;

// True when the project moved to a different step and it is not the first render: then the step region is brought into
// view so the new card is not left above the fold.
export function stepChanged(previous: string | null, next: string): boolean {
  return previous !== null && previous !== next;
}

export function ChatLayout({
  progress,
  step,
  conversation,
  stepRef,
  endRef,
}: {
  progress: ReactNode;
  step: ReactNode;
  conversation: ReactNode;
  stepRef?: RefObject<HTMLDivElement | null>;
  endRef?: RefObject<HTMLDivElement | null>;
}) {
  return (
    <>
      <div data-region="progress" className="sticky top-0 z-10 -mt-6 bg-bg pb-3 pt-6">
        {progress}
      </div>
      <section ref={stepRef} data-region="step" aria-label="Current step" className="flex scroll-mt-16 flex-col gap-4 empty:hidden">
        {step}
      </section>
      <div data-region="conversation" className="flex flex-col gap-4">
        {conversation}
      </div>
      <div ref={endRef} aria-hidden />
    </>
  );
}
