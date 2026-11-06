"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut } from "lucide-react";
import { useToast } from "@/components/ui/toast";
import { logout } from "@/lib/api-real";
import { useRealUser } from "@/lib/hooks";
import { NAV_ITEMS } from "@/lib/nav";

const rowClass =
  "flex w-full items-center gap-2 rounded-lg px-2.5 py-[7px] text-left text-sm leading-[normal] text-ink hover:bg-white focus-visible:outline-2 focus-visible:outline-brand [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-ink-2";

// User menu popover (opens upward from the sidebar user card): the signed-in email and Log out.
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
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        trigger.current?.focus();
      }
    };
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (panel.current?.contains(t) || trigger.current?.contains(t)) return;
      setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
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
  return (
    <>
      <button
        ref={trigger}
        type="button"
        aria-label="Open user menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2.5 rounded-[10px] border border-border bg-card p-2.5 text-left shadow-card"
      >
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-surface text-sm text-muted">
          {email.charAt(0).toUpperCase()}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-medium leading-[18px] text-ink">
          {email}
        </span>
        <ChevronDown aria-hidden size={14} className="text-ink-2" />
      </button>

      {open && (
        <div
          ref={panel}
          role="menu"
          aria-label="User menu"
          className="fixed bottom-2 left-4 z-40 flex w-[232px] flex-col gap-0.5 rounded-xl border border-border bg-surface p-2 shadow-menu"
        >
          <div className="p-2.5 text-sm leading-[normal]">
            <span className="block truncate text-muted">{email}</span>
          </div>
          <div role="separator" className="h-px w-full bg-border" />
          {NAV_ITEMS.map((n) => (
            <Link key={n.href} href={n.href} role="menuitem" onClick={() => setOpen(false)} className={rowClass}>
              <span className="min-w-px flex-1">{n.label}</span>
            </Link>
          ))}
          <div role="separator" className="h-px w-full bg-border" />
          <button
            type="button"
            role="menuitem"
            disabled={busy}
            onClick={logOut}
            className={rowClass}
          >
            <LogOut aria-hidden />
            <span className="min-w-px flex-1">Log out</span>
          </button>
        </div>
      )}
    </>
  );
}
