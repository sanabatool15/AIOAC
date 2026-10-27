"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  CircleHelp,
  Gauge,
  KeyRound,
  LogOut,
  Receipt,
  Settings,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { logout } from "@/lib/mock-api";
import type { Shell } from "@/lib/types";
import { cn } from "@/lib/utils";

const rowClass =
  "flex w-full items-center gap-2 rounded-lg px-2.5 py-[7px] text-left text-sm leading-[normal] text-ink hover:bg-white focus-visible:outline-2 focus-visible:outline-brand [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-ink-2";

// Screen 20: user menu popover (opens upward from the sidebar user card).
export function UserMenu({ user }: { user: Shell["user"] }) {
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

  const link = (href: string, label: string, icon: React.ReactNode) => (
    <Link
      href={href}
      role="menuitem"
      className={rowClass}
      onClick={() => setOpen(false)}
    >
      {icon}
      <span className="min-w-px flex-1">{label}</span>
    </Link>
  );

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
          {user.name.charAt(0)}
        </span>
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-medium leading-[18px] text-ink">
            {user.name}
          </span>
          <span className="text-xs leading-4 text-muted">{user.plan}</span>
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
          <div className="flex flex-col gap-0.5 p-2.5 text-sm leading-[normal]">
            <span className="font-semibold text-ink">{user.name}</span>
            <span className="truncate text-muted">{user.email}</span>
          </div>
          <div className="flex items-center justify-between gap-2 rounded-lg p-2.5">
            <div className="flex flex-col gap-px leading-[normal]">
              <span className="text-sm font-semibold whitespace-nowrap text-ink">
                {user.plan}
              </span>
              <span className="text-[11px] whitespace-nowrap text-muted">
                {user.usage}
              </span>
            </div>
            <Link
              href="/billing/plan"
              onClick={() => setOpen(false)}
              className={cn(
                buttonVariants({ size: "md" }),
                "h-8 shrink-0 rounded-[9px] px-3 text-[13px] shadow-glow",
              )}
            >
              Upgrade
            </Link>
          </div>
          {link("/settings/keys", "Settings", <Settings aria-hidden />)}
          {link("/account/usage", "Usage and plan", <Gauge aria-hidden />)}
          {link(
            "/account/billing",
            "Billing and invoices",
            <Receipt aria-hidden />,
          )}
          {link("/settings/keys", "API keys", <KeyRound aria-hidden />)}
          <button
            type="button"
            role="menuitem"
            className={rowClass}
            onClick={() => {
              setOpen(false);
              toast("Help and feedback opens in the full product.");
            }}
          >
            <CircleHelp aria-hidden />
            <span className="min-w-px flex-1">Help and feedback</span>
          </button>
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
