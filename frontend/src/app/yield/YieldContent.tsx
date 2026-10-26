"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { z } from "zod";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { ThemedLoader } from "@/components/ui/ThemedLoader";
import { ApiError, api, type WeatherResponse, type YieldOptionsResponse, type YieldPredictResponse } from "@/lib/api-client";

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

export function YieldContent() {
  const auth = useAuth();
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

  return (
    <div className="flex flex-col gap-8 pb-16">
      <header className="relative overflow-hidden rounded-[30px] border border-hairline bg-surface px-6 py-7 shadow-[0_18px_45px_rgba(6,71,52,0.06)] sm:px-9 sm:py-9">
        <div className="relative z-10 max-w-2xl">
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.15em] text-forest/60">
            <span className="h-px w-8 bg-forest/40" />
            Yield outlook
          </div>
          <h1 className="mt-4 max-w-[13ch] text-4xl font-medium leading-[0.96] tracking-[-0.045em] text-forest sm:text-6xl">
            Plan the season with a number you can inspect.
          </h1>
          <p className="mt-4 max-w-xl text-base leading-[1.6] text-ink-muted">
            Select a supported crop and district. The backend combines live weather inputs with the yield model, then shows the range, risk, and factors behind the estimate.
          </p>
        </div>
        <Image
          src="/mascot3.png"
          alt="CropSense mascot holding a yield chart"
          width={220}
          height={220}
          className="absolute -bottom-3 right-2 hidden w-44 object-contain sm:block lg:right-10 lg:w-52"
        />
      </header>

      {errorMessage && (
        <div role="alert" className="flex items-start justify-between gap-4 rounded-2xl border border-risk-high/30 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage("")} className="shrink-0 font-mono text-[10px] uppercase underline">Dismiss</button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
        <form onSubmit={predict} className="rounded-[28px] border border-hairline bg-surface p-5 shadow-[0_18px_45px_rgba(6,71,52,0.05)] sm:p-7">
          <div className="flex items-start justify-between gap-4 border-b border-hairline pb-5">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Forecast inputs</p>
              <h2 className="mt-2 text-2xl font-medium text-ink">Describe this field</h2>
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
            <div className="rounded-2xl border border-hairline bg-page px-4 py-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-ink">Field location</p>
                  <p className="mt-1 text-xs text-ink-muted">District coordinates are loaded from the backend. You can refine them.</p>
                </div>
                <button type="button" onClick={() => void fetchWeather()} disabled={isLoadingWeather || !latitude || !longitude} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-full border border-forest/20 px-3 text-xs font-medium text-forest hover:bg-leaf">
                  {isLoadingWeather ? (
                    <>
                      <ThemedLoader label="" size="sm" className="h-6 w-6" />
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
            <details className="rounded-2xl border border-hairline bg-page px-4 py-3">
              <summary className="cursor-pointer text-sm font-medium text-ink">Add soil readings <span className="font-normal text-ink-muted">(optional)</span></summary>
              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <label className="text-xs text-ink-muted">pH<input type="number" min="3" max="11" step="0.1" value={ph} onChange={(event) => setPh(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
                <label className="text-xs text-ink-muted">Organic carbon<input type="number" min="0" max="10" step="0.1" value={organicCarbon} onChange={(event) => setOrganicCarbon(event.target.value)} className={`${fieldClass} mt-1.5`} /></label>
                <label className="text-xs text-ink-muted">Texture<input value={texture} onChange={(event) => setTexture(event.target.value)} placeholder="e.g. loam" className={`${fieldClass} mt-1.5`} /></label>
              </div>
            </details>
            {weather && (
              <div className="rounded-2xl border border-forest/15 bg-leaf/60 px-4 py-4">
                <div className="flex items-start justify-between gap-3">
                  <div><p className="text-sm font-medium text-forest">Weather preview</p><p className="mt-1 text-xs text-forest/65">{weather.provider} · {weather.start_date} to {weather.end_date}</p></div>
                  <span className="rounded-full bg-surface px-2.5 py-1 font-mono text-[10px] uppercase text-forest">Editable</span>
                </div>
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <label className="text-xs text-forest/70">Mean temp °C<input type="number" step="0.1" value={weatherOverride.temp} onChange={(event) => setWeatherOverride((current) => ({ ...current, temp: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                  <label className="text-xs text-forest/70">Rain total mm<input type="number" step="0.1" value={weatherOverride.rain} onChange={(event) => setWeatherOverride((current) => ({ ...current, rain: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                  <label className="text-xs text-forest/70">Heat-stress days<input type="number" min="0" step="1" value={weatherOverride.heat} onChange={(event) => setWeatherOverride((current) => ({ ...current, heat: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                  <label className="text-xs text-forest/70">Water balance mm<input type="number" step="0.1" value={weatherOverride.water} onChange={(event) => setWeatherOverride((current) => ({ ...current, water: event.target.value }))} className={`${fieldClass} mt-1.5`} /></label>
                </div>
              </div>
            )}
          </fieldset>
          <button type="submit" disabled={isLoadingOptions || isPredicting} className={buttonClass("primary", "lg", "mt-6 flex w-full items-center justify-center gap-2 rounded-full")}>
            {isPredicting ? (
              <>
                <ThemedLoader label="" size="sm" className="h-6 w-6" />
                Calculating with the yield model…
              </>
            ) : isLoadingOptions ? "Loading supported locations…" : "Predict yield"}
          </button>
          <p className="mt-3 text-center text-xs text-ink-muted">Weather is fetched by the backend for the selected district.</p>
        </form>

        {result ? (
          <section aria-live="polite" className="flex flex-col gap-5">
            <div className="rounded-[28px] border border-hairline bg-surface p-6 shadow-[0_18px_45px_rgba(6,71,52,0.05)] sm:p-7">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Expected yield · {crop} · {district}</p>
                  <p className="mt-3 text-5xl font-medium tracking-[-0.06em] text-forest sm:text-6xl">{formatNumber(result.prediction.yield_value)} <span className="text-xl tracking-normal text-ink-muted">{result.prediction.unit}</span></p>
                  <p className="mt-2 text-sm text-ink-muted">80% model interval: {formatNumber(result.prediction.interval.lower)} to {formatNumber(result.prediction.interval.upper)} {result.prediction.unit}</p>
                </div>
                <span className={`rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] ${riskTone(result.risk.level)}`}>{result.risk.level} risk</span>
              </div>
              <div className="mt-6 grid gap-3 border-t border-hairline pt-5 sm:grid-cols-3">
                <div><p className="text-xs text-ink-muted">Baseline</p><p className="mt-1 text-lg font-medium text-ink">{formatNumber(result.risk.baseline_yield)} {result.prediction.unit}</p></div>
                <div><p className="text-xs text-ink-muted">Compared with baseline</p><p className="mt-1 text-lg font-medium text-ink">{result.risk.ratio_to_baseline >= 0 ? "+" : ""}{formatNumber(result.risk.ratio_to_baseline * 100, 0)}%</p></div>
                <div><p className="text-xs text-ink-muted">Model response</p><p className="mt-1 text-lg font-medium text-ink">{Math.round(result.latency_ms)} ms</p></div>
              </div>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              <div className="rounded-[26px] bg-forest p-6 text-leaf">
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-leaf/55">Weather received</p>
                <div className="mt-5 grid grid-cols-2 gap-y-5">
                  <div><p className="text-xs text-leaf/60">Mean temperature</p><p className="mt-1 text-2xl">{formatNumber(result.weather_summary.temp_mean)}°</p></div>
                  <div><p className="text-xs text-leaf/60">Rain total</p><p className="mt-1 text-2xl">{formatNumber(result.weather_summary.rain_total)} mm</p></div>
                  <div><p className="text-xs text-leaf/60">Heat-stress days</p><p className="mt-1 text-2xl">{result.weather_summary.heat_stress_days}</p></div>
                  <div><p className="text-xs text-leaf/60">Water balance</p><p className="mt-1 text-2xl">{formatNumber(result.weather_summary.water_balance)}</p></div>
                </div>
                <p className="mt-5 border-t border-leaf/15 pt-3 font-mono text-[10px] uppercase tracking-[0.08em] text-leaf/50">Source · {result.weather_summary.source}</p>
              </div>
              <div className="rounded-[26px] border border-hairline bg-leaf p-6 text-forest">
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Risk readout</p>
                <p className="mt-3 text-lg leading-[1.45]">{result.risk.rationale}</p>
                {result.risk.advisories.length > 0 && <ul className="mt-4 space-y-2 border-t border-forest/15 pt-4 text-sm"><li>{result.risk.advisories[0]}</li></ul>}
              </div>
            </div>
            <div className="rounded-[26px] border border-hairline bg-surface p-6">
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div><p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Why the model moved</p><h2 className="mt-2 text-2xl font-medium text-ink">Yield factors</h2></div>
                <span className="text-xs text-ink-muted">SHAP · {result.model.version}</span>
              </div>
              <div className="mt-5 space-y-4">
                {result.explanation.contributions.map((item) => (
                  <div key={item.feature}>
                    <div className="flex items-center justify-between gap-4 text-sm"><span className="font-medium text-ink">{item.feature}</span><span className={item.direction === "increase" ? "text-risk-low" : item.direction === "decrease" ? "text-risk-high" : "text-ink-muted"}>{item.direction === "increase" ? "+" : item.direction === "decrease" ? "−" : ""}{formatNumber(Math.abs(item.shap), 2)}</span></div>
                    <div className="mt-2 h-2 rounded-full bg-page"><div className={`h-full rounded-full ${item.direction === "increase" ? "bg-risk-low" : item.direction === "decrease" ? "bg-risk-high" : "bg-forest/40"}`} style={{ width: `${Math.max(8, Math.abs(item.shap) / maxContribution * 100)}%` }} /></div>
                    <p className="mt-1 text-xs text-ink-muted">{item.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>
        ) : (
          <div className="flex min-h-[420px] flex-col justify-between rounded-[28px] border border-dashed border-hairline bg-leaf/35 p-7">
            <div><p className="font-mono text-[10px] uppercase tracking-[0.13em] text-forest/60">Your forecast will appear here</p><h2 className="mt-3 max-w-sm text-3xl font-medium leading-tight text-forest">One clear estimate. The reasoning beside it.</h2><p className="mt-3 max-w-md text-sm leading-[1.6] text-ink-muted">Run a forecast to see the model interval, weather summary, baseline comparison, and the inputs that pushed the result up or down.</p></div>
            <div className="flex items-end justify-between gap-4"><Link href="/dashboard" className="text-sm font-medium text-forest underline-offset-4 hover:underline">Back to dashboard</Link><Image src="/mascot6.png" alt="CropSense mascot reviewing soil readings" width={180} height={180} className="w-36 object-contain sm:w-44" /></div>
          </div>
        )}
      </div>
    </div>
  );
}
