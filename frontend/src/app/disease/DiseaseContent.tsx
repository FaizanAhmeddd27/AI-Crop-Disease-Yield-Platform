"use client";

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { ApiError, api, type DiseaseClassItem, type DiseasePredictResponse } from "@/lib/api-client";
import { env } from "@/lib/env";
import { cn } from "@/lib/utils";

const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_LONG_SIDE = 1280;

function mediaUrl(path: string | undefined, fallback = "") {
  if (!path) return fallback;
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("blob:")) {
    return path;
  }
  return `${env.apiBaseUrl}${path}`;
}

async function prepareImage(file: File): Promise<File> {
  if (file.size <= 2 * 1024 * 1024) return file;

  const bitmap = await createImageBitmap(file);
  const scale = Math.min(1, MAX_LONG_SIDE / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * scale));
  canvas.height = Math.max(1, Math.round(bitmap.height * scale));
  canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.88),
  );
  if (!blob) throw new Error("The image could not be prepared. Please try another photo.");
  return new File([blob], file.name.replace(/\.[^.]+$/, ".jpg"), { type: "image/jpeg" });
}

function formatClass(classId: string) {
  return classId.replace(/___/g, " · ").replace(/_/g, " ");
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function severityDot(level: DiseasePredictResponse["severity"]["level"]) {
  if (level === "severe") return "bg-risk-high";
  if (level === "moderate") return "bg-risk-medium";
  if (level === "unknown") return "bg-ink-muted";
  return "bg-risk-low";
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("motion-safe:animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        className="opacity-75"
      />
    </svg>
  );
}

export function DiseaseContent() {
  const auth = useAuth();
  const inputId = useId();
  const libraryId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const resultRef = useRef<HTMLElement>(null);
  const prefersReduced = useReducedMotion();

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [result, setResult] = useState<DiseasePredictResponse | null>(null);
  const [classes, setClasses] = useState<DiseaseClassItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [classSearch, setClassSearch] = useState("");
  const [classTotal, setClassTotal] = useState(0);
  const [libraryOpen, setLibraryOpen] = useState(false);
  const [zoom, setZoom] = useState<"original" | "gradcam" | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.diseaseClasses().then((response) => {
      if (!cancelled) {
        setClasses(response.classes);
        setClassTotal(response.total_classes);
      }
    }).catch(() => {
      // The upload flow remains usable if the optional taxonomy panel is unavailable.
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  // Zoom lightbox: Esc closes, background stays still while it is open.
  useEffect(() => {
    if (!zoom) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setZoom(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [zoom]);

  const filteredClasses = useMemo(() => {
    const query = classSearch.trim().toLowerCase();
    if (!query) return classes;
    return classes.filter((item) =>
      `${item.crop} ${item.disease_name}`.toLowerCase().includes(query),
    );
  }, [classSearch, classes]);

  const selectFile = useCallback(async (nextFile: File | undefined) => {
    if (!nextFile) return;
    setErrorMessage("");
    setResult(null);
    setZoom(null);

    if (!ACCEPTED_TYPES.includes(nextFile.type)) {
      setErrorMessage("Use a JPEG, PNG, or WebP image.");
      return;
    }
    if (nextFile.size > MAX_FILE_BYTES) {
      setErrorMessage("That image is larger than 10 MB. Choose a smaller file.");
      return;
    }

    try {
      const prepared = await prepareImage(nextFile);
      setFile(prepared);
      setPreviewUrl(URL.createObjectURL(prepared));
    } catch (error: unknown) {
      setErrorMessage(error instanceof Error ? error.message : "The image could not be prepared.");
    }
  }, []);

  const clearSelection = () => {
    setFile(null);
    setResult(null);
    setErrorMessage("");
    setZoom(null);
    if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const analyze = async () => {
    if (!file || isAnalyzing) {
      if (!file) setErrorMessage("Choose a leaf photo before running the analysis.");
      return;
    }
    setIsAnalyzing(true);
    setErrorMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api.predictDisease(form, auth.token ?? undefined);
      setResult(response);
      window.requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({
          behavior: prefersReduced ? "auto" : "smooth",
          block: "start",
        });
      });
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setErrorMessage(
          error.code === "TIMEOUT"
            ? "The model took too long to respond. Try again with a clearer, smaller photo."
            : error.message,
        );
      } else {
        setErrorMessage("The analysis failed. Please try again with a clear leaf photo.");
      }
    } finally {
      setIsAnalyzing(false);
    }
  };

  const resultOriginal = mediaUrl(result?.explanation.original_url, previewUrl);
  const resultOverlay = mediaUrl(result?.explanation.overlay_url);
  const isUncertain = result?.status === "uncertain" || result?.status === "not_a_leaf";

  const enter = prefersReduced ? false : { opacity: 0, y: 12 };
  const enterTransition = { duration: 0.45, ease: "easeOut" } as const;

  return (
    <div className="flex flex-col gap-8 pb-16">
      {/* ── HEADER ── */}
      <motion.header
        initial={enter}
        animate={{ opacity: 1, y: 0 }}
        transition={enterTransition}
        className="relative flex flex-col gap-3"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] text-forest/60">
            <span className="h-px w-8 bg-forest/40" />
            Disease detection
          </div>
          <Link href="/dashboard" className="text-sm text-ink-muted underline-offset-4 hover:text-forest hover:underline">
            Back to dashboard
          </Link>
        </div>
        <h1 className="max-w-[13ch] text-4xl font-medium leading-[0.96] tracking-[-0.045em] text-forest sm:text-6xl">
          See what the leaf is telling you.
        </h1>
        <p className="max-w-2xl text-base leading-[1.6] text-ink-muted sm:pr-36">
          Upload one clear leaf photo. The production classifier returns a diagnosis,
          confidence, estimated severity, visual evidence, and sourced next steps.
        </p>
        <Image
          src="/mascot5.png"
          alt=""
          aria-hidden="true"
          width={150}
          height={150}
          loading="eager"
          style={{ height: "auto" }}
          className="pointer-events-none absolute right-0 top-4 hidden w-24 object-contain sm:block md:w-28 lg:w-36"
        />
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
          <span><span className="text-forest/50">01</span> Add a photo</span>
          <span aria-hidden="true" className="text-forest/30">·</span>
          <span><span className="text-forest/50">02</span> Run analysis</span>
          <span aria-hidden="true" className="text-forest/30">·</span>
          <span><span className="text-forest/50">03</span> Review evidence</span>
        </p>
      </motion.header>

      {errorMessage && (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-2xl border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage("")} className="shrink-0 font-mono text-[10px] uppercase underline">
            Dismiss
          </button>
        </div>
      )}

      {/* ── UPLOAD + SUPPORTED LIBRARY (one card) ── */}
      <motion.section
        initial={enter}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.08 }}
        className="rounded-[28px] border border-hairline bg-surface p-4 shadow-[0_20px_50px_rgba(6,71,52,0.08)] sm:p-6"
      >
        <div className="mx-auto flex max-w-2xl flex-col">
          <div
            onDragOver={(event) => {
              event.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setIsDragging(false);
              void selectFile(event.dataTransfer.files[0]);
            }}
            className={cn(
              "relative flex min-h-[360px] flex-col items-center justify-center overflow-hidden rounded-[22px] border border-dashed p-6 text-center transition-colors sm:min-h-[420px]",
              isDragging ? "border-forest bg-page" : "border-hairline bg-page/45",
            )}
          >
            {previewUrl ? (
              <div className="flex w-full flex-col">
                <div className="relative min-h-[240px] flex-1 sm:min-h-[300px]">
                  <Image src={previewUrl} alt="Selected leaf preview" fill unoptimized className="object-contain p-2" />
                </div>
                {isAnalyzing && (
                  <div className="absolute inset-0 z-10 grid place-items-center rounded-[22px] bg-surface/75 backdrop-blur-[2px]">
                    <div className="flex flex-col items-center gap-3">
                      <Spinner className="h-7 w-7 text-forest" />
                      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-forest">
                        Running the disease model…
                      </p>
                    </div>
                  </div>
                )}
                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4 text-left">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-ink">{file?.name}</p>
                    <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-muted">
                      {file ? `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to analyze` : ""}
                    </p>
                  </div>
                  <button type="button" onClick={clearSelection} className="text-xs font-medium text-ink-muted underline-offset-4 hover:text-risk-high hover:underline">
                    Replace photo
                  </button>
                </div>
              </div>
            ) : (
              <>
                <Image
                  src="/mascot1.png"
                  alt=""
                  aria-hidden="true"
                  width={170}
                  height={170}
                  loading="eager"
                  style={{ height: "auto" }}
                  className="pointer-events-none absolute bottom-1 right-1 hidden w-20 object-contain opacity-90 min-[420px]:block sm:right-4 sm:w-36"
                />
                <span className="mb-5 grid size-14 place-items-center rounded-full bg-leaf text-forest">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="size-7" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 16V4m0 0L8 8m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" />
                  </svg>
                </span>
                <div className="relative z-10">
                  <h2 className="text-lg font-medium text-ink sm:text-xl">Drop a leaf photo here</h2>
                  <p className="mt-2 max-w-sm text-sm leading-[1.55] text-ink-muted">
                    Keep one leaf in frame, use even light, and avoid shadows or fingers over the spots.
                  </p>
                  <div className="mt-6 flex flex-wrap justify-center gap-3">
                    <label htmlFor={inputId} className={buttonClass("primary", "md", "cursor-pointer rounded-full")}>
                      Choose photo
                    </label>
                  </div>
                  <p className="mt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                    JPEG · PNG · WEBP · MAX 10 MB
                  </p>
                </div>
              </>
            )}
            <input
              ref={inputRef}
              id={inputId}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              onChange={(event) => void selectFile(event.target.files?.[0])}
            />
          </div>

          <button
            type="button"
            onClick={() => void analyze()}
            disabled={!file || isAnalyzing}
            className={buttonClass("primary", "lg", "mt-4 flex w-full items-center justify-center gap-2 rounded-full")}
          >
            {isAnalyzing ? (
              <>
                <Spinner className="h-4 w-4" />
                Running the disease model…
              </>
            ) : "Analyze leaf"}
          </button>
        </div>

        {/* Supported library — collapsed by default */}
        <div className="mx-auto mt-5 max-w-2xl border-t border-hairline pt-1">
          <button
            type="button"
            aria-expanded={libraryOpen}
            aria-controls={libraryId}
            onClick={() => setLibraryOpen((open) => !open)}
            className="flex w-full items-center justify-between gap-3 py-3 text-left"
          >
            <span className="flex items-center gap-2.5">
              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-risk-low" />
              <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/70">
                Supported library{classTotal > 0 ? ` · ${classTotal} classes` : ""}
              </span>
            </span>
            <span className="flex items-center gap-3">
              <span className="rounded-full bg-risk-low/15 px-2.5 py-1 font-mono text-[10px] uppercase text-risk-low">
                Live API
              </span>
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                className={cn("h-4 w-4 text-ink-muted transition-transform duration-300", libraryOpen && "rotate-180")}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
              </svg>
            </span>
          </button>
          <AnimatePresence initial={false}>
            {libraryOpen && (
              <motion.div
                key="library"
                id={libraryId}
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.28, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="pb-4">
                  <input
                    value={classSearch}
                    onChange={(event) => setClassSearch(event.target.value)}
                    placeholder="Search crop or disease"
                    aria-label="Search crop or disease"
                    className="min-h-11 w-full rounded-xl border border-hairline bg-page px-3 text-sm text-ink outline-none focus:border-forest"
                  />
                  <div className="mt-3 flex max-h-32 flex-wrap content-start gap-1.5 overflow-y-auto">
                    {filteredClasses.slice(0, 18).map((item) => (
                      <span key={item.class_id} className="rounded-full bg-page px-2.5 py-1 text-[11px] text-ink-muted">
                        {item.crop} · {item.disease_name}
                      </span>
                    ))}
                    {classes.length > 0 && filteredClasses.length === 0 && (
                      <p className="text-xs text-ink-muted">No matching classes.</p>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </motion.section>

      {/* ── RESULT ── */}
      {result && (
        <section ref={resultRef} aria-live="polite" className="flex scroll-mt-24 flex-col gap-5 border-t border-hairline pt-8">
          {/* Verdict */}
          <motion.div
            initial={enter}
            animate={{ opacity: 1, y: 0 }}
            transition={enterTransition}
            className="relative overflow-hidden rounded-[24px] border border-hairline bg-surface p-6 shadow-[0_18px_45px_rgba(6,71,52,0.06)] sm:p-8"
          >
            <div className="absolute inset-y-0 left-0 w-1.5 bg-leaf" aria-hidden="true" />
            <div className="relative z-10 flex flex-wrap items-start justify-between gap-5 pl-1 sm:pl-2">
              <div className="flex items-start gap-4">
                <span
                  className={cn(
                    "grid size-14 shrink-0 place-items-center rounded-2xl font-mono text-lg",
                    isUncertain
                      ? "bg-risk-medium/15 text-risk-medium"
                      : result.prediction.is_healthy
                        ? "bg-risk-low/15 text-risk-low"
                        : "bg-risk-high/15 text-risk-high",
                  )}
                >
                  {isUncertain ? "?" : result.prediction.is_healthy ? "✓" : "!"}
                </span>
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-forest/55">
                    What we found · {result.prediction.crop}
                  </p>
                  <h2 className="mt-2 text-3xl font-medium tracking-[-0.04em] text-forest sm:text-5xl">
                    {isUncertain ? "Photo needs a retake." : result.prediction.is_healthy ? "This leaf looks healthy." : `${result.prediction.disease} found.`}
                  </h2>
                  <p className="mt-3 max-w-xl text-sm leading-[1.55] text-ink-muted">
                    {isUncertain
                      ? "The model is not confident enough to give a reliable answer. Take a closer photo with one leaf filling the frame."
                      : result.prediction.is_healthy
                        ? "No supported disease pattern was detected in this photo. Keep monitoring the plant as it grows."
                        : "The model found a disease pattern. Review the highlighted evidence and the practical guidance below."}
                  </p>
                </div>
              </div>
              <span className={cn(
                "rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em]",
                isUncertain
                  ? "bg-risk-medium/15 text-risk-medium"
                  : result.prediction.is_healthy
                    ? "bg-risk-low/15 text-risk-low"
                    : "bg-risk-high/15 text-risk-high",
              )}>
                {isUncertain ? "Retake recommended" : result.prediction.is_healthy ? "Healthy leaf" : "Action recommended"}
              </span>
            </div>
            <p className="relative z-10 mt-6 border-t border-hairline pt-3 pl-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted sm:pl-2">
              {result.model.name} {result.model.version} · {Math.round(result.latency_ms)} ms
            </p>
          </motion.div>

          {/* Evidence + metrics */}
          <motion.div
            initial={enter}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.08 }}
            className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]"
          >
            {/* Evidence viewer */}
            <div className="rounded-[26px] border border-hairline bg-surface p-4 sm:p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <figure>
                  <figcaption className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">
                    Original photo
                  </figcaption>
                  <button
                    type="button"
                    onClick={() => setZoom("original")}
                    aria-label="Zoom the original photo"
                    className="group relative block aspect-square w-full overflow-hidden rounded-2xl bg-page"
                  >
                    {resultOriginal && (
                      <Image src={resultOriginal} alt="Original uploaded leaf" fill unoptimized className="object-contain transition-transform duration-300 group-hover:scale-[1.03]" />
                    )}
                    <span className="absolute inset-0 grid place-items-center bg-forest/0 opacity-0 transition-all duration-200 group-hover:bg-forest/25 group-hover:opacity-100 group-focus-visible:bg-forest/25 group-focus-visible:opacity-100">
                      <span className="grid size-10 place-items-center rounded-full bg-surface text-forest shadow-lg">
                        <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.34-4.34M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0ZM10 7v6m3-3H7" />
                        </svg>
                      </span>
                    </span>
                  </button>
                </figure>
                <figure>
                  <figcaption className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-forest">
                    Model attention · Grad-CAM
                  </figcaption>
                  {resultOverlay ? (
                    <button
                      type="button"
                      onClick={() => setZoom("gradcam")}
                      aria-label="Zoom the Grad-CAM heatmap"
                      className="group relative block aspect-square w-full overflow-hidden rounded-2xl bg-page"
                    >
                      <Image src={resultOverlay} alt="Grad-CAM heatmap overlay showing model attention" fill unoptimized className="object-contain transition-transform duration-300 group-hover:scale-[1.03]" />
                      <span className="absolute inset-0 grid place-items-center bg-forest/0 opacity-0 transition-all duration-200 group-hover:bg-forest/25 group-hover:opacity-100 group-focus-visible:bg-forest/25 group-focus-visible:opacity-100">
                        <span className="grid size-10 place-items-center rounded-full bg-surface text-forest shadow-lg">
                          <svg aria-hidden="true" viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="1.5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-4.34-4.34M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0ZM10 7v6m3-3H7" />
                          </svg>
                        </span>
                      </span>
                    </button>
                  ) : (
                    <div className="grid aspect-square w-full place-items-center rounded-2xl bg-page p-5 text-center text-sm text-ink-muted">
                      Heatmap unavailable for this result.
                    </div>
                  )}
                </figure>
              </div>
              <p className="mt-4 text-xs leading-[1.55] text-ink-muted">
                Highlighted regions show where the model focused when making its prediction.
                They do not prove the disease location. Select an image to zoom.
              </p>
            </div>

            {/* Confidence + likely classes */}
            <div className="flex flex-col gap-4">
              <div className="rounded-[26px] bg-forest p-6 text-leaf sm:p-7">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-leaf/55">Model confidence</p>
                    <p className="mt-2 text-5xl font-medium tracking-[-0.04em]">{percent(result.prediction.confidence)}</p>
                  </div>
                  <span
                    title={result.severity.note}
                    aria-label={`Estimated severity: ${result.severity.level}. ${result.severity.note}`}
                    className="inline-flex shrink-0 cursor-help items-center gap-2 rounded-full bg-black/20 px-3 py-1.5 text-xs font-medium text-leaf ring-1 ring-inset ring-leaf/25"
                  >
                    <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", severityDot(result.prediction.is_healthy ? "low" : result.severity.level))} />
                    {result.prediction.is_healthy ? "No visible severity" : `${result.severity.level} · estimated`}
                  </span>
                </div>
                <div className="mt-5 h-2 overflow-hidden rounded-full bg-leaf/15">
                  <motion.div
                    className="h-full rounded-full bg-leaf"
                    initial={prefersReduced ? false : { width: 0 }}
                    animate={{ width: `${result.prediction.confidence * 100}%` }}
                    transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 }}
                  />
                </div>
                <p className="mt-3 text-xs leading-relaxed text-leaf/65">
                  {result.prediction.is_healthy
                    ? "The model found no supported disease pattern."
                    : `Estimated affected leaf area: ${result.severity.ratio.toFixed(1)}% · ${result.severity.method.replace(/_/g, " ")}`}
                </p>
              </div>

              <div className="rounded-[26px] border border-hairline bg-surface p-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="text-sm font-medium text-ink">Other likely classes</h3>
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">Top 3</span>
                </div>
                <div className="mt-4 flex flex-col gap-3.5">
                  {result.prediction.top_k.slice(0, 3).map((item, index) => (
                    <div key={item.class_id} className="flex items-center gap-3">
                      <span className="min-w-0 flex-1 truncate text-sm text-ink">{formatClass(item.class_id)}</span>
                      <div className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-brand-100">
                        <motion.div
                          className="h-full rounded-full bg-forest"
                          initial={prefersReduced ? false : { width: 0 }}
                          animate={{ width: `${item.confidence * 100}%` }}
                          transition={{ duration: 0.6, ease: "easeOut", delay: 0.2 + index * 0.08 }}
                        />
                      </div>
                      <span className="w-9 shrink-0 text-right font-mono text-[10px] text-ink-muted">{percent(item.confidence)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>

          {/* Photo quality notes */}
          {result.explanation.quality_warnings?.map((warning) => (
            <div key={warning} className="flex items-start gap-2.5 rounded-2xl border border-risk-medium/30 bg-risk-medium/10 px-4 py-3 text-sm text-ink">
              <svg aria-hidden="true" viewBox="0 0 24 24" className="mt-0.5 h-4 w-4 shrink-0 text-risk-medium" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
              </svg>
              <p><strong className="font-medium">Photo quality note:</strong> {warning.replace(/^low_saliency_quality:\s*/, "")}</p>
            </div>
          ))}

          {/* Guidance */}
          <motion.div
            initial={enter}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.16 }}
            className="rounded-[26px] border border-hairline bg-surface p-6 sm:p-7"
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Curated guidance</p>
            <h3 className="mt-2 text-xl font-medium leading-snug text-ink sm:text-2xl">
              {result.recommendations.summary}
            </h3>

            {result.recommendations.actions.length > 0 && (
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                {result.recommendations.actions.map((action) => (
                  <div key={`${action.type}-${action.text}`} className="rounded-2xl bg-page p-4">
                    <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-forest">{action.type}</p>
                    <p className="mt-2 text-sm leading-[1.55] text-ink">{action.text}</p>
                  </div>
                ))}
              </div>
            )}

            {result.recommendations.prevention.length > 0 && (
              <div className="mt-5 border-t border-hairline pt-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">Prevention</p>
                <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm text-ink-muted">
                  {result.recommendations.prevention.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </div>
            )}

            <div className="mt-6 rounded-2xl bg-leaf p-5 text-forest">
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Read before acting</p>
              <p className="mt-2 text-sm leading-[1.6]">{result.recommendations.disclaimer}</p>
              {result.recommendations.sources.length > 0 && (
                <div className="mt-4 border-t border-forest/15 pt-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-forest/60">Sources</p>
                  <div className="mt-2 flex flex-col gap-1.5">
                    {result.recommendations.sources.map((source) => (
                      <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="w-fit text-sm underline underline-offset-4 hover:text-forest/70">
                        {source.title} ↗
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        </section>
      )}

      {/* ── EVIDENCE ZOOM ── */}
      <AnimatePresence>
        {zoom && result && (
          <motion.div
            key="evidence-zoom"
            role="dialog"
            aria-modal="true"
            aria-label="Evidence image zoom"
            className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-ink/85 p-4 backdrop-blur-sm"
            initial={prefersReduced ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
          >
            <button
              type="button"
              aria-label="Close image zoom"
              onClick={() => setZoom(null)}
              className="absolute inset-0 cursor-zoom-out"
            />
            <button
              type="button"
              aria-label="Close"
              onClick={() => setZoom(null)}
              className="absolute right-4 top-4 z-10 rounded-full border border-leaf/25 bg-black/30 p-2 text-leaf transition-colors hover:bg-black/50"
            >
              ✕
            </button>
            <motion.div
              className="relative z-10 flex w-full max-w-4xl flex-col items-center gap-3"
              initial={prefersReduced ? false : { scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={prefersReduced ? { opacity: 0 } : { scale: 0.97, opacity: 0 }}
              transition={{ duration: 0.22, ease: "easeOut" }}
            >
              <div className="flex rounded-full border border-leaf/25 bg-black/30 p-1" role="tablist" aria-label="Zoom image">
                <button
                  type="button"
                  role="tab"
                  aria-selected={zoom === "original"}
                  onClick={() => setZoom("original")}
                  className={cn(
                    "min-h-9 rounded-full px-4 font-mono text-[11px] uppercase tracking-[0.08em] transition-colors",
                    zoom === "original" ? "bg-leaf font-semibold text-forest" : "text-leaf/70 hover:text-leaf",
                  )}
                >
                  Original
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={zoom === "gradcam"}
                  onClick={() => setZoom("gradcam")}
                  disabled={!resultOverlay}
                  className={cn(
                    "min-h-9 rounded-full px-4 font-mono text-[11px] uppercase tracking-[0.08em] transition-colors",
                    zoom === "gradcam" ? "bg-leaf font-semibold text-forest" : "text-leaf/70 hover:text-leaf",
                    !resultOverlay && "cursor-not-allowed opacity-40",
                  )}
                >
                  Grad-CAM
                </button>
              </div>
              <div className="relative h-[62vh] w-full overflow-hidden rounded-2xl bg-page">
                <Image
                  src={zoom === "original" ? resultOriginal : resultOverlay}
                  alt={zoom === "original" ? "Zoomed original leaf photo" : "Zoomed Grad-CAM heatmap"}
                  fill
                  unoptimized
                  className="object-contain"
                />
              </div>
              <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-leaf/70">
                Press Esc or click outside to close
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
