"use client";
import { useEffect, useRef } from "react";
import { isNearBottom, shouldFollow } from "@/lib/scroll";

function scrollParent(el: HTMLElement | null): HTMLElement | null {
  for (let n = el?.parentElement ?? null; n; n = n.parentElement) {
    const o = getComputedStyle(n).overflowY;
    if (o === "auto" || o === "scroll") return n;
  }
  return null;
}

// Puts the newest chat message next to the composer after each change, but only when the person is reading the end of
// the page or has just sent something. If they scrolled up on purpose, nothing moves. `end` is an element placed right
// after the last message.
export function useFollowChat(end: React.RefObject<HTMLElement | null>, changeKey: string, lastIsUserMessage: boolean, ready: boolean) {
  const near = useRef(true);
  const seeded = useRef(false);
  useEffect(() => {
    const box = scrollParent(end.current);
    if (!box) return;
    const onScroll = () => {
      near.current = isNearBottom(box);
    };
    box.addEventListener("scroll", onScroll, { passive: true });
    return () => box.removeEventListener("scroll", onScroll);
  }, [end]);
  useEffect(() => {
    if (!ready) return;
    if (!seeded.current) {
      seeded.current = true; // opening the page: show the newest message, next to the composer
      end.current?.scrollIntoView?.({ block: "end" });
      return;
    }
    if (shouldFollow(near.current, lastIsUserMessage)) {
      end.current?.scrollIntoView?.({ block: "end" });
      near.current = true;
    }
  }, [end, changeKey, lastIsUserMessage, ready]);
}
