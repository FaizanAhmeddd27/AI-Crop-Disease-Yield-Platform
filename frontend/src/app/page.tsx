"use client";

import Image from "next/image";
import Link from "next/link";
import {
  motion,
  useInView,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion";
import type { ReactNode } from "react";
import { useEffect, useId, useRef, useState } from "react";

import { ButtonLink } from "@/components/ui/Button";

/* ── Shared bits ─────────────────────────────────────────────────────────── */

function Label({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <p
      className={`font-mono text-xs uppercase tracking-[0.08em] text-forest/70 ${className}`}
    >
      {children}
    </p>
  );
}

/** Fade-up-on-scroll wrapper (DESIGN.md motion: 12px, once, no loops). */
function FadeUp({ children, className = "" }: { children: ReactNode; className?: string }) {
  const prefersReduced = useReducedMotion();

  return (
    <motion.section
      initial={{ opacity: 0, y: prefersReduced ? 0 : 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.45, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.section>
  );
}

function ConfidenceBar({ pct }: { pct: number }) {
  return (
    <div className="h-2 w-full rounded-full bg-brand-100">
      <div className="h-2 rounded-full bg-forest transition-[width] duration-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Severity pill — status colour as a 15% fill with full-colour text (DESIGN.md). */
function SeverityBadge({ level }: { level: "low" | "moderate" | "severe" }) {
  const styles =
    level === "severe"
      ? "bg-risk-high/15 text-risk-high"
      : level === "moderate"
        ? "bg-risk-medium/15 text-risk-medium"
        : "bg-risk-low/15 text-risk-low";
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {level}
    </span>
  );
}

/**
 * Full-bleed wrapper: escapes the max-w-6xl main container to true viewport
 * width (100vw), safe against horizontal scrollbar because body clips overflow.
 */
function FullBleed({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`mx-[calc(50%_-_50vw)] ${className}`}>{children}</div>;
}

/** Gentle scroll parallax for showcase visuals. Off under reduced motion. */
function Parallax({
  children,
  range = 24,
  className = "",
}: {
  children: ReactNode;
  range?: number;
  className?: string;
}) {
  const prefersReduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "end start"],
  });
  const y = useTransform(scrollYProgress, [0, 1], [-range, range]);

  return (
    <div ref={ref} className={className}>
      <motion.div style={prefersReduced ? undefined : { y }}>{children}</motion.div>
    </div>
  );
}

/** Decorative flat leaf outline used as panel ornament — no gradients. */
function LeafOrnament({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={className}
      stroke="currentColor"
      strokeWidth={1}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M4 20c0-8 6-14 16-16 0 10-5 16-13 16H4Z" />
      <path d="M4 20c3-6 7-9 12-11" />
    </svg>
  );
}

/* ── Tape marquee: crossing ribbons, infinite opposite loops ─────────────── */

/** Four-point sparkle decoration, flat vector in theme colours. */
function Sparkle({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M12 0c.9 6.7 5.3 11.1 12 12-6.7.9-11.1 5.3-12 12-.9-6.7-5.3-11.1-12-12C6.7 11.1 11.1 6.7 12 0Z" />
    </svg>
  );
}

function TapeArrow({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M3 12h17M14 6l6 6-6 6" />
    </svg>
  );
}

function TapeRow({
  items,
  glyph,
  tapClass,
}: {
  items: readonly string[];
  glyph: "arrow" | "spark";
  tapClass: string;
}) {
  const Glyph = glyph === "arrow" ? TapeArrow : Sparkle;
  const sizeClass = glyph === "arrow" ? "size-5 sm:size-7" : "size-4 sm:size-5";

  return (
    /* overflow-hidden is the tape clip; type runs edge to edge */
    <div className={`overflow-hidden py-2.5 sm:py-3 ${tapClass}`}>
      <div className={`flex w-max ${glyph === "arrow" ? "animate-marquee" : "animate-marquee-rev"}`}>
        {[0, 1].map((half) => (
          <ul key={half} aria-hidden={half === 1} className="flex items-center">
            {items.map((item) => (
              <li key={item} className="flex items-center">
                <span className="whitespace-nowrap px-6 text-[26px] font-black uppercase leading-none tracking-[-0.02em] sm:px-8 sm:text-4xl">
                  {item}
                </span>
                <Glyph className={glyph === "arrow" ? "size-5 shrink-0 sm:size-7" : sizeClass} />
              </li>
            ))}
          </ul>
        ))}
      </div>
    </div>
  );
}

function TapeMarquee() {
  return (
    <section
      aria-label="What Zenvy covers"
      className="relative mx-[calc(50%_-_50vw)] overflow-x-clip py-12 sm:py-16"
    >
      <p className="sr-only">
        38 disease classes, 36 punjab districts, wheat and maize, grad-cam overlays, shap
        explanations, open-meteo weather.
      </p>

      {/* flat sparkles scattered on the pale page */}
      <Sparkle className="absolute left-[6%] top-10 size-5 text-forest/25" />
      <Sparkle className="absolute right-[14%] top-6 size-3 text-forest/20" />
      <Sparkle className="absolute bottom-8 left-[22%] size-4 text-forest/25" />
      <Sparkle className="absolute bottom-16 right-[8%] size-6 text-forest/15" />
      <Sparkle className="absolute right-[40%] top-1/2 size-4 text-forest/20" />

      {/* ribbon A — dark forest tape, scrolls left */}
      <div className="relative z-0 -mx-10 -rotate-[4deg]">
        <TapeRow
          tapClass="bg-forest text-leaf shadow-[0_10px_28px_rgba(6,71,52,0.22)]"
          glyph="arrow"
          items={["detect disease", "forecast yield", "grad-cam overlay", "shap drivers"]}
        />
      </div>

      {/* ribbon B — white tape crossing it, scrolls right */}
      <div className="relative z-10 -mx-10 -mt-7 rotate-[2.5deg] sm:-mt-9">
        <TapeRow
          tapClass="border-y-2 border-forest/10 bg-surface text-forest shadow-[0_8px_20px_rgba(6,71,52,0.12)]"
          glyph="spark"
          items={["wheat", "maize", "38 classes", "36 districts"]}
        />
      </div>
    </section>
  );
}

/* ── How it works: a journey — auto-advancing, each step has a live demo ─── */

/** Step 1 demo: a scan beam sweeping the uploaded leaf. */
function StepVisualScan({ active, reduced }: { active: boolean; reduced: boolean }) {
  const run = active && !reduced;

  return (
    <div
      aria-hidden="true"
      className="relative h-12 w-24 overflow-hidden rounded-lg border border-dashed border-forest/50 bg-surface"
    >
      <LeafOrnament className="absolute left-1/2 top-1/2 size-7 -translate-x-1/2 -translate-y-1/2 text-forest" />
      <motion.span
        className="absolute inset-x-1 h-0.5 rounded-full bg-forest"
        animate={{ top: run ? ["12%", "78%", "12%"] : "26%" }}
        transition={
          run ? { duration: 2, repeat: Infinity, ease: "easeInOut" } : undefined
        }
      />
    </div>
  );
}

/** Step 2 demo: inference bars pulsing like a model at work. */
function StepVisualRun({ active, reduced }: { active: boolean; reduced: boolean }) {
  const run = active && !reduced;

  return (
    <div aria-hidden="true" className="flex h-12 items-end gap-1.5">
      {[0.45, 0.75, 0.55, 0.95, 0.7, 0.5].map((h, i) => (
        <motion.span
          key={i}
          className="w-2.5 rounded-sm bg-forest/85"
          style={{ height: `${Math.round(h * 100)}%`, transformOrigin: "bottom" }}
          animate={run ? { scaleY: [1, 0.3, 1] } : { scaleY: 0.5 }}
          transition={
            run
              ? { duration: 1.5, repeat: Infinity, delay: i * 0.13, ease: "easeInOut" }
              : undefined
          }
        />
      ))}
    </div>
  );
}

/** Step 3 demo: centred-zero SHAP bars drawing themselves from the midline. */
function StepVisualWhy({ active, reduced }: { active: boolean; reduced: boolean }) {
  const run = active && !reduced;

  return (
    <div aria-hidden="true" className="relative h-12 w-24">
      <span className="absolute inset-x-0 top-1/2 h-px bg-forest/25" />
      {[0.65, -0.35, 0.45, -0.2, 0.3].map((v, i) => (
        <motion.span
          key={i}
          className={`absolute top-1/2 h-1.5 -translate-y-1/2 rounded-sm ${
            v >= 0 ? "left-1/2 bg-forest" : "right-1/2 bg-forest/40"
          }`}
          animate={
            run
              ? { width: [0, `${Math.abs(v) * 70}px`], opacity: [0.3, 1, 1] }
              : { width: `${Math.abs(v) * 70}px` }
          }
          transition={
            run
              ? {
                  duration: 1.1,
                  repeat: Infinity,
                  repeatDelay: 0.9,
                  delay: i * 0.12,
                  ease: "easeOut",
                }
              : undefined
          }
        />
      ))}
    </div>
  );
}

const STEP_VISUALS = [StepVisualScan, StepVisualRun, StepVisualWhy] as const;

function HowItWorks() {
  const prefersReduced = useReducedMotion();
  const [active, setActive] = useState(0);

  useEffect(() => {
    // One step every 4 s — a slow, readable pulse, not a distraction.
    if (prefersReduced) return undefined;
    const timer = window.setInterval(() => {
      setActive((current) => (current + 1) % STEPS.length);
    }, 4000);
    return () => window.clearInterval(timer);
  }, [prefersReduced]);

  const nodePositions = [16.666, 50, 83.333];

  return (
    <div>
      <Label className="mb-8 text-center">How it works</Label>

      {/* journey track: dashed path, three nodes, a dot that travels between them */}
      <div aria-hidden="true" className="relative mb-1 hidden h-6 md:block">
        <span className="absolute inset-x-3 top-1/2 border-t-2 border-dashed border-hairline" />
        {nodePositions.map((left, i) => (
          <span
            key={left}
            className={`absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 transition-colors duration-300 ${
              i === active ? "border-forest bg-leaf" : "border-hairline bg-page"
            }`}
            style={{ left: `${left}%` }}
          />
        ))}
        {/* the traveler */}
        <motion.span
          className="absolute top-1/2"
          animate={{ left: `${nodePositions[active]}%` }}
          transition={{ type: "spring", stiffness: 140, damping: 18 }}
        >
          <span className="block size-5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-forest ring-4 ring-leaf" />
        </motion.span>
      </div>

      <ol className="grid gap-3 md:grid-cols-3">
        {STEPS.map((step, i) => {
          const isActive = i === active;
          const Visual = STEP_VISUALS[i];

          return (
            <li key={step.n} className="contents">
              <button
                type="button"
                onClick={() => {
                  setActive(i);
                }}
                aria-current={isActive ? "step" : undefined}
                className={`flex h-full w-full flex-col items-start gap-3 rounded-2xl border p-6 text-left transition-all duration-300 ${
                  isActive
                    ? "border-hairline bg-brand-100/70 shadow-[0_10px_24px_rgba(6,71,52,0.08)]"
                    : "border-transparent hover:border-hairline hover:bg-brand-100/30"
                }`}
              >
                <span className="flex w-full items-center justify-between">
                  <span
                    className={`font-mono text-[32px] font-semibold leading-none tracking-[-0.04em] transition-colors ${
                      isActive ? "text-forest" : "text-forest/30"
                    }`}
                  >
                    {step.n}
                  </span>
                  <Sparkle
                    className={`size-5 text-forest transition-opacity ${
                      isActive ? "opacity-100" : "opacity-0"
                    }`}
                  />
                </span>

                {/* live micro-demo: only runs while this step is highlighted */}
                <Visual active={isActive} reduced={prefersReduced === true} />

                <h3
                  className={`text-xl font-medium tracking-[-0.3px] transition-colors ${
                    isActive ? "text-forest" : "text-forest/70"
                  }`}
                >
                  {step.title}
                </h3>
                <p
                  className={`text-sm leading-[1.5] transition-colors ${
                    isActive ? "text-ink" : "text-ink-muted"
                  }`}
                >
                  {step.body}
                </p>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

const STEPS = [
  {
    n: "01",
    title: "Add your data",
    body: "A leaf photo, or your crop and location.",
  },
  {
    n: "02",
    title: "The model runs",
    body: "An image classifier or a yield forecaster, using weather and soil data.",
  },
  {
    n: "03",
    title: "See why",
    body: "The result, plus the explanation behind it.",
  },
] as const;

/* ── Model numbers: editorial count-up band, full width ──────────────────── */

function FieldSignals() {
  const signals = [
    {
      value: 38,
      label: "disease classes",
      eyebrow: "01 · Vision",
      note: "The leaf classifier checks the supported crop and disease set before it gives a result.",
      tone: "bg-leaf text-forest",
      size: "w-[min(82vw,34rem)]",
    },
    {
      value: 36,
      label: "Punjab districts",
      eyebrow: "02 · Reach",
      note: "Weather inputs resolve district by district from a live Open-Meteo feed.",
      tone: "bg-[#d6efbd] text-forest",
      size: "w-[min(70vw,24rem)]",
    },
    {
      value: "02",
      label: "supported crops",
      eyebrow: "03 · Crops",
      note: "Wheat and maize are the first production pathways in the yield model.",
      tone: "bg-[#b8dc9c] text-forest",
      size: "w-[min(70vw,24rem)]",
    },
    {
      value: "CAM",
      label: "heatmap evidence",
      eyebrow: "04 · Evidence",
      note: "Grad-CAM shows which part of the leaf influenced the diagnosis.",
      tone: "bg-[#8fbd80] text-forest",
      size: "w-[min(70vw,24rem)]",
    },
    {
      value: "SHAP",
      label: "yield drivers",
      eyebrow: "05 · Forecast",
      note: "The forecast includes the factors that pushed the estimate up or down.",
      tone: "bg-[#6ba875] text-leaf",
      size: "w-[min(70vw,24rem)]",
    },
  ] as const;
  const cards = [...signals, ...signals];

  return (
    <FullBleed className="relative overflow-hidden bg-forest text-leaf">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 opacity-30"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(224,255,194,0.22) 1px, transparent 0)",
          backgroundSize: "28px 28px",
          maskImage: "linear-gradient(to bottom, black, transparent 90%)",
          WebkitMaskImage: "linear-gradient(to bottom, black, transparent 90%)",
        }}
      />

      <div className="relative mx-auto max-w-6xl px-4 py-14 sm:py-20">
        <div className="flex flex-col gap-5 border-b border-leaf/20 pb-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-leaf/60">
              The field signals behind Zenvy
            </p>
            <h2 className="mt-3 max-w-[16ch] text-3xl font-medium leading-[0.98] tracking-[-0.04em] sm:text-5xl">
              A clearer read on what the models can see.
            </h2>
          </div>
          <p className="max-w-[30ch] text-sm leading-[1.55] text-leaf/65 sm:text-right">
            Move through the coverage, evidence, and data that shape each answer.
          </p>
        </div>

        <div
          className="group mt-8 overflow-hidden"
          aria-label="Zenvy model coverage and explanation signals"
          tabIndex={0}
        >
          <div className="flex w-max gap-3 py-2 animate-signal-rail group-hover:[animation-play-state:paused] group-focus-within:[animation-play-state:paused]">
            {cards.map((signal, index) => (
              <article
                key={`${signal.eyebrow}-${index}`}
                className={`flex min-h-[270px] shrink-0 flex-col justify-between rounded-[24px] p-5 shadow-[0_18px_40px_rgba(0,0,0,0.12)] transition-transform duration-300 hover:-translate-y-1 sm:min-h-[300px] sm:p-7 ${signal.size} ${signal.tone}`}
              >
                <div className="flex items-center justify-between gap-4">
                  <span className="font-mono text-[10px] uppercase tracking-[0.14em] opacity-65">
                    {signal.eyebrow}
                  </span>
                  <span aria-hidden="true" className="h-px w-10 bg-current opacity-35" />
                </div>
                <div>
                  <p className="font-accent text-[70px] leading-[0.78] tracking-[-0.06em] sm:text-[92px]">
                    {signal.value}
                  </p>
                  <h3 className="mt-6 font-mono text-[11px] font-semibold uppercase tracking-[0.14em]">
                    {signal.label}
                  </h3>
                  <p className="mt-3 max-w-[32ch] text-sm leading-[1.5] opacity-75">{signal.note}</p>
                </div>
              </article>
            ))}
          </div>
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-leaf/20 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-leaf/50">
            Auto-scroll · hover or focus to pause
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-leaf/35">
            Coverage from the shipped models
          </p>
        </div>
      </div>
    </FullBleed>
  );
}

/* ── Product showcase: alternating rows with parallax app mocks ──────────── */

function DiseaseMock() {
  return (
    <div className="relative w-full min-w-0 rounded-[20px] bg-forest p-5 sm:p-7">
      <LeafOrnament className="absolute -right-6 -top-6 size-28 rotate-12 text-leaf/10" />
      <div className="grid min-w-0 items-center gap-4 sm:grid-cols-[auto_minmax(0,1fr)]">
        <div className="mx-auto grid size-32 shrink-0 place-items-center rounded-xl bg-page sm:size-36">
          <LeafCanvas withHeat className="h-24 w-24 sm:h-28 sm:w-28" />
        </div>
        <div className="min-w-0 rounded-xl bg-surface p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-ink">Leaf blight · disease found</p>
              <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
                Confidence 0.86
              </p>
            </div>
            <SeverityBadge level="moderate" />
          </div>
          <div className="mt-3">
            <ConfidenceBar pct={86} />
          </div>
          <p className="mt-3 flex min-w-0 items-center gap-2 border-t border-hairline pt-2.5 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
            <LeafOrnament className="size-3.5 shrink-0 text-forest" />
            <span aria-hidden="true" className="hidden truncate sm:inline">advice · cited advisory, not generated</span>
            <span className="truncate sm:hidden">cited advisory</span>
          </p>
        </div>
      </div>
    </div>
  );
}

function YieldMock() {
  return (
    <div className="min-w-0 w-full rounded-[20px] border border-hairline bg-surface p-5 shadow-[0_18px_40px_rgba(6,71,52,0.10)] sm:p-7">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
            Yield forecast · wheat · ludhiana
          </p>
          <p className="mt-1 font-accent text-5xl leading-none text-forest">
            4.02 <span className="text-2xl">t/ha</span>
          </p>
          <p className="mt-1.5 text-xs text-ink-muted">up from a 3.20 t/ha baseline</p>
        </div>
        <SeverityBadge level="low" />
      </div>
      <div className="mt-5 flex flex-col gap-2.5">
        {[
          { name: "w_rain_total_mm", v: 0.62 },
          { name: "soil_awc_pct", v: -0.28 },
          { name: "yield_lag1_tha", v: 0.19 },
        ].map((feature) => {
          const positive = feature.v >= 0;
          return (
            <div key={feature.name} className="flex items-center gap-2">
              <span className="w-24 shrink-0 truncate font-mono text-[10px] text-ink-muted">
                {feature.name}
              </span>
              <div className="relative h-2 flex-1">
                <span aria-hidden="true" className="absolute left-1/2 top-0 h-full w-px bg-hairline" />
                <div
                  className={`absolute top-0 h-2 rounded-sm ${positive ? "left-1/2 bg-forest" : "right-1/2 bg-ink-muted"}`}
                  style={{ width: `${Math.min(48, Math.abs(feature.v) * 60)}%` }}
                />
              </div>
              <span
                className={`w-12 shrink-0 text-right font-mono text-[10px] ${positive ? "text-forest" : "text-ink-muted"}`}
              >
                {positive ? "+" : "-"}
                {Math.abs(feature.v).toFixed(2)} t
              </span>
            </div>
          );
        })}
      </div>
      <p className="mt-4 border-t border-hairline pt-3 font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
        shap · top drivers behind the number
      </p>
    </div>
  );
}

function ProductShowcase() {
  return (
    <div className="flex flex-col gap-20 md:gap-28">
      {/* row 1 — detection, mock on the right */}
      <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
        <div className="flex min-w-0 flex-col gap-5">
          <Label>Detection</Label>
          <h2 className="text-[30px] font-medium leading-[1.05] tracking-[-1px] text-forest lg:text-[42px] lg:tracking-[-1.5px]">
            One photo in. A diagnosis and the{" "}
            <em className="font-accent font-normal">fix</em> out.
          </h2>
          <p className="max-w-md text-[17px] leading-[1.5] text-ink-muted">
            Scan a leaf with your phone. The classifier names the disease, scores how sure it
            is, and grades severity — so you know whether to treat the field or just watch it.
          </p>
          <ul className="flex flex-col gap-2.5 text-sm leading-[1.5] text-ink-muted">
            {[
              "38 classes covered, including the rare ones",
              "Confidence and severity on every scan",
              "Treatment steps from a cited advisory",
            ].map((point) => (
              <li key={point} className="flex items-start gap-2.5">
                <LeafOrnament className="mt-0.5 size-4 shrink-0 -rotate-45 text-forest" />
                {point}
              </li>
            ))}
          </ul>
          <div className="pt-2">
            <ButtonLink href="/dashboard" variant="ghost">
              Try detection
            </ButtonLink>
          </div>
        </div>
        <Parallax range={26} className="min-w-0 w-full">
          <DiseaseMock />
        </Parallax>
      </div>

      {/* row 2 — forecasting, mirrored, mock on the left */}
      <div className="grid items-center gap-10 lg:grid-cols-2 lg:gap-14">
        <Parallax range={20} className="min-w-0 w-full lg:order-1">
          <YieldMock />
        </Parallax>
        <div className="order-2 flex min-w-0 flex-col gap-5 lg:order-2">
          <Label>Forecasting</Label>
          <h2 className="text-[30px] font-medium leading-[1.05] tracking-[-1px] text-forest lg:text-[42px] lg:tracking-[-1.5px]">
            Know the yield{" "}
            <em className="font-accent font-normal">before</em> the combine does.
          </h2>
          <p className="max-w-md text-[17px] leading-[1.5] text-ink-muted">
            Enter your crop and district. Weather and soil are pulled in for you, the
            forecaster returns a number — and SHAP shows exactly what moved it.
          </p>
          <ul className="flex flex-col gap-2.5 text-sm leading-[1.5] text-ink-muted">
            {[
              "Wheat and maize, across 36 districts",
              "Weather and soil pulled automatically",
              "SHAP shows what pushed the forecast up or down",
            ].map((point) => (
              <li key={point} className="flex items-start gap-2.5">
                <LeafOrnament className="mt-0.5 size-4 shrink-0 -rotate-45 text-forest" />
                {point}
              </li>
            ))}
          </ul>
          <div className="pt-2">
            <ButtonLink href="/dashboard" variant="ghost">
              Try a forecast
            </ButtonLink>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Hero visual: a flat phone-frame "scan" mock ──────────────────────────── */

/** Flat leaf with a blurred Grad-CAM heat blob (used for before/after shots). */
function LeafCanvas({
  withHeat = false,
  tone = "light",
  className = "",
}: {
  withHeat?: boolean;
  tone?: "light" | "dark";
  className?: string;
}) {
  // Unique filter id per instance — multiple LeafCanvas components may share a page.
  const uid = useId();
  const filterId = `heat-blur${uid.replace(/[^a-zA-Z0-9]/g, "")}`;
  const dark = tone === "dark";

  return (
    <svg viewBox="0 0 96 96" fill="none" aria-hidden="true" className={className}>
      {withHeat ? (
        <defs>
          <filter id={filterId} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4.5" />
          </filter>
        </defs>
      ) : null}
      <path
        d="M20 76c0-26 17-43 48-48 0 30-15 48-38 48H20Z"
        className={dark ? "fill-[#8FCB74]" : "fill-forest"}
      />
      <path
        d="M20 76c9-18 21-28 34-34"
        className={dark ? "stroke-[#0B120E]" : "stroke-leaf"}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <path
        d="M38 60c6-8 12-13 18-16M30 68c4-5 8-9 12-11"
        className={dark ? "stroke-[#0B120E]" : "stroke-forest"}
        strokeWidth="1"
        strokeLinecap="round"
        opacity="0.5"
      />
      {withHeat ? (
        <g filter={`url(#${filterId})`}>
          <ellipse cx="58" cy="40" rx="12" ry="9" fill="#F2E23A" />
          <ellipse cx="59" cy="41" rx="8" ry="6" fill="#F2B53A" />
          <ellipse cx="60" cy="42" rx="4.5" ry="3.5" fill="#D9453B" />
        </g>
      ) : null}
    </svg>
  );
}

function HeroReport() {
  return (
    <div className="relative mx-auto w-full max-w-[640px] lg:max-w-none lg:scale-105">
      <Image
        src="/hero.png"
        alt="Farmer and crop assistant reviewing plant health"
        width={1536}
        height={1024}
        className="h-auto w-full object-contain"
        priority
      />
    </div>
  );
}

/* ── Explainability: a black field report on a dotted board ──────────────── */

function ReasoningSection() {
  const prefersReduced = useReducedMotion();
  const frameRef = useRef<HTMLDivElement>(null);
  const inView = useInView(frameRef, { once: true, margin: "-120px" });
  const run = inView && !prefersReduced;

  // Scroll-linked reveal: the report rises from below and settles into place.
  const { scrollYProgress } = useScroll({
    target: frameRef,
    offset: ["start 95%", "start 35%"],
  });
  const smooth = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 26,
    restDelta: 0.001,
  });
  const frameY = useTransform(smooth, [0, 1], [280, 0]);
  const frameScale = useTransform(smooth, [0, 1], [0.88, 1]);
  const frameRotate = useTransform(smooth, [0, 1], [8, 0]);
  const frameOpacity = useTransform(smooth, [0, 0.32], [0, 1]);

  const evidence = [
    { label: "Lesion margin", value: 0.62 },
    { label: "Chlorotic halo", value: 0.41 },
    { label: "Healthy tissue", value: 0.12 },
  ];

  return (
    <FullBleed className="relative overflow-hidden bg-page">
      {/* faint dot grid, faded towards the edges so it reads as texture, not wallpaper */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "radial-gradient(circle at 1px 1px, rgba(6,71,52,0.12) 1px, transparent 0)",
          backgroundSize: "24px 24px",
          maskImage:
            "radial-gradient(ellipse 85% 75% at 50% 38%, black 20%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 85% 75% at 50% 38%, black 20%, transparent 100%)",
        }}
      />

      <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-14 sm:pb-24 sm:pt-16 md:pb-28 md:pt-20">
        <div className="flex items-center justify-between gap-4">
          <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-forest/60">
            Explainable AI
          </span>
          <span className="rounded-full bg-forest px-3.5 py-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-leaf">
            Evidence attached
          </span>
        </div>

        <motion.div
          initial={prefersReduced ? false : { opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="mx-auto mt-10 max-w-3xl text-center sm:mt-12"
        >
          <h2 className="text-balance text-[clamp(30px,5.6vw,64px)] font-medium leading-[1.02] tracking-[-0.04em] text-forest">
            Every answer comes with its{" "}
            <em className="font-accent font-normal">reasoning.</em>
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-[16px] leading-[1.55] text-ink-muted">
            Confidence, the region the model looked at, and the advisory behind the
            recommendation — attached to the result, not hidden behind it.
          </p>
        </motion.div>

        <motion.div
          ref={frameRef}
          style={
            prefersReduced
              ? { opacity: 1 }
              : {
                  y: frameY,
                  scale: frameScale,
                  rotateX: frameRotate,
                  opacity: frameOpacity,
                  transformPerspective: 2000,
                }
          }
          className="mx-auto mt-10 max-w-6xl origin-bottom will-change-transform sm:mt-14"
        >
          <div className="rounded-[34px_34px_82px_34px] bg-[#0B120E] p-2 shadow-[0_55px_110px_-42px_rgba(6,36,27,0.5)] ring-1 ring-forest/30 sm:rounded-[42px_42px_110px_42px] sm:p-2.5">
            <div className="overflow-hidden rounded-[27px_27px_70px_27px] bg-[#0D1511]">
              {/* window chrome */}
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <div className="flex items-center gap-1.5" aria-hidden="true">
                  <span className="size-1.5 rounded-full bg-white/20" />
                  <span className="size-1.5 rounded-full bg-white/20" />
                  <span className="size-1.5 rounded-full bg-white/20" />
                </div>
                <span className="hidden font-mono text-[9px] uppercase tracking-[0.12em] text-white/30 sm:block">
                  zenvy / field-report / 0123
                </span>
                <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.1em] text-[#9BE07A]">
                  <span aria-hidden="true" className="size-1.5 rounded-full bg-[#9BE07A]" />
                  sample
                </span>
              </div>

              <div className="grid min-h-[560px] gap-7 p-4 sm:min-h-[620px] sm:p-6 md:min-h-[700px] md:grid-cols-[0.92fr_1.08fr] md:gap-8 md:p-8">
                {/* left — visual evidence */}
                <div className="flex h-full min-h-[500px] flex-col rounded-[24px_10px_24px_10px] border border-white/10 bg-[#0A100C] p-5 sm:rounded-[30px_12px_30px_12px] sm:p-6">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-white/35">
                      Visual evidence
                    </span>
                    <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-white/25">
                      grad-cam
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <figure>
                      <div className="relative grid aspect-square place-items-center rounded-lg bg-[#101C15] ring-1 ring-inset ring-white/[0.06]">
                        <LeafCanvas tone="dark" className="w-[78%]" />
                        <span className="absolute left-2 top-2 font-mono text-[8px] uppercase tracking-[0.1em] text-white/30">
                          original
                        </span>
                      </div>
                    </figure>
                    <figure>
                      <div className="relative grid aspect-square place-items-center overflow-hidden rounded-lg bg-[#101C15] ring-1 ring-inset ring-[#9BE07A]/25">
                        <motion.div
                          className="w-[78%]"
                          initial={prefersReduced ? false : { opacity: 0 }}
                          animate={run ? { opacity: 1 } : undefined}
                          transition={{ duration: 0.9, delay: 0.5 }}
                        >
                          <LeafCanvas tone="dark" withHeat />
                        </motion.div>
                        <motion.span
                          aria-hidden="true"
                          className="absolute inset-x-2 h-px bg-[#9BE07A]/70"
                          initial={prefersReduced ? false : { top: "10%", opacity: 0 }}
                          animate={
                            run ? { top: ["10%", "88%"], opacity: [0, 1, 0] } : undefined
                          }
                          transition={{ duration: 1.4, delay: 0.35, ease: "easeInOut" }}
                        />
                        <span className="absolute left-2 top-2 font-mono text-[8px] uppercase tracking-[0.1em] text-[#9BE07A]/70">
                          overlay
                        </span>
                      </div>
                    </figure>
                  </div>

                  <div className="mt-3 flex items-center gap-1.5">
                    {["#4477EE", "#55BB88", "#F2E23A", "#F2B53A", "#D9453B"].map((colour) => (
                      <span
                        key={colour}
                        aria-hidden="true"
                        className="h-1.5 flex-1 rounded-sm"
                        style={{ backgroundColor: colour }}
                      />
                    ))}
                  </div>
                  <div className="mt-1.5 flex justify-between font-mono text-[8px] uppercase tracking-[0.1em] text-white/25">
                    <span>low attention</span>
                    <span>high</span>
                  </div>
                  <p className="mt-auto pt-4 text-[11px] leading-[1.5] text-white/40">
                    Warm regions mark the pixels that most influenced the class score — the
                    lesion edge here, not the healthy leaf.
                  </p>
                </div>

                {/* right — answer and reasoning */}
                <div className="flex min-h-[500px] flex-col justify-center gap-6 py-2 sm:min-h-[560px]">
                  <div>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-white/35">
                          Diagnosis
                        </span>
                        <p className="mt-1 text-2xl font-semibold tracking-[-0.02em] text-[#F1F6EE]">
                          Early blight
                        </p>
                        <p className="mt-0.5 text-xs text-white/40">
                          Alternaria solani · tomato
                        </p>
                      </div>
                      <span className="shrink-0 rounded-full bg-[#F2B53A]/12 px-2.5 py-1 text-[10px] font-medium text-[#F2B53A]">
                        Moderate
                      </span>
                    </div>

                    <div className="mt-3 flex items-center gap-3">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
                        <div
                          className="h-full rounded-full bg-[#9BE07A] transition-[width] duration-[900ms] ease-out"
                          style={{ width: inView || prefersReduced ? "86%" : 0 }}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-white/55">0.86</span>
                    </div>
                  </div>

                  <div className="border-t border-white/10 pt-3.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-white/35">
                        Why this answer
                      </span>
                      <span className="font-mono text-[8px] uppercase tracking-[0.1em] text-white/25">
                        attention share
                      </span>
                    </div>
                    <div className="mt-3 flex flex-col gap-2.5">
                      {evidence.map((row, i) => (
                        <div key={row.label} className="flex items-center gap-3">
                          <span className="w-[6.5rem] shrink-0 text-[11px] text-white/50">
                            {row.label}
                          </span>
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.07]">
                            <div
                              className="h-full rounded-full bg-[#9BE07A]/80 transition-[width] duration-[900ms] ease-out"
                              style={{
                                width: inView || prefersReduced ? `${row.value * 100}%` : 0,
                                transitionDelay: `${300 + i * 90}ms`,
                              }}
                            />
                          </div>
                          <span className="w-8 shrink-0 text-right font-mono text-[10px] text-white/35">
                            {row.value.toFixed(2)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-[10px_22px_10px_22px] border border-white/10 bg-white/[0.03] p-3">
                    <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-white/35">
                      Recommended action
                    </span>
                    <p className="mt-1.5 text-[12px] leading-[1.55] text-white/65">
                      Remove affected lower leaves and improve airflow. Apply a labelled
                      fungicide only if spread continues past the next week.
                    </p>
                    <p className="mt-2 font-mono text-[8px] uppercase tracking-[0.1em] text-white/25">
                      Source · cited crop advisory
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/10 px-4 py-2.5 font-mono text-[8px] uppercase tracking-[0.1em] text-white/25">
                <span>model v0.1.0 · temperature-scaled</span>
                <span>confidence gate 0.60</span>
                <span className="text-[#9BE07A]/60">sample output</span>
              </div>
            </div>
          </div>
        </motion.div>

        <p className="mt-5 text-center font-mono text-[10px] uppercase tracking-[0.12em] text-[#4E6355]">
          Sample field report · crops and conditions differ
        </p>
      </div>
    </FullBleed>
  );
}

/* ── Landing page ────────────────────────────────────────────────────────── */

export default function Home() {
  return (
    <div className="flex flex-col gap-24 md:gap-32">
      {/* 1 — Hero */}
      <section className="grid items-center gap-14 lg:grid-cols-[minmax(0,1fr)_minmax(0,0.95fr)] lg:gap-16">
        <div className="flex flex-col">
          <div className="flex items-center gap-3">
            <span aria-hidden="true" className="h-px w-8 bg-forest/35" />
            <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-forest/60">
              Crop diagnostics · yield forecasting
            </p>
          </div>

          <h1 className="mt-6 text-[clamp(34px,7.4vw,68px)] font-semibold leading-[0.94] tracking-[-0.045em] text-forest">
            Diagnose the leaf.
            <br />
            Forecast the harvest.
          </h1>

          <p className="mt-6 max-w-[44ch] text-[17px] leading-[1.55] text-ink-muted sm:text-[18px]">
            One leaf photo returns a calibrated diagnosis, a severity grade and the Grad-CAM
            evidence behind it. Add your district and Zenvy turns weather and soil into a
            yield number with the drivers that moved it.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <ButtonLink href="/dashboard" size="lg">
              Scan a leaf
            </ButtonLink>
            <ButtonLink href="/dashboard" variant="ghost" size="lg">
              Forecast yield
            </ButtonLink>
          </div>

          {/* honest numbers: they come from the shipped models, not marketing */}
          <div className="mt-10 flex flex-wrap items-baseline gap-x-7 gap-y-3 border-t border-hairline pt-5">
            {[
              { value: "38", label: "disease classes" },
              { value: "36", label: "Punjab districts" },
              { value: "2", label: "crops covered" },
            ].map((fact) => (
              <div key={fact.label} className="flex items-baseline gap-2">
                <span className="text-xl font-semibold tracking-[-0.02em] text-forest">
                  {fact.value}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                  {fact.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        <HeroReport />
      </section>

      {/* 1.5 — Capability tape marquee */}
      <TapeMarquee />

      {/* 2 — Two tools */}
      <FadeUp>
        <h2 className="sr-only">Two tools</h2>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="group relative overflow-hidden rounded-[20px] bg-forest p-8 text-leaf transition-transform duration-300 hover:-translate-y-1 md:p-12">
            <LeafOrnament className="absolute -right-8 -top-8 size-36 rotate-12 text-leaf/10 transition-transform duration-500 group-hover:scale-110" />
            <div className="flex items-end justify-between gap-4">
              <div className="flex flex-col gap-4">
                <Label className="text-leaf/70">Disease detection</Label>
                <h3 className="text-[32px] font-medium leading-[1.02] tracking-[-1px] md:text-[40px]">
                  One leaf photo, one <em className="font-accent font-normal">answer.</em>
                </h3>
                <ul className="flex flex-col gap-1.5 text-sm leading-[1.5] text-leaf/90">
                  <li>A confidence score and a severity level, every time.</li>
                  <li>Grad-CAM shows where the model looked.</li>
                  <li>Recommended actions come from a trusted agricultural source.</li>
                </ul>
                <Link
                  href="/dashboard"
                  className="group/link inline-flex items-center gap-1.5 pt-2 text-sm font-medium text-leaf underline-offset-4 hover:underline"
                >
                  Scan a leaf
                  <span aria-hidden="true" className="transition-transform group-hover/link:translate-x-0.5">→</span>
                </Link>
              </div>
              <Image
                src="/mascot1.png"
                alt=""
                width={1254}
                height={1254}
                aria-hidden="true"
                className="hidden w-36 shrink-0 self-end md:block lg:w-44"
              />
            </div>
          </div>

          <div className="group relative overflow-hidden rounded-[20px] bg-leaf p-8 text-forest transition-transform duration-300 hover:-translate-y-1 md:p-12">
            <LeafOrnament className="absolute -left-8 -bottom-8 size-36 -rotate-45 text-forest/10 transition-transform duration-500 group-hover:scale-110" />
            <div className="flex items-end justify-between gap-4">
              <div className="flex flex-col gap-4">
                <Label>Yield prediction</Label>
                <h3 className="text-[32px] font-medium leading-[1.02] tracking-[-1px] md:text-[40px]">
                  Your season in <em className="font-accent font-normal">numbers.</em>
                </h3>
                <ul className="flex flex-col gap-1.5 text-sm leading-[1.5] text-forest/90">
                  <li>Enter your crop, location and farm details.</li>
                  <li>Weather and soil data are pulled in for you.</li>
                  <li>Get a predicted yield and a risk level, with SHAP showing the main factors.</li>
                </ul>
                <Link
                  href="/dashboard"
                  className="group/link inline-flex items-center gap-1.5 pt-2 text-sm font-medium text-forest underline-offset-4 hover:underline"
                >
                  Forecast yield
                  <span aria-hidden="true" className="transition-transform group-hover/link:translate-x-0.5">→</span>
                </Link>
              </div>
              <Image
                src="/mascot2.png"
                alt=""
                width={483}
                height={507}
                aria-hidden="true"
                className="hidden w-32 shrink-0 self-end md:block lg:w-40"
              />
            </div>
          </div>
        </div>
      </FadeUp>

      {/* 3 — How it works (auto-advancing highlight) */}
      <FadeUp>
        <HowItWorks />
      </FadeUp>

      {/* 3.5 — Scrolling model coverage */}
      <FieldSignals />

      {/* 4 — Explainable AI: a black field report on a dotted board */}
      <ReasoningSection />

      {/* 4.5 — Product showcase */}
      <FadeUp>
        <ProductShowcase />
      </FadeUp>

      {/* 5 — Final CTA */}
      <FadeUp>
        <section className="relative overflow-hidden rounded-[20px] bg-forest px-6 py-16 text-center md:py-24">
          <LeafOrnament className="absolute -left-10 -top-10 size-48 -rotate-45 text-leaf/10" />
          <LeafOrnament className="absolute -right-10 -bottom-10 size-64 rotate-12 text-leaf/10" />
          <div className="relative">
            <h2 className="text-[36px] font-medium leading-[0.95] tracking-[-1px] text-leaf md:text-[64px] md:tracking-[-3px]">
              Healthier crops,{" "}
              <em className="font-accent font-normal">clearer harvests.</em>
            </h2>
            <div className="mt-8 flex justify-center">
              <ButtonLink
                href="/dashboard"
                size="lg"
                variant="secondary"
                className="bg-leaf text-forest hover:bg-surface hover:text-forest"
              >
                Try it
              </ButtonLink>
            </div>
            <nav
              aria-label="Footer"
              className="mt-10 flex justify-center gap-6 font-mono text-[11px] uppercase tracking-[0.08em] text-leaf/60"
            >
              <Link href="/about" className="transition-colors hover:text-leaf">
                About the models
              </Link>
              <Link href="/dashboard" className="transition-colors hover:text-leaf">
                Forecast yield
              </Link>
              <Link href="/dashboard" className="transition-colors hover:text-leaf">
                Dashboard
              </Link>
            </nav>
            <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.08em] text-leaf/40">
              Decision support only · confirm with a local agronomist
            </p>
          </div>
          <Image
            src="/mascot6.png"
            alt=""
            width={389}
            height={431}
            aria-hidden="true"
            className="absolute bottom-0 left-4 hidden w-20 opacity-90 md:block lg:w-28"
          />
          <Image
            src="/mascot3.png"
            alt=""
            width={428}
            height={502}
            aria-hidden="true"
            className="absolute bottom-0 right-4 hidden w-20 opacity-90 md:block lg:w-28"
          />
        </section>
      </FadeUp>
    </div>
  );
}
