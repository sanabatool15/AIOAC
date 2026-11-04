"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { listProjects } from "@/lib/api-real";
import { cn } from "@/lib/utils";

// Real-mode sidebar: new project + your projects from the backend. No login, plans, keys or sharing.
export function RealSidebar() {
  const pathname = usePathname();
  const [items, setItems] = useState<{ id: string; goal: string }[]>([]);
  useEffect(() => {
    let alive = true;
    listProjects()
      .then((r) => alive && setItems(r.slice(0, 20)))
      .catch(() => alive && setItems([]));
    return () => {
      alive = false;
    };
  }, [pathname]);
  return (
    <nav aria-label="Projects" className="flex w-[260px] shrink-0 flex-col gap-3 border-r border-border bg-card p-4">
      <p className="text-base font-semibold text-ink">AIOAC</p>
      <Link href="/" className="rounded-lg bg-brand-tint px-3 py-2 text-sm font-semibold text-brand-ink">
        + New project
      </Link>
      <ul className="flex min-h-0 flex-col gap-1 overflow-y-auto">
        {items.map((p) => (
          <li key={p.id}>
            <Link
              href={`/c/${p.id}`}
              className={cn(
                "block truncate rounded-lg px-3 py-1.5 text-sm text-ink-2 hover:bg-surface",
                pathname === `/c/${p.id}` && "bg-surface font-semibold text-ink",
              )}
            >
              {p.goal}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
