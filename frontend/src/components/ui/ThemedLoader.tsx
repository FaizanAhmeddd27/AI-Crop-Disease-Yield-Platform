"use client";

import { DotLottieReact } from "@lottiefiles/dotlottie-react";

import { cn } from "@/lib/utils";

interface ThemedLoaderProps {
  label?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}

const sizes = {
  sm: "h-20 w-20",
  md: "h-36 w-36",
  lg: "h-52 w-52",
} as const;

export function ThemedLoader({
  label = "Loading your crop workspace",
  className,
  size = "md",
}: ThemedLoaderProps) {
  return (
    <div
      className={cn("flex flex-col items-center justify-center gap-3 text-center", className)}
      role="status"
      aria-live="polite"
    >
      <div className={cn("relative", sizes[size])} aria-hidden="true">
        <DotLottieReact src="/loading.lottie" loop autoplay />
        <span className="pointer-events-none absolute left-1/2 top-[39%] z-20 flex h-[11%] w-[38%] -translate-x-1/2 items-center justify-between loader-face-bob">
          <span className="h-[82%] w-[20%] rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.9)]" />
          <span className="h-[34%] w-[18%] rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.9)]" />
          <span className="h-[82%] w-[20%] rounded-full bg-white shadow-[0_0_4px_rgba(255,255,255,0.9)]" />
        </span>
      </div>
      {label && (
        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
          {label}
        </p>
      )}
    </div>
  );
}
