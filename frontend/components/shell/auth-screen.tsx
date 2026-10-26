"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { forgotPassword, login, oauthLogin, signup } from "@/lib/mock-api";

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
  const [notice, setNotice] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      router.push("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
    }
  }

  async function onForgot() {
    setError(null);
    setNotice(null);
    try {
      await forgotPassword(email);
      setNotice("If that email has an account, we sent a reset link.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
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
          it, you pay $0.
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

          <Button
            type="button"
            variant="outline"
            size="lg"
            disabled={busy}
            onClick={() => run(() => oauthLogin("google"))}
          >
            Continue with Google
          </Button>
          <Button
            type="button"
            variant="outline"
            size="lg"
            disabled={busy}
            onClick={() => run(() => oauthLogin("github"))}
          >
            Continue with GitHub
          </Button>

          <div
            className="flex items-center gap-3"
            role="separator"
            aria-label="or"
          >
            <span className="h-px flex-1 bg-border" />
            <span className="text-sm text-muted">or</span>
            <span className="h-px flex-1 bg-border" />
          </div>

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
              placeholder="••••••••"
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
          {notice && (
            <p role="status" className="text-sm text-success">
              {notice}
            </p>
          )}

          <Button type="submit" size="lg" disabled={busy}>
            {busy && (
              <LoaderCircle aria-hidden className="motion-safe:animate-spin" />
            )}
            {busy ? c.busy : c.submit}
          </Button>

          <div className="flex items-start justify-between text-sm">
            {mode === "login" ? (
              <button
                type="button"
                onClick={onForgot}
                className="text-muted hover:text-ink"
              >
                Forgot password?
              </button>
            ) : (
              <span />
            )}
            <Link
              href={c.switchHref}
              className="font-semibold text-ink hover:underline"
            >
              {c.switchText}
            </Link>
          </div>

          <p className="text-xs text-muted">
            Demo sign-in. Google and GitHub buttons are dummy OAuth for now.
          </p>
        </form>
      </section>
    </main>
  );
}
