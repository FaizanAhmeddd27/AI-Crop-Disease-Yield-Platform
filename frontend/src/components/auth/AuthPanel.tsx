"use client";

/**
 * Single In/Up auth page — one card with two animated tabs (Log in / Register),
 * wired to the real backend via AuthProvider → POST /auth/login | /auth/register.
 * A successful auth redirects to `?next=` (default /dashboard).
 */

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { motion } from "framer-motion";

import { useAuth } from "@/components/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

type Mode = "login" | "register";

const inputClass =
  "h-11 w-full rounded-lg border border-hairline bg-surface px-3.5 text-sm text-ink " +
  "placeholder:text-ink-muted/60 focus-visible:border-transparent focus-visible:ring-2 focus-visible:ring-forest/50";
const labelClass = "font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted";

function Ornament({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M4 20c0-8 6-14 16-16 0 10-5 16-13 16H4Z" />
      <path d="M4 20c3-6 7-9 12-11" />
    </svg>
  );
}

export function AuthPanel() {
  const auth = useAuth();
  const router = useRouter();
  const params = useSearchParams();

  const [mode, setMode] = useState<Mode>(
    params.get("mode") === "register" ? "register" : "login",
  );
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only same-origin relative paths are honoured as the post-auth target.
  const nextPath = (() => {
    const raw = params.get("next");
    if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
    return "/dashboard";
  })();

  // Already signed in? Straight to the target, no form.
  useEffect(() => {
    if (auth.status === "authenticated") {
      router.replace(nextPath);
    }
  }, [auth.status, nextPath, router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);

    try {
      const form = event.currentTarget;
      const email = form.email.value.trim().toLowerCase();

      if (mode === "login") {
        await auth.login(email, form.password.value);
        router.replace(nextPath);
        return;
      }

      const password = form.password.value;
      if (password !== form.confirm.value) {
        setError("The passwords do not match.");
        return;
      }
      await auth.register({
        email,
        password,
        full_name: form.fullname.value.trim(),
      });
      router.replace(nextPath);
    } catch (cause) {
      const message =
        cause instanceof ApiError && cause.message
          ? cause.message
          : cause instanceof Error && cause.message
            ? cause.message
            : "Something went wrong. Please try again.";
      setError(message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto grid w-full max-w-5xl overflow-hidden rounded-[24px] border border-hairline bg-surface shadow-[0_24px_60px_rgba(6,71,52,0.10)] md:grid-cols-[1fr_1.1fr]">
      {/* brand panel */}
      <div className="relative hidden overflow-hidden bg-forest p-10 text-leaf md:flex md:flex-col">
        <Ornament className="absolute -right-8 -top-8 size-36 rotate-12 text-leaf/10" />
        <Ornament className="absolute -bottom-12 -left-12 size-48 -rotate-45 text-leaf/10" />

        <Image
          src="/logo.png"
          alt=""
          width={410}
          height={406}
          className="h-10 w-auto self-start"
        />

        <div className="mt-16 flex flex-col gap-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-leaf/60">
            One account for both tools
          </p>
          <h1 className="text-4xl font-medium leading-[1.05] tracking-[-1px]">
            Healthier crops,{" "}
            <em className="font-accent font-normal">clearer harvests.</em>
          </h1>
          <p className="max-w-xs text-sm leading-[1.55] text-leaf/80">
            Detect disease from one leaf photo and forecast yield before harvest —
            with every answer&apos;s reasoning shown.
          </p>
          <ul className="mt-4 flex flex-col gap-2 font-mono text-[10px] uppercase tracking-[0.12em] text-leaf/70">
            <li>38 disease classes</li>
            <li>36 punjab districts</li>
            <li>Wheat + maize</li>
          </ul>
        </div>

        <Image
          src="/mascot2.png"
          alt=""
          width={483}
          height={507}
          aria-hidden="true"
          className="mt-auto w-36 self-end lg:w-44"
        />
      </div>

      {/* form panel */}
      <div className="flex flex-col p-6 sm:p-10">
        <div className="mb-8 flex flex-col gap-1.5">
          <h2 className="text-2xl font-medium tracking-[-0.5px] text-forest">
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="text-sm text-ink-muted">
            {mode === "login"
              ? "Log in to reach your scans, forecasts and history."
              : "Register once — your scans and forecasts stay in history."}
          </p>
        </div>

        {/* animated tabs */}
        <div
          role="tablist"
          aria-label="Log in or register"
          className="relative mb-8 grid grid-cols-2 rounded-full border border-hairline bg-page p-1"
        >
          {(["login", "register"] as const).map((tab) => (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={mode === tab}
              onClick={() => {
                setMode(tab);
                setError(null);
              }}
              className={cn(
                "relative z-10 min-h-10 rounded-full px-4 text-sm font-medium transition-colors",
                mode === tab ? "text-forest" : "text-ink-muted hover:text-forest",
              )}
            >
              {mode === tab && (
                <motion.span
                  layoutId="auth-tab-pill"
                  transition={{ type: "spring", stiffness: 320, damping: 30 }}
                  aria-hidden="true"
                  className="absolute inset-0 -z-10 rounded-full bg-surface shadow-[0_2px_8px_rgba(6,71,52,0.08)] ring-1 ring-hairline"
                />
              )}
              {tab === "login" ? "Log in" : "Register"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          {mode === "register" && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="fullname" className={labelClass}>
                Full name
              </label>
              <input
                id="fullname"
                name="fullname"
                type="text"
                autoComplete="name"
                placeholder="Faizan Ahmed"
                className={inputClass}
              />
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label htmlFor="email" className={labelClass}>
              Email
            </label>
            <input
              id="email"
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@farm.example"
              className={inputClass}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="password" className={labelClass}>
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              minLength={6}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder={mode === "register" ? "At least 6 characters" : "••••••••"}
              className={inputClass}
            />
          </div>

          {mode === "register" && (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="confirm" className={labelClass}>
                Confirm password
              </label>
              <input
                id="confirm"
                name="confirm"
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                placeholder="Repeat the password"
                className={inputClass}
              />
            </div>
          )}

          {error && (
            <p
              role="alert"
              className="rounded-lg bg-risk-high/10 px-3 py-2 text-sm text-risk-high"
            >
              {error}
            </p>
          )}

          <Button type="submit" size="lg" disabled={pending} aria-busy={pending} className="mt-1">
            {pending
              ? mode === "login"
                ? "Signing in…"
                : "Creating account…"
              : mode === "login"
                ? "Log in"
                : "Create account"}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs leading-[1.5] text-ink-muted">
          Zenvy is decision support only — confirm with a local agronomist.{" "}
          <span className="block sm:inline sm:before:content-['·_']">Bound to the honest numbers.</span>
        </p>
      </div>
    </div>
  );
}
