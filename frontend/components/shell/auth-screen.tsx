"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import * as real from "@/lib/api-real";
import { DEMO_LOGIN } from "@/lib/config";
import { passwordInputType } from "@/lib/goal";
import { safeNext } from "@/lib/session";
import { pathAfterAuth } from "@/lib/welcome";
import { Logo } from "./logo";

const { login, signup } = real;

const points = [
  "Free baseline before you commit",
  "PayPal holds a cap, never charges early",
  "Independent test on data the model never saw",
];

const copy = {
  login: {
    title: "Welcome back",
    sub: "Log in to continue your chats.",
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
  const [showPw, setShowPw] = useState(false);
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
      <section className="hidden shrink-0 flex-col justify-center gap-5 p-16 lg:flex lg:w-1/2">
        <Logo />
        <p className="text-title text-ink">Train with proof. Pay for results.</p>
        <p className="max-w-form text-body text-muted">
          Describe a prediction, add your data and agree a target. If we miss it, you pay only the compute used.
        </p>
        <ul className="flex flex-col gap-2.5 pt-3">
          {points.map((p) => (
            <li key={p} className="flex items-center gap-2.5 text-body text-ink">
              <span aria-hidden className="size-2 shrink-0 rounded-full bg-brand" />
              {p}
            </li>
          ))}
        </ul>
      </section>

      <section className="flex min-w-0 flex-1 items-center justify-center px-6">
        <form
          className="flex w-full max-w-sm flex-col gap-3.5"
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
          <Logo className="lg:hidden" />
          <h1 className="text-title text-ink">{c.title}</h1>
          <p className="text-body text-muted">{c.sub}</p>

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
            <div className="relative">
              <Input
                id="password"
                type={passwordInputType(showPw)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                placeholder={mode === "signup" ? "At least 8 characters" : "••••••••"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={!!error}
                className="pr-11"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={showPw ? "Hide characters" : "Show characters"}
                aria-pressed={showPw}
                onClick={() => setShowPw((v) => !v)}
                className="absolute right-0 top-0"
              >
                {showPw ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
              </Button>
            </div>
          </Field>

          {error && (
            <p role="alert" className="text-body text-danger">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" block disabled={busy}>
            {busy && (
              <LoaderCircle aria-hidden className="motion-safe:animate-spin" />
            )}
            {busy ? c.busy : c.submit}
          </Button>

          <div className="flex justify-end text-body">
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
              block
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
