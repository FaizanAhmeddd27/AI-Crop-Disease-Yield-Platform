"use client";

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState, type FormEvent } from "react";
import { z } from "zod";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { ThemedLoader } from "@/components/ui/ThemedLoader";
import { ApiError, api, type WeatherResponse, type YieldOptionsResponse, type YieldPredictResponse } from "@/lib/api-client";
import { cn } from "@/lib/utils";

const fieldClass =
  "min-h-12 w-full rounded-2xl border border-hairline bg-page px-4 text-sm text-ink outline-none transition focus:border-forest focus:ring-2 focus:ring-forest/10";

const yieldFormSchema = z.object({
  crop: z.string().min(1),
  district: z.string().min(1),
  year: z.coerce.number().int().min(1900).max(2200),
  area: z.coerce.number().positive(),
  latitude: z.coerce.number().min(-90).max(90),
  longitude: z.coerce.number().min(-180).max(180),
});

function formatNumber(value: number, digits = 1) {
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits }).format(value);
}

function riskTone(level: YieldPredictResponse["risk"]["level"]) {
  if (level === "high") return "bg-risk-high/15 text-risk-high";
  if (level === "medium") return "bg-risk-medium/15 text-risk-medium";
  return "bg-risk-low/15 text-risk-low";
}

function formatFeature(feature: string) {
  return feature.replace(/_/g, " ");
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

/**
 * Honest notes for non-`ok` model statuses, shown next to the estimate.
 */
function statusNote(status: YieldPredictResponse["status"]) {
  if (status === "degraded") {
    return "Some weather inputs were missing, so the model filled the gaps with defaults. Treat this estimate as indicative.";
  }
  if (status === "out_of_bounds") {
    return "This location sits outside the model's training region. Treat this estimate as indicative.";
  }
  return null;
}

export function YieldContent() {
  const auth = useAuth();
  const soilId = useId();
  const weatherId = useId();
  const weatherPanelId = useId();
  const resultRef = useRef<HTMLElement>(null);
  const prefersReduced = useReducedMotion();

  const [options, setOptions] = useState<YieldOptionsResponse | null>(null);
  const [crop, setCrop] = useState("");
  const [district, setDistrict] = useState("");
  const [year, setYear] = useState("");
  const [area, setArea] = useState("1");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [ph, setPh] = useState("");
  const [organicCarbon, setOrganicCarbon] = useState("");
  const [texture, setTexture] = useState("");
  const [result, setResult] = useState<YieldPredictResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoadingOptions, setIsLoadingOptions] = useState(true);
  const [weather, setWeather] = useState<WeatherResponse | null>(null);
  const [isLoadingWeather, setIsLoadingWeather] = useState(false);
  const [weatherOverride, setWeatherOverride] = useState({ temp: "", rain: "", heat: "", water: "" });
  const [isPredicting, setIsPredicting] = useState(false);
  const [soilOpen, setSoilOpen] = useState(false);
  const [weatherOpen, setWeatherOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.yieldOptions()
      .then((response) => {
        if (cancelled) return;
        setOptions(response);
        setCrop(response.supported_crops[0] ?? "");
        setDistrict(response.districts[0]?.name ?? "");
        setYear(String(response.default_year));
        setLatitude(String(response.districts[0]?.lat ?? ""));
        setLongitude(String(response.districts[0]?.lon ?? ""));
      })
      .catch(() => {
        if (!cancelled) setErrorMessage("Yield options could not be loaded. Check that the backend is running.");
      })
      .finally(() => {
        if (!cancelled) setIsLoadingOptions(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedDistrict = useMemo(
    () => options?.districts.find((item) => item.name === district) ?? options?.districts.find((item) => item.supported_crops.includes(crop)),
    [crop, district, options],
  );
  const availableDistricts = useMemo(
    () => options?.districts.filter((item) => item.supported_crops.includes(crop)) ?? [],
    [crop, options],
  );

  const activeDistrict = availableDistricts.some((item) => item.name === district)
    ? district
    : availableDistricts[0]?.name ?? "";

  if (isLoadingOptions && !options) {
    return (
      <ThemedLoader
        label="Loading supported crops and districts"
        className="min-h-[32rem]"
        size="lg"
      />
    );
  }

  const fetchWeather = async () => {
    if (!latitude || !longitude || !year || !crop) return;
    setIsLoadingWeather(true);
    setErrorMessage("");
    try {
      const response = await api.weather({
        lat: Number(latitude),
        lon: Number(longitude),
        start_date: `${year}-01-01`,
        end_date: `${year}-12-31`,
        crop,
      });
      setWeather(response);
      setWeatherOverride({
        temp: String(response.mean_temp_c),
        rain: String(response.total_rain_mm),
        heat: String(response.heat_stress_days),
        water: String(response.water_balance_mm),
      });
      setWeatherOpen(true);
    } catch (error: unknown) {
      setErrorMessage(error instanceof ApiError ? error.message : "The weather preview could not be loaded.");
    } finally {
      setIsLoadingWeather(false);
    }
  };

  const predict = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = yieldFormSchema.safeParse({
      crop,
      district: selectedDistrict?.name ?? "",
      year,
      area,
      latitude,
      longitude,
    });
    if (!parsed.success || !selectedDistrict) {
      setErrorMessage("Choose a crop, district, season year, and cultivated area.");
      return;
    }
    setIsPredicting(true);
    setErrorMessage("");
    try {
      const soil = ph || organicCarbon || texture
        ? {
            ...(ph ? { ph: Number(ph) } : {}),
            ...(organicCarbon ? { organic_carbon: Number(organicCarbon) } : {}),
            ...(texture ? { texture } : {}),
          }
        : undefined;
      const response = await api.predictYield({
        crop,
        location: {
          lat: Number(latitude),
          lon: Number(longitude),
          district: selectedDistrict.name,
          region: selectedDistrict.zone,
        },
        season: { year: Number(year) },
        area_ha: Number(area),
        weather_override: weatherOverride.temp || weatherOverride.rain || weatherOverride.heat || weatherOverride.water
          ? {
              ...(weatherOverride.temp ? { w_temp_mean_c: Number(weatherOverride.temp) } : {}),
              ...(weatherOverride.rain ? { w_rain_total_mm: Number(weatherOverride.rain) } : {}),
              ...(weatherOverride.heat ? { w_heat_stress_days: Number(weatherOverride.heat) } : {}),
              ...(weatherOverride.water ? { w_water_balance_mm: Number(weatherOverride.water) } : {}),
            }
          : undefined,
        ...(soil ? { soil } : {}),
      }, auth.token ?? undefined);
      setResult(response);
      window.requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({
          behavior: prefersReduced ? "auto" : "smooth",
          block: "start",
        });
      });
    } catch (error: unknown) {
      setErrorMessage(error instanceof ApiError ? error.message : "The yield prediction failed. Please try again.");
    } finally {
      setIsPredicting(false);
    }
  };

  const maxContribution = Math.max(
    0.1,
    ...(result?.explanation.contributions.map((item) => Math.abs(item.shap)) ?? []),
  );

  const enter = prefersReduced ? false : { opacity: 0, y: 12 };
  const enterTransition = { duration: 0.45, ease: "easeOut" } as const;

  // Interval band geometry — lower/estimate/baseline mapped onto one honest scale.
  const band = (() => {
    if (!result) return null;
    const { lower, upper } = result.prediction.interval;
    const baseline = result.risk.baseline_yield;
    const estimate = result.prediction.yield_value;
    const lo = Math.min(lower, baseline, estimate);
    const hi = Math.max(upper, baseline, estimate);
    const span = Math.max(hi - lo, 0.0001);
    const pad = span * 0.14;
    const min = lo - pad;
    const max = hi + pad;
    const pct = (value: number) => ((value - min) / (max - min)) * 100;
    return {
      bandLeft: pct(lower),
      bandWidth: Math.max(pct(upper) - pct(lower), 2),
      estimatePct: pct(estimate),
      baselinePct: pct(baseline),
      unit: result.prediction.unit,
    };
  })();

  const note = result ? statusNote(result.status) : null;

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
            Yield outlook
          </div>
          <Link href="/dashboard" className="text-sm text-ink-muted underline-offset-4 hover:text-forest hover:underline">
            Back to dashboard
          </Link>
        </div>
        <h1 className="max-w-[14ch] text-4xl font-medium leading-[0.96] tracking-[-0.045em] text-forest sm:text-6xl">
          Plan the season with a number you can inspect.
        </h1>
        <p className="max-w-2xl text-base leading-[1.6] text-ink-muted sm:pr-36">
          Describe the field, let the backend pull live weather for the district, then read
          the estimate, its range, and the factors that moved it.
        </p>
        <Image
          src="/mascot3.png"
          alt=""
          aria-hidden="true"
          width={180}
          height={180}
          loading="eager"
          style={{ height: "auto" }}
          className="pointer-events-none absolute right-0 top-4 hidden w-24 object-contain sm:block md:w-28 lg:w-36"
        />
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-[0.14em] text-ink-muted">
          <span><span className="text-forest/50">01</span> Describe the field</span>
          <span aria-hidden="true" className="text-forest/30">·</span>
          <span><span className="text-forest/50">02</span> Run the forecast</span>
          <span aria-hidden="true" className="text-forest/30">·</span>
          <span><span className="text-forest/50">03</span> Inspect the factors</span>
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

      {/* ── FORECAST INPUTS ── */}
      <motion.section
        initial={enter}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.08 }}
        className="rounded-[28px] border border-hairline bg-surface p-4 shadow-[0_20px_50px_rgba(6,71,52,0.08)] sm:p-7"
      >
        <form onSubmit={predict}>
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-hairline pb-5">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Forecast inputs</p>
              <h2 className="mt-2 text-2xl font-medium tracking-[-0.03em] text-ink">Describe this field</h2>
            </div>
            <span className="rounded-full bg-leaf px-3 py-1.5 font-mono text-[10px] uppercase text-forest">Live model</span>
          </div>

          <fieldset disabled={isLoadingOptions || isPredicting} className="mt-6 grid gap-5">
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="text-sm font-medium text-ink">
                Crop
                <select value={crop} onChange={(event) => setCrop(event.target.value)} className={`${fieldClass} mt-2`}>
                  {options?.supported_crops.map((item) => <option key={item} value={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}
                </select>
              </label>
              <label className="text-sm font-medium text-ink">
                District
                <select value={activeDistrict} onChange={(event) => {
                  const next = options?.districts.find((item) => item.name === event.target.value);
                  setDistrict(event.target.value);
                  if (next) {
                    setLatitude(String(next.lat));
                    setLongitude(String(next.lon));
                  }
                }} className={`${fieldClass} mt-2`}>
                  {availableDistricts.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
                </select>
              </label>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="text-sm font-medium text-ink">
                Season year
                <input type="number" min="2000" max="2050" value={year} onChange={(event) => setYear(event.target.value)} className={`${fieldClass} mt-2`} />
              </label>
              <label className="text-sm font-medium text-ink">
                Cultivated area (ha)
                <input type="number" min="0.01" step="0.01" value={area} onChange={(event) => setArea(event.target.value)} className={`${fieldClass} mt-2`} />
              </label>
            </div>

            {/* Location + weather fetch */}
            <div className="rounded-2xl border border-hairline bg-page px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-ink">Field location</p>
                  <p className="mt-1 text-xs text-ink-muted">
                    District coordinates are loaded from the backend. You can refine them.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void fetchWeather()}
                  disabled={isLoadingWeather || !latitude || !longitude}
                  className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-forest/20 px-3 text-xs font-medium text-forest transition-colors hover:bg-leaf disabled:pointer-events-none disabled:opacity-50"
                >
                  {isLoadingWeather ? (
                    <>
                      <Spinner className="h-4 w-4" />
                      Fetching weather…
                    </>
                  ) : "Refresh weather"}
                </button>
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="text-xs text-ink-muted">Latitude<input type="number" min="-90" max="90" step="0.0001" value={latitude} onChange={(event) => setLatitude(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
                <label className="text-xs text-ink-muted">Longitude<input type="number" min="-180" max="180" step="0.0001" value={longitude} onChange={(event) => setLongitude(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
              </div>
            </div>

            {/* Weather preview — collapsible, editable */}
            <AnimatePresence initial={false}>
              {weather && (
                <motion.div
                  key="weather"
                  id={weatherId}
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: "auto", opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.28, ease: "easeOut" }}
                  className="overflow-hidden"
                >
                  <div className="rounded-2xl border border-forest/15 bg-leaf/60 px-4 py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-forest">Weather preview</p>
                        <p className="mt-1 text-xs text-forest/65">
                          {weather.provider} · {weather.start_date} to {weather.end_date} · {weather.daily_records_count} daily records
                        </p>
                      </div>
                      <span className="rounded-full bg-surface px-2.5 py-1 font-mono text-[10px] uppercase text-forest">Editable</span>
                    </div>
                    <button
                      type="button"
                      aria-expanded={weatherOpen}
                      aria-controls={weatherPanelId}
                      onClick={() => setWeatherOpen((open) => !open)}
                      className="mt-3 flex w-full items-center justify-between gap-3 text-left text-xs font-medium text-forest/80"
                    >
                      Adjust the four inputs sent to the model
                      <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        className={cn("h-4 w-4 transition-transform duration-300", weatherOpen && "rotate-180")}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    </button>
                    <AnimatePresence initial={false}>
                      {weatherOpen && (
                        <motion.div
                          id={weatherPanelId}
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.26, ease: "easeOut" }}
                          className="overflow-hidden"
                        >
                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            <label className="text-xs text-forest/70">Mean temp °C<input type="number" step="0.1" value={weatherOverride.temp} onChange={(event) => setWeatherOverride((current) => ({ ...current, temp: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                            <label className="text-xs text-forest/70">Rain total mm<input type="number" step="0.1" value={weatherOverride.rain} onChange={(event) => setWeatherOverride((current) => ({ ...current, rain: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                            <label className="text-xs text-forest/70">Heat-stress days<input type="number" min="0" step="1" value={weatherOverride.heat} onChange={(event) => setWeatherOverride((current) => ({ ...current, heat: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                            <label className="text-xs text-forest/70">Water balance mm<input type="number" step="0.1" value={weatherOverride.water} onChange={(event) => setWeatherOverride((current) => ({ ...current, water: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Soil readings — collapsed by default */}
            <div className="rounded-2xl border border-hairline bg-page px-4 py-1">
              <button
                type="button"
                aria-expanded={soilOpen}
                aria-controls={soilId}
                onClick={() => setSoilOpen((open) => !open)}
                className="flex w-full items-center justify-between gap-3 py-3 text-left"
              >
                <span className="text-sm font-medium text-ink">
                  Soil readings <span className="font-normal text-ink-muted">(optional)</span>
                </span>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  className={cn("h-4 w-4 text-ink-muted transition-transform duration-300", soilOpen && "rotate-180")}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                </svg>
              </button>
              <AnimatePresence initial={false}>
                {soilOpen && (
                  <motion.div
                    key="soil"
                    id={soilId}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.28, ease: "easeOut" }}
                    className="overflow-hidden"
                  >
                    <div className="grid gap-4 pb-4 sm:grid-cols-3">
                      <label className="text-xs text-ink-muted">pH<input type="number" min="3" max="11" step="0.1" value={ph} onChange={(event) => setPh(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
                      <label className="text-xs text-ink-muted">Organic carbon<input type="number" min="0" max="10" step="0.1" value={organicCarbon} onChange={(event) => setOrganicCarbon(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
                      <label className="text-xs text-ink-muted">Texture<input value={texture} onChange={(event) => setTexture(event.target.value)} placeholder="e.g. loam" className={`${fieldClass} mt-1.5`} /></label>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </fieldset>

          <button type="submit" disabled={isLoadingOptions || isPredicting} className={buttonClass("primary", "lg", "mt-6 flex w-full items-center justify-center gap-2 rounded-full")}>
            {isPredicting ? (
              <>
                <Spinner className="h-4 w-4" />
                Calculating with the yield model…
              </>
            ) : isLoadingOptions ? "Loading supported locations…" : "Predict yield"}
          </button>
          <p className="mt-3 text-center text-xs text-ink-muted">Weather is fetched by the backend for the selected district.</p>
        </form>
      </motion.section>

      {/* ── RESULT ── */}
      {result ? (
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
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-forest/55">
                  Expected yield · {crop[0]?.toUpperCase() + crop.slice(1)} · {activeDistrict}
                </p>
                <p className="mt-3 text-5xl font-medium tracking-[-0.06em] text-forest sm:text-7xl">
                  {formatNumber(result.prediction.yield_value)}{" "}
                  <span className="text-xl tracking-normal text-ink-muted sm:text-2xl">{result.prediction.unit}</span>
                </p>
                <p className="mt-3 max-w-xl text-sm leading-[1.55] text-ink-muted">
                  80% model interval: {formatNumber(result.prediction.interval.lower)} to{" "}
                  {formatNumber(result.prediction.interval.upper)} {result.prediction.unit}
                </p>
              </div>
              <span className={cn("rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em]", riskTone(result.risk.level))}>
                {result.risk.level} risk
              </span>
            </div>

            {note && (
              <p className="relative z-10 mt-5 rounded-xl border border-risk-medium/30 bg-risk-medium/10 px-4 py-3 text-xs leading-[1.55] text-ink">
                <strong className="font-medium">Model note:</strong> {note}
              </p>
            )}

            <div className="relative z-10 mt-6 grid gap-3 border-t border-hairline pt-5 sm:grid-cols-3">
              <div>
                <p className="text-xs text-ink-muted">District baseline</p>
                <p className="mt-1 text-lg font-medium text-ink">{formatNumber(result.risk.baseline_yield)} {result.prediction.unit}</p>
              </div>
              <div>
                <p className="text-xs text-ink-muted">Compared with baseline</p>
                <p className={cn("mt-1 text-lg font-medium", result.risk.ratio_to_baseline >= 0 ? "text-risk-low" : "text-risk-high")}>
                  {result.risk.ratio_to_baseline >= 0 ? "+" : ""}{formatNumber(result.risk.ratio_to_baseline * 100, 0)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-ink-muted">Model response</p>
                <p className="mt-1 text-lg font-medium text-ink">{Math.round(result.latency_ms)} ms</p>
              </div>
            </div>
            <p className="relative z-10 mt-4 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
              {result.model.name} {result.model.version}
            </p>
          </motion.div>

          {/* Interval band — where the estimate sits against the baseline */}
          {band && (
            <motion.div
              initial={enter}
              animate={{ opacity: 1, y: 0 }}
              transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.08 }}
              className="rounded-[26px] border border-hairline bg-surface p-6"
            >
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Range</p>
                  <h2 className="mt-2 text-xl font-medium tracking-[-0.03em] text-ink sm:text-2xl">Where this estimate sits</h2>
                </div>
                <span className="text-xs text-ink-muted">P10–P90 model interval</span>
              </div>

              <div className="relative mt-8 h-16">
                {/* track */}
                <div className="absolute inset-x-0 top-7 h-2 overflow-hidden rounded-full bg-page">
                  <motion.div
                    className="absolute h-full rounded-full bg-leaf"
                    initial={prefersReduced ? false : { width: 0 }}
                    animate={{ width: `${band.bandWidth}%` }}
                    transition={{ duration: 0.7, ease: "easeOut", delay: 0.15 }}
                    style={{ left: `${band.bandLeft}%` }}
                  />
                </div>

                {/* baseline marker */}
                <div className="absolute top-0 h-16" style={{ left: `${band.baselinePct}%` }}>
                  <div className="h-7 w-px border-l-2 border-dashed border-ink-muted/70" />
                  <p className="mt-1 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] uppercase tracking-[0.08em] text-ink-muted">
                    Baseline {formatNumber(result.risk.baseline_yield)}
                  </p>
                </div>

                {/* estimate marker */}
                <div className="absolute top-0 h-16" style={{ left: `${band.estimatePct}%` }}>
                  <div className="mx-auto h-7 w-0.5 bg-forest" />
                  <div className="mx-auto mt-0.5 h-3 w-3 rounded-full bg-forest ring-4 ring-leaf" />
                  <p className="mt-1 -translate-x-1/2 whitespace-nowrap font-mono text-[9px] uppercase tracking-[0.08em] text-forest">
                    {formatNumber(result.prediction.yield_value)}
                  </p>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 border-t border-hairline pt-4 text-xs text-ink-muted">
                <span className="flex items-center gap-2"><span aria-hidden="true" className="h-2 w-6 rounded-full bg-leaf" /> 80% interval</span>
                <span className="flex items-center gap-2"><span aria-hidden="true" className="h-3 w-0.5 bg-forest" /> This forecast</span>
                <span className="flex items-center gap-2"><span aria-hidden="true" className="h-3 w-px border-l-2 border-dashed border-ink-muted/70" /> District baseline</span>
              </div>
              <p className="mt-3 text-xs leading-[1.55] text-ink-muted">
                Most model runs for this field land inside the band. The baseline is what the
                district historically returns for this crop.
              </p>
            </motion.div>
          )}

          {/* Weather + risk readout */}
          <motion.div
            initial={enter}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.12 }}
            className="grid gap-5 lg:grid-cols-2"
          >
            <div className="rounded-[26px] bg-forest p-6 text-leaf sm:p-7">
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-leaf/55">Weather the model received</p>
              <div className="mt-5 grid grid-cols-2 gap-y-5">
                <div>
                  <p className="text-xs text-leaf/60">Mean temperature</p>
                  <p className="mt-1 text-3xl font-medium tracking-[-0.03em]">{formatNumber(result.weather_summary.temp_mean)}°</p>
                </div>
                <div>
                  <p className="text-xs text-leaf/60">Rain total</p>
                  <p className="mt-1 text-3xl font-medium tracking-[-0.03em]">{formatNumber(result.weather_summary.rain_total)} <span className="text-base font-normal text-leaf/70">mm</span></p>
                </div>
                <div>
                  <p className="text-xs text-leaf/60">Heat-stress days</p>
                  <p className="mt-1 text-3xl font-medium tracking-[-0.03em]">{result.weather_summary.heat_stress_days}</p>
                </div>
                <div>
                  <p className="text-xs text-leaf/60">Water balance</p>
                  <p className="mt-1 text-3xl font-medium tracking-[-0.03em]">{formatNumber(result.weather_summary.water_balance)} <span className="text-base font-normal text-leaf/70">mm</span></p>
                </div>
              </div>
              <p className="mt-5 border-t border-leaf/15 pt-3 font-mono text-[10px] uppercase tracking-[0.08em] text-leaf/50">
                Source · {result.weather_summary.source}
              </p>
            </div>

            <div className="flex flex-col rounded-[26px] border border-hairline bg-leaf p-6 text-forest sm:p-7">
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Risk readout</p>
              <p className="mt-3 text-base leading-[1.55] sm:text-lg">{result.risk.rationale}</p>
              {result.risk.advisories.length > 0 && (
                <div className="mt-auto border-t border-forest/15 pt-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-forest/60">Advisories</p>
                  <ul className="mt-2 list-disc space-y-1.5 pl-4 text-sm leading-[1.55]">
                    {result.risk.advisories.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>

          {/* SHAP factors */}
          <motion.div
            initial={enter}
            animate={{ opacity: 1, y: 0 }}
            transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.16 }}
            className="rounded-[26px] border border-hairline bg-surface p-6 sm:p-7"
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Why the model moved</p>
                <h2 className="mt-2 text-xl font-medium tracking-[-0.03em] text-ink sm:text-2xl">Yield factors</h2>
              </div>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-muted">
                {result.explanation.method} · {result.model.version}
              </span>
            </div>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              {result.explanation.contributions.map((item, index) => (
                <div key={item.feature} className="rounded-2xl bg-page p-4">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="min-w-0 truncate font-medium capitalize text-ink">{formatFeature(item.feature)}</span>
                    <span className={cn(
                      "shrink-0 font-mono text-[11px]",
                      item.direction === "increase" ? "text-risk-low" : item.direction === "decrease" ? "text-risk-high" : "text-ink-muted",
                    )}>
                      {item.direction === "increase" ? "+" : item.direction === "decrease" ? "−" : ""}
                      {formatNumber(Math.abs(item.shap), 2)}
                    </span>
                  </div>
                  <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-surface">
                    <motion.div
                      className={cn(
                        "h-full rounded-full",
                        item.direction === "increase" ? "bg-risk-low" : item.direction === "decrease" ? "bg-risk-high" : "bg-forest/40",
                      )}
                      initial={prefersReduced ? false : { width: 0 }}
                      animate={{ width: `${Math.max(8, (Math.abs(item.shap) / maxContribution) * 100)}%` }}
                      transition={{ duration: 0.6, ease: "easeOut", delay: 0.15 + index * 0.06 }}
                    />
                  </div>
                  <p className="mt-2 text-xs leading-[1.5] text-ink-muted">{item.text}</p>
                </div>
              ))}
            </div>
            <p className="mt-5 border-t border-hairline pt-4 text-xs leading-[1.55] text-ink-muted">
              Each bar shows how far one input pushed the estimate away from the model&apos;s base
              value. Green raised it, red pulled it down.
            </p>
          </motion.div>
        </section>
      ) : (
        /* ── EMPTY STATE ── */
        <motion.div
          initial={enter}
          animate={{ opacity: 1, y: 0 }}
          transition={{ ...enterTransition, delay: prefersReduced ? 0 : 0.12 }}
          className="flex min-h-[320px] flex-col justify-between gap-6 rounded-[28px] border border-dashed border-hairline bg-leaf/35 p-7 sm:flex-row sm:items-end sm:p-9"
        >
          <div className="max-w-md">
            <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Your forecast will appear here</p>
            <h2 className="mt-3 text-3xl font-medium leading-[1.05] tracking-[-0.04em] text-forest">
              One clear estimate. The reasoning beside it.
            </h2>
            <p className="mt-3 text-sm leading-[1.6] text-ink-muted">
              Run a forecast to see the interval, the weather the model received, the baseline
              comparison, and the inputs that pushed the result up or down.
            </p>
            <Link href="/dashboard" className="mt-5 inline-block text-sm font-medium text-forest underline-offset-4 hover:underline">
              Back to dashboard
            </Link>
          </div>
          <Image
            src="/mascot6.png"
            alt=""
            aria-hidden="true"
            width={200}
            height={200}
            loading="eager"
            style={{ height: "auto" }}
            className="w-40 self-end object-contain sm:w-48"
          />
        </motion.div>
      )}
    </div>
  );
}
