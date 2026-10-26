"use client";

import Image from "next/image";
import { useEffect, useState } from "react";

import { ThemedLoader } from "@/components/ui/ThemedLoader";
import { ApiError, api, type ModelInfo, type ModelsResponse } from "@/lib/api-client";

function metricEntries(metrics: Record<string, unknown>) {
  return Object.entries(metrics).filter(([, value]) => ["string", "number", "boolean"].includes(typeof value));
}

export function AboutContent() {
  const [data, setData] = useState<ModelsResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    api.models()
      .then(setData)
      .catch((error: unknown) => {
        setErrorMessage(error instanceof ApiError ? error.message : "Model information could not be loaded.");
      })
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="flex flex-col gap-8 pb-16 sm:gap-10">
      <header className="relative isolate overflow-hidden rounded-[32px] bg-forest px-6 py-8 text-leaf shadow-[0_28px_65px_rgba(6,71,52,0.16)] sm:min-h-[360px] sm:px-10 sm:py-10">
        <div className="pointer-events-none absolute -right-24 -top-28 -z-10 h-80 w-80 rounded-full border border-leaf/10 bg-leaf/5" />
        <div className="pointer-events-none absolute -bottom-36 left-1/3 -z-10 h-80 w-80 rounded-full border border-leaf/10" />
        <Image
          src="/mascot6.png"
          alt="Zenvy mascot holding a model report"
          width={300}
          height={300}
          priority
          className="pointer-events-none absolute -bottom-8 right-1 hidden w-56 object-contain sm:block lg:right-12 lg:w-64"
        />
        <div className="relative z-10 max-w-2xl">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] text-leaf/60">
            <span className="h-1.5 w-1.5 rounded-full bg-leaf" />
            Model transparency · live registry
          </div>
          <h1 className="mt-5 max-w-[12ch] text-4xl font-medium leading-[0.92] tracking-[-0.05em] sm:text-6xl">Know what the models can see.</h1>
          <p className="mt-5 max-w-[48ch] text-base leading-[1.6] text-leaf/75">Versions and evaluation metrics come from the running backend registry. Explore the evidence, inputs, and boundaries around every output.</p>
          <div className="mt-7 flex flex-wrap gap-2 font-mono text-[10px] uppercase tracking-[0.1em] text-leaf/65">
            <span className="rounded-full border border-leaf/25 px-3 py-2">Grad-CAM evidence</span>
            <span className="rounded-full border border-leaf/25 px-3 py-2">SHAP factors</span>
          </div>
        </div>
      </header>

      {errorMessage && <div role="alert" className="rounded-2xl border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">{errorMessage}</div>}

      <section>
        <div className="flex flex-col gap-3 border-b border-hairline pb-5 sm:flex-row sm:items-end sm:justify-between">
          <div><p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Production registry</p><h2 className="mt-2 text-3xl font-medium tracking-tight text-ink">Active model cards</h2></div>
          <span className="w-fit rounded-full bg-leaf px-3 py-1.5 font-mono text-[10px] uppercase text-forest">{data?.registry ?? "Loading"}</span>
        </div>
        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          {data?.models.map((model) => <ModelCard key={`${model.pipeline}-${model.version}`} model={model} />)}
          {isLoading && <ThemedLoader label="Loading model registry" className="min-h-64 rounded-[26px] border border-dashed border-hairline bg-page p-6" size="sm" />}
          {data?.models.length === 0 && <div className="rounded-[26px] border border-dashed border-hairline bg-page p-6 text-sm text-ink-muted">No promoted models are currently registered.</div>}
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-2">
        <div className="rounded-[26px] border border-hairline bg-surface p-6 shadow-[0_14px_35px_rgba(6,71,52,0.04)]">
          <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">How outputs are explained</p>
          <dl className="mt-5 divide-y divide-hairline">
            <div className="py-4 first:pt-0"><dt className="font-medium text-ink">Disease evidence</dt><dd className="mt-1 text-sm leading-[1.55] text-ink-muted">Grad-CAM shows the image regions that influenced the class score. It is attention, not proof.</dd></div>
            <div className="py-4"><dt className="font-medium text-ink">Yield factors</dt><dd className="mt-1 text-sm leading-[1.55] text-ink-muted">SHAP contributions show which weather, soil, and location features moved the estimate.</dd></div>
            <div className="py-4 last:pb-0"><dt className="font-medium text-ink">Advice</dt><dd className="mt-1 text-sm leading-[1.55] text-ink-muted">Disease actions come from a curated knowledge base with source links, not generated treatment text.</dd></div>
          </dl>
        </div>
        <div className="relative overflow-hidden rounded-[26px] bg-[#0b5a43] p-6 text-leaf shadow-[0_18px_40px_rgba(6,71,52,0.1)]">
          <Image src="/mascot3.png" alt="" width={150} height={150} className="pointer-events-none absolute -bottom-4 right-3 hidden w-28 opacity-90 sm:block" aria-hidden="true" />
          <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-leaf/55">Limits to keep in mind</p>
          <ul className="mt-5 space-y-4 text-sm leading-[1.55] text-leaf/75">
            <li>Field photos can be harder than training images, so confidence can drop with poor light, blur, or multiple leaves.</li>
            <li>Severity is an estimate from visible lesion area, not a laboratory measurement.</li>
            <li>Only supported crops, districts, and disease classes are covered by the current models.</li>
            <li>Use the result as decision support and confirm serious crop problems with a qualified agronomist.</li>
          </ul>
        </div>
      </section>

      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-hairline pt-5 text-sm text-ink-muted">
        <span>Model cards are served live from <code className="font-mono text-xs text-forest">GET /api/v1/models</code>.</span>
        <div className="flex flex-wrap gap-4"><a href="#disease-model-card" className="underline-offset-4 hover:text-forest hover:underline">Disease model card</a><a href="#yield-model-card" className="underline-offset-4 hover:text-forest hover:underline">Yield model card</a><a href="https://plantvillage.psu.edu/" target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-forest hover:underline">PlantVillage ↗</a><a href="https://open-meteo.com/" target="_blank" rel="noreferrer" className="underline-offset-4 hover:text-forest hover:underline">Open-Meteo ↗</a></div>
      </footer>
    </div>
  );
}

function ModelCard({ model }: { model: ModelInfo }) {
  return (
    <article id={`${model.pipeline}-model-card`} className="group relative overflow-hidden rounded-[26px] border border-hairline bg-surface p-6 shadow-[0_14px_35px_rgba(6,71,52,0.05)] transition-transform duration-300 hover:-translate-y-1">
      <div className="absolute right-0 top-0 h-1 w-24 bg-leaf transition-all duration-300 group-hover:w-40" />
      <div className="flex items-start justify-between gap-4">
        <div><p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">{model.pipeline} model</p><h3 className="mt-2 text-2xl font-medium tracking-tight text-ink">{model.name}</h3></div>
        <span className="shrink-0 rounded-full bg-page px-3 py-1.5 font-mono text-[10px] text-forest">v{model.version}</span>
      </div>
      <div className="mt-6 grid gap-2 border-t border-hairline pt-4 sm:grid-cols-2">
        {metricEntries(model.metrics).map(([key, value]) => <div key={key} className="rounded-xl bg-page px-3 py-2"><p className="text-[11px] capitalize text-ink-muted">{key.replace(/_/g, " ")}</p><p className="mt-1 text-sm font-medium text-ink">{String(value)}</p></div>)}
      </div>
    </article>
  );
}
