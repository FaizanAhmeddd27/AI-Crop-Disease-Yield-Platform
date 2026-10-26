"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { ThemedLoader } from "@/components/ui/ThemedLoader";
import { ApiError, api, type DiseaseClassItem, type DiseasePredictResponse } from "@/lib/api-client";
import { env } from "@/lib/env";

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

function severityClass(level: DiseasePredictResponse["severity"]["level"]) {
  if (level === "severe") return "bg-risk-high/15 text-risk-high";
  if (level === "moderate") return "bg-risk-medium/15 text-risk-medium";
  if (level === "low") return "bg-risk-low/15 text-risk-low";
  return "bg-ink/10 text-ink-muted";
}

export function DiseaseContent() {
  const auth = useAuth();
  const inputId = useId();
  const cameraId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [result, setResult] = useState<DiseasePredictResponse | null>(null);
  const [classes, setClasses] = useState<DiseaseClassItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [classSearch, setClassSearch] = useState("");
  const [evidenceView, setEvidenceView] = useState<"original" | "gradcam">("original");

  useEffect(() => {
    let cancelled = false;
    api.diseaseClasses().then((response) => {
      if (!cancelled) setClasses(response.classes);
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
    setEvidenceView("original");

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
    if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    if (inputRef.current) inputRef.current.value = "";
  };

  const analyze = async () => {
    if (!file) {
      setErrorMessage("Choose a leaf photo before running the analysis.");
      return;
    }
    setIsAnalyzing(true);
    setErrorMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await api.predictDisease(form, auth.token ?? undefined);
      setResult(response);
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

  return (
    <div className="flex flex-col gap-8 pb-16">
      <header className="relative flex flex-col gap-3">
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
          alt="CropSense mascot showing a leaf analysis heatmap"
          width={150}
          height={150}
          className="pointer-events-none absolute right-0 top-7 hidden w-28 object-contain sm:block lg:w-36"
        />
        <ol className="mt-4 grid max-w-3xl gap-2 sm:grid-cols-3">
          {[
            ["01", "Add a photo", "One leaf, clear light"],
            ["02", "Run analysis", "Production model"],
            ["03", "Review evidence", "Diagnosis and guidance"],
          ].map(([number, title, copy]) => (
            <li key={number} className="flex items-center gap-3 rounded-2xl border border-hairline bg-surface px-3 py-2.5">
              <span className="font-mono text-[10px] text-forest/50">{number}</span>
              <span className="min-w-0">
                <strong className="block text-xs font-medium text-ink">{title}</strong>
                <span className="block text-[11px] text-ink-muted">{copy}</span>
              </span>
            </li>
          ))}
        </ol>
      </header>

      {errorMessage && (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-2xl border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage("")} className="shrink-0 font-mono text-[10px] uppercase underline">
            Dismiss
          </button>
        </div>
      )}

      <section className="grid gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(320px,0.92fr)]">
        <div className="rounded-[28px] border border-hairline bg-surface p-4 shadow-[0_20px_50px_rgba(6,71,52,0.08)] sm:p-6">
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
            className={`relative flex min-h-[430px] flex-col items-center justify-center overflow-hidden rounded-[26px] border border-dashed p-6 text-center transition-colors sm:min-h-[500px] ${
              isDragging ? "border-forest bg-page" : "border-hairline bg-page/45"
            }`}
          >
            {previewUrl ? (
              <>
                <div className="relative flex min-h-[290px] w-full flex-1 items-center justify-center">
                  <Image src={previewUrl} alt="Selected leaf preview" fill unoptimized className="object-contain p-3" />
                </div>
                <div className="mt-5 flex w-full flex-wrap items-center justify-between gap-3 border-t border-hairline pt-4 text-left">
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
              </>
            ) : (
              <>
                <Image
                  src="/mascot1.png"
                  alt="CropSense mascot inspecting a leaf"
                  width={170}
                  height={170}
                  className="pointer-events-none absolute bottom-0 right-1 w-32 object-contain opacity-90 sm:right-5 sm:w-40"
                />
                <span className="mb-6 grid size-16 place-items-center rounded-full bg-leaf text-forest">
                  <svg aria-hidden="true" viewBox="0 0 24 24" className="size-8" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 16V4m0 0L8 8m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3" />
                  </svg>
                </span>
                <div className="relative z-10">
                <h2 className="text-xl font-medium text-ink">Drop a leaf photo here</h2>
                <p className="mt-2 max-w-sm text-sm leading-[1.55] text-ink-muted">
                  Keep one leaf in frame, use even light, and avoid shadows or fingers over the spots.
                </p>
                <div className="mt-7 flex flex-wrap justify-center gap-3">
                  <label htmlFor={inputId} className={buttonClass("primary", "md", "cursor-pointer rounded-full")}>
                    Choose photo
                  </label>
                  <label htmlFor={cameraId} className={buttonClass("secondary", "md", "cursor-pointer rounded-full")}>
                    Use camera
                  </label>
                </div>
                <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                  JPEG · PNG · WEBP · MAX 10 MB
                </p>
                </div>
              </>
            )}
            <input ref={inputRef} id={inputId} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(event) => void selectFile(event.target.files?.[0])} />
            <input id={cameraId} type="file" accept="image/*" capture="environment" className="sr-only" onChange={(event) => void selectFile(event.target.files?.[0])} />
          </div>
          <button type="button" onClick={() => void analyze()} disabled={!file || isAnalyzing} className={buttonClass("primary", "lg", "mt-4 flex w-full items-center justify-center gap-2 rounded-full")}>
            {isAnalyzing ? (
              <>
                <ThemedLoader label="" size="sm" className="h-6 w-6" />
                Running the disease model…
              </>
            ) : "Analyze leaf"}
          </button>
        </div>

        <aside className="flex flex-col gap-4">
          <div className="rounded-[28px] bg-forest p-6 text-leaf sm:p-7">
            <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-leaf/55">How this result is built</p>
            <div className="mt-6 flex flex-col gap-5">
              {[
                ["01", "Classification", "EfficientNet-B0 compares the image against 38 supported crop and disease classes."],
                ["02", "Visual evidence", "Grad-CAM highlights regions that influenced the class score. It is attention, not proof."],
                ["03", "Severity estimate", "A colour-based lesion ratio maps affected leaf area into coarse severity bands."],
              ].map(([number, title, copy]) => (
                <div key={number} className="flex gap-4 border-t border-leaf/15 pt-4">
                  <span className="font-mono text-[10px] text-leaf/45">{number}</span>
                  <div>
                    <h2 className="font-medium">{title}</h2>
                    <p className="mt-1 text-sm leading-[1.5] text-leaf/65">{copy}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-[24px] border border-hairline bg-surface p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Supported library</p>
                <p className="mt-1 text-lg font-medium text-ink">{classes.length || 38} classes</p>
              </div>
              <span className="rounded-full bg-risk-low/15 px-2.5 py-1 font-mono text-[10px] uppercase text-risk-low">Live API</span>
            </div>
            <input value={classSearch} onChange={(event) => setClassSearch(event.target.value)} placeholder="Search crop or disease" className="mt-4 min-h-11 w-full rounded-xl border border-hairline bg-page px-3 text-sm text-ink outline-none focus:border-forest" />
            <div className="mt-3 flex max-h-36 flex-wrap content-start gap-1.5 overflow-y-auto">
              {filteredClasses.slice(0, 18).map((item) => (
                <span key={item.class_id} className="rounded-full bg-page px-2.5 py-1 text-[11px] text-ink-muted">{item.crop} · {item.disease_name}</span>
              ))}
            </div>
          </div>
        </aside>
      </section>

      {result && (
        <section aria-live="polite" className="flex flex-col gap-6 border-t border-hairline pt-8">
          <div className="relative overflow-hidden rounded-[30px] border border-hairline bg-surface p-6 shadow-[0_18px_45px_rgba(6,71,52,0.06)] sm:p-8">
            <div className="absolute inset-y-0 left-0 w-1.5 bg-leaf" aria-hidden="true" />
            <div className="relative z-10 flex flex-wrap items-start justify-between gap-6 pl-1 sm:pl-2">
              <div className="flex items-start gap-4">
                <span className="grid size-14 shrink-0 place-items-center rounded-2xl bg-leaf text-forest">
                  <span className="font-mono text-lg">
                    {isUncertain ? "?" : result.prediction.is_healthy ? "✓" : "!"}
                  </span>
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
              <span className={`rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] ${
                isUncertain
                  ? "bg-risk-medium/15 text-risk-medium"
                  : result.prediction.is_healthy
                    ? "bg-risk-low/15 text-risk-low"
                    : "bg-risk-high/15 text-risk-high"
              }`}>
                {isUncertain ? "Retake recommended" : result.prediction.is_healthy ? "Healthy leaf" : "Action recommended"}
              </span>
            </div>
            <p className="relative z-10 mt-6 border-t border-hairline pt-3 pl-1 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted sm:pl-2">
              {result.model.name} {result.model.version} · {Math.round(result.latency_ms)} ms
            </p>
          </div>

          <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[26px] border border-hairline bg-surface p-4 sm:p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <figure>
                  <figcaption className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-muted">Original</figcaption>
                  <div className="relative aspect-square overflow-hidden rounded-2xl bg-page">
                    {resultOriginal && <Image src={resultOriginal} alt="Original uploaded leaf" fill unoptimized className="object-contain" />}
                  </div>
                </figure>
                <figure>
                  <figcaption className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-forest">Model attention · Grad-CAM</figcaption>
                  <div className="relative aspect-square overflow-hidden rounded-2xl bg-page">
                    {resultOverlay ? <Image src={resultOverlay} alt="Grad-CAM heatmap overlay showing model attention" fill unoptimized className="object-contain" /> : <div className="grid h-full place-items-center p-5 text-center text-sm text-ink-muted">Heatmap unavailable for this result.</div>}
                  </div>
                </figure>
              </div>
              <div className="mt-4 flex rounded-full border border-hairline bg-page p-1" role="tablist" aria-label="Evidence viewer">
                <button type="button" role="tab" aria-selected={evidenceView === "original"} onClick={() => setEvidenceView("original")} className={`min-h-10 flex-1 rounded-full px-3 text-xs font-medium transition-colors ${evidenceView === "original" ? "bg-forest text-leaf" : "text-ink-muted hover:text-forest"}`}>View original</button>
                <button type="button" role="tab" aria-selected={evidenceView === "gradcam"} onClick={() => setEvidenceView("gradcam")} className={`min-h-10 flex-1 rounded-full px-3 text-xs font-medium transition-colors ${evidenceView === "gradcam" ? "bg-forest text-leaf" : "text-ink-muted hover:text-forest"}`}>View Grad-CAM</button>
              </div>
              <div className="relative mt-3 aspect-[2/1] overflow-hidden rounded-2xl bg-page">
                {evidenceView === "original" && resultOriginal ? <Image src={resultOriginal} alt="Original uploaded leaf in the evidence viewer" fill unoptimized className="object-contain" /> : resultOverlay ? <Image src={resultOverlay} alt="Grad-CAM heatmap in the evidence viewer" fill unoptimized className="object-contain" /> : <div className="grid h-full place-items-center p-5 text-center text-sm text-ink-muted">Grad-CAM is unavailable for this result.</div>}
              </div>
              <p className="mt-4 text-xs leading-[1.55] text-ink-muted">
                Highlighted regions show where the model focused when making its prediction. They do not prove the disease location.
              </p>
            </div>

            <div className="flex flex-col gap-4">
              <div className="rounded-[26px] bg-forest p-6 text-leaf">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-leaf/55">How sure is the model?</p>
                    <p className="mt-2 text-4xl font-medium">{percent(result.prediction.confidence)}</p>
                  </div>
                  <div title={result.severity.note} aria-label={`Estimated severity: ${result.severity.level}. ${result.severity.note}`} className={`cursor-help rounded-full px-3 py-1.5 text-xs font-medium capitalize ${severityClass(result.prediction.is_healthy ? "low" : result.severity.level)}`}>
                    {result.prediction.is_healthy ? "No visible severity" : `${result.severity.level} · estimated`}
                  </div>
                </div>
                <div className="mt-6 h-2 overflow-hidden rounded-full bg-leaf/15">
                  <div className="h-full rounded-full bg-leaf transition-[width] duration-700" style={{ width: `${result.prediction.confidence * 100}%` }} />
                </div>
                <p className="mt-3 text-xs text-leaf/60">
                  {result.prediction.is_healthy ? "The model found no supported disease pattern." : `Estimated affected leaf area: ${result.severity.ratio.toFixed(1)}% · ${result.severity.method.replace(/_/g, " ")}`}
                </p>
              </div>

              <div className="rounded-[26px] border border-hairline bg-surface p-6">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="font-medium text-ink">Other likely classes</h3>
                  <span className="font-mono text-[10px] uppercase text-ink-muted">Top 5</span>
                </div>
                <div className="mt-4 flex flex-col gap-3">
                  {result.prediction.top_k.slice(0, 3).map((item) => (
                    <div key={item.class_id} className="flex items-center gap-3">
                      <span className="min-w-0 flex-1 truncate text-sm text-ink">{formatClass(item.class_id)}</span>
                      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-brand-100">
                        <div className="h-full rounded-full bg-forest/70" style={{ width: `${item.confidence * 100}%` }} />
                      </div>
                      <span className="w-10 text-right font-mono text-[10px] text-ink-muted">{percent(item.confidence)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {result.explanation.quality_warnings?.map((warning) => (
            <div key={warning} className="rounded-2xl border border-risk-medium/30 bg-risk-medium/10 px-4 py-3 text-sm text-ink">
              <strong className="font-medium">Photo quality note:</strong> {warning.replace(/^low_saliency_quality:\s*/, "")}
            </div>
          ))}

          <div className="grid items-start gap-5 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[26px] border border-hairline bg-surface p-6">
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Curated guidance</p>
              <h3 className="mt-2 text-2xl font-medium text-ink">{result.recommendations.summary}</h3>
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
                  <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-ink-muted">
                    {result.recommendations.prevention.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
            </div>
            <div className="self-start rounded-[26px] bg-leaf p-6 text-forest">
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Read before acting</p>
              <p className="mt-3 text-sm leading-[1.6]">{result.recommendations.disclaimer}</p>
              {result.recommendations.sources.length > 0 && (
                <div className="mt-6 border-t border-forest/15 pt-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-forest/60">Sources</p>
                  <div className="mt-2 flex flex-col gap-2">
                    {result.recommendations.sources.map((source) => (
                      <a key={source.url} href={source.url} target="_blank" rel="noreferrer" className="text-sm underline-offset-4 hover:underline">
                        {source.title} ↗
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
