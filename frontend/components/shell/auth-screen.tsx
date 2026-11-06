"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import * as real from "@/lib/api-real";
import { DEMO_LOGIN } from "@/lib/config";
import { safeNext } from "@/lib/session";
import { pathAfterAuth } from "@/lib/welcome";

const { login, signup } = real;

const points = [
  "Free baseline before you commit",
  "PayPal holds a cap, never charges early",
  "Independent test on data the model never saw",
];

const copy = {
  login: {
    title: "Welcome back",
    sub: "Log in to continue your projects.",
    submit: "Log in",
    busy: "Logging in...",
    switchText: "New here? Sign up",
    switchHref: "/signup",
  },
  signup: {
    title: "Create your account",
    sub: "Start with a free baseline.",
    submit: "Sign up",
    busy: "Creating account...",
    switchText: "Have an account? Log in",
    switchHref: "/login",
  },
} as const;

// Screen 1: Login / sign up. After sign-in we go to the chat home.
export function AuthScreen({ mode }: { mode: "login" | "signup" }) {
  const router = useRouter();
  const c = copy[mode];
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      // Return to the page that sent us here; the path is checked to stay on this site.
      const next = safeNext(new URLSearchParams(window.location.search).get("next"));
      router.push(pathAfterAuth(mode, next));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen w-full bg-bg">
      <section className="hidden w-[640px] shrink-0 flex-col justify-center gap-5 p-16 lg:flex">
        <div className="flex items-center gap-2.5">
          <div
            className="size-[30px] rounded-lg bg-brand-gradient shadow-btn-primary"
            aria-hidden
          />
          <span className="text-xl font-semibold text-ink">AIOAC</span>
        </div>
        <h2 className="text-[28px] font-semibold leading-[52px] text-ink">
          Train with proof.
          <br />
          Pay for results.
        </h2>
        <p className="text-base leading-6 text-muted">
          Describe a prediction, add your data, and agree a target. If we miss
          it, you pay only the compute used.
        </p>
        <ul className="flex flex-col gap-2.5 pt-3">
          {points.map((p) => (
            <li key={p} className="flex items-center gap-2.5 text-sm text-ink">
              <span
                aria-hidden
                className="size-2 shrink-0 rounded-[4px] bg-brand-gradient"
              />
              {p}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex min-w-0 flex-1 items-center justify-center px-6">
        <form
          className="flex w-[380px] max-w-full flex-col gap-3.5 leading-[normal]"
          onSubmit={(e) => {
            e.preventDefault();
            run(() =>
              mode === "login"
                ? login(email, password)
                : signup(email, password),
            );
          }}
          noValidate
        >
          <h1 className="text-[28px] font-semibold text-ink">{c.title}</h1>
          <p className="text-sm text-muted">{c.sub}</p>

          <Field label="Email" htmlFor="email">
            <Input
              id="email"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={!!error}
            />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input
              id="password"
              type="password"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              aria-invalid={!!error}
            />
          </Field>

          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" disabled={busy}>
            {busy && (
              <LoaderCircle aria-hidden className="motion-safe:animate-spin" />
            )}
            {busy ? c.busy : c.submit}
          </Button>

          <div className="flex justify-end text-sm">
            <Link
              href={c.switchHref}
              className="font-semibold text-ink hover:underline"
            >
              {c.switchText}
            </Link>
          </div>

          {DEMO_LOGIN && (
            <Button
              type="button"
              variant="outline"
              size="lg"
              disabled={busy}
              onClick={() => run(() => real.demoLogin())}
            >
              Try the demo
            </Button>
          )}
        </form>
      </section>
    </main>
  );
}
