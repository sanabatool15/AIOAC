"use client";
import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronsUpDown, LogOut } from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { logout } from "@/lib/api-real";
import { useRealUser } from "@/lib/hooks";
import { NAV_ITEMS } from "@/lib/nav";

const rowClass =
  "flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-body text-ink hover:bg-bg focus-visible:bg-bg [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-ink-2";

// User menu popover (opens upward from the sidebar user card): the signed-in email, the same pages as the sidebar
// (same icons) and Log out. Arrow keys move between items; Esc closes it and returns focus to the button.
export function UserMenu() {
  const user = useRealUser();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    if (!open) return;
    const items = () => Array.from(panel.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([disabled])') ?? []);
    items()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // Capture phase + stop: an enclosing drawer must not also close on this Esc.
        e.stopPropagation();
        e.preventDefault();
        setOpen(false);
        trigger.current?.focus();
        return;
      }
      if (e.key === "ArrowDown" || e.key === "ArrowUp" || e.key === "Home" || e.key === "End") {
        const list = items();
        if (list.length === 0) return;
        e.preventDefault();
        const at = list.indexOf(document.activeElement as HTMLElement);
        const next =
          e.key === "Home" ? 0 : e.key === "End" ? list.length - 1 : e.key === "ArrowDown" ? (at + 1) % list.length : (at <= 0 ? list.length : at) - 1;
        list[next].focus();
      }
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panel.current?.contains(t) || trigger.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  async function logOut() {
    setBusy(true);
    try {
      await logout();
      setOpen(false);
      router.push("/login");
    } catch {
      toast("Could not log out. Try again.", "error");
    } finally {
      setBusy(false);
    }
  }

  const email = user?.email ?? "";
  // A name from the part of the address before the @: "sana.batool6678" becomes "Sana Batool".
  const name =
    email
      .split("@")[0]
      .replace(/[0-9_.\-]+/g, " ")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(" ") || "Your account";
  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-label="Open user menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-lg p-2 text-left transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
      >
        <Image src="/avatar.png" alt="" width={32} height={32} className="size-8 shrink-0 rounded-full border border-border object-cover" />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-body font-medium text-ink">{name}</span>
          <span className="truncate text-micro text-muted">{email}</span>
        </span>
        <ChevronsUpDown aria-hidden size={14} className="shrink-0 text-muted" />
      </button>

      {open && (
        <div
          ref={panel}
          role="menu"
          aria-label="User menu"
          className="fixed bottom-2 left-4 z-50 flex w-60 max-w-[calc(100vw-2rem)] flex-col gap-0.5 rounded-xl border border-border bg-surface p-2 shadow-popover"
        >
          <div className="p-2.5 text-body">
            <span className="block truncate text-muted">{email}</span>
          </div>
          <div role="separator" className="h-px w-full bg-border" />
          {NAV_ITEMS.map((n) => (
            <Link key={n.href} href={n.href} role="menuitem" onClick={() => setOpen(false)} className={rowClass}>
              <n.icon aria-hidden />
              <span className="min-w-px flex-1">{n.label}</span>
            </Link>
          ))}
          <div role="separator" className="h-px w-full bg-border" />
          <button type="button" role="menuitem" disabled={busy} onClick={logOut} className={rowClass}>
            <LogOut aria-hidden />
            <span className="min-w-px flex-1">Log out</span>
          </button>
        </div>
      )}
    </>
  );
}
