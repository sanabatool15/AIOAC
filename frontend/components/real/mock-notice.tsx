"use client";
import Link from "next/link";
import { USE_MOCK_API } from "@/lib/config";

// The PayPal return pages only exist for the real backend. In mock mode the fake PayPal window is used.
export function MockModeNotice({ children }: { children: React.ReactNode }) {
  if (!USE_MOCK_API) return <>{children}</>;
  return (
    <section className="flex flex-1 items-start justify-center p-8">
      <p className="text-sm text-muted">
        This page is only used with the real backend (NEXT_PUBLIC_USE_MOCK_API=false).{" "}
        <Link href="/" className="font-semibold text-brand-ink underline">
          Go home
        </Link>
      </p>
    </section>
  );
}
