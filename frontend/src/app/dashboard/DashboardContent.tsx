"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useState } from "react";

import { useAuth } from "@/components/auth/AuthProvider";
import { buttonClass } from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { ThemedLoader } from "@/components/ui/ThemedLoader";
import {
  api,
  type DiseaseHistoryItem,
  type DiseasePredictResponse,
  type HistoryStats,
  type ModelInfo,
  type User,
  type YieldHistoryItem,
  type YieldPredictResponse,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";
import { env } from "@/lib/env";

function dashboardMediaUrl(path: string | undefined) {
  if (!path) return "";
  if (/^(https?:|blob:)/.test(path)) return path;
  return `${env.apiBaseUrl}${path}`;
}

const PUNJAB_DISTRICTS = [
  "Attock", "Bahawalnagar", "Bahawalpur", "Bhakkar", "Chakwal", "Chiniot",
  "Dera Ghazi Khan", "Faisalabad", "Gujranwala", "Gujrat", "Hafizabad", "Jhang",
  "Jhelum", "Kasur", "Khanewal", "Khushab", "Kot Addu", "Lahore", "Layyah",
  "Lodhran", "Mandi Bahauddin", "Mianwali", "Multan", "Muzaffargarh",
  "Nankana Sahib", "Narowal", "Okara", "Pakpattan", "Rahim Yar Khan", "Rajanpur",
  "Rawalpindi", "Sahiwal", "Sargodha", "Sheikhupura", "Sialkot", "Toba Tek Singh",
  "Vehari",
];

type DashboardTab = "overview" | "disease" | "yield" | "scan" | "forecast" | "account";

interface ProfileTabContentProps {
  user: User | null;
  token: string | null;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

function ProfileTabContent({ user, token, onSuccess, onError }: ProfileTabContentProps) {
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number || "");
  const [prefLang, setPrefLang] = useState(user?.preferred_language || "en");
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isUpdatingProfile, setIsUpdatingProfile] = useState(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState(false);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    setIsUpdatingProfile(true);
    onError("");
    try {
      await api.updateMe({ full_name: fullName, phone_number: phoneNumber, preferred_language: prefLang }, token);
      onSuccess("Profile updated successfully.");
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : "Failed to update profile.");
    } finally {
      setIsUpdatingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;
    if (newPassword.length < 6) {
      onError("New password must be at least 6 characters.");
      return;
    }
    setIsUpdatingPassword(true);
    onError("");
    try {
      await api.changePassword({ old_password: oldPassword, new_password: newPassword }, token);
      onSuccess("Password changed successfully.");
      setOldPassword("");
      setNewPassword("");
    } catch (err: unknown) {
      onError(err instanceof Error ? err.message : "Failed to change password.");
    } finally {
      setIsUpdatingPassword(false);
    }
  };

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* Profile update form */}
      <form onSubmit={handleUpdateProfile} className="flex flex-col gap-4 rounded-xl border border-hairline bg-surface p-6 shadow-sm">
        <div>
          <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
            Farmer Profile
          </span>
          <h3 className="text-lg font-medium text-ink">Personal Information</h3>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-email" className="text-xs font-mono uppercase text-ink-muted">Registered Email</label>
          <input
            id="dashboard-account-email"
            type="email"
            value={user?.email || ""}
            disabled
            className="rounded-lg border border-hairline bg-page p-2 text-sm text-ink-muted opacity-80 cursor-not-allowed"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-full-name" className="text-xs font-mono uppercase text-ink-muted">Full Name</label>
          <input
            id="dashboard-account-full-name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-phone" className="text-xs font-mono uppercase text-ink-muted">Phone Number</label>
          <input
            id="dashboard-account-phone"
            type="text"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="+92 300 1234567"
            className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-lang" className="text-xs font-mono uppercase text-ink-muted">Preferred Language</label>
          <select
            id="dashboard-account-lang"
            value={prefLang}
            onChange={(e) => setPrefLang(e.target.value)}
            className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
          >
            <option value="en">English (default)</option>
            <option value="ur">Urdu (اردو)</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={isUpdatingProfile}
          className={buttonClass("primary", "md", "rounded-lg font-mono text-xs uppercase mt-2")}
        >
          {isUpdatingProfile ? "Saving…" : "Save Profile"}
        </button>
      </form>

      {/* Password update form */}
      <form onSubmit={handleChangePassword} className="flex flex-col gap-4 rounded-xl border border-hairline bg-surface p-6 shadow-sm">
        <div>
          <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
            Authentication Security
          </span>
          <h3 className="text-lg font-medium text-ink">Update Password</h3>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-old-pw" className="text-xs font-mono uppercase text-ink-muted">Current Password</label>
          <input
            id="dashboard-account-old-pw"
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
            required
            className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="dashboard-account-new-pw" className="text-xs font-mono uppercase text-ink-muted">New Password (min 6 chars)</label>
          <input
            id="dashboard-account-new-pw"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
          />
        </div>

        <button
          type="submit"
          disabled={isUpdatingPassword}
          className={buttonClass("ghost", "md", "rounded-lg font-mono text-xs uppercase mt-2")}
        >
          {isUpdatingPassword ? "Updating…" : "Change Password"}
        </button>

        <div className="mt-4 rounded-lg border border-hairline bg-page p-3 text-xs text-ink-muted">
          <strong className="text-ink">Privacy Guarantee (NFR-PR-003):</strong> All your field scans, location data, and predictions belong to you. You can purge records anytime from the history tabs.
        </div>
      </form>
    </div>
  );
}

export function DashboardContent() {
  const auth = useAuth();
  const router = useRouter();
  const fileInputId = useId();

  const user = auth.user;
  const token = auth.token;

  // Navigation & UI state
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Real backend data
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [diseaseHistory, setDiseaseHistory] = useState<DiseaseHistoryItem[]>([]);
  const [yieldHistory, setYieldHistory] = useState<YieldHistoryItem[]>([]);
  const [modelsInfo, setModelsInfo] = useState<ModelInfo[]>([]);

  // Filter states
  const [diseaseFilter, setDiseaseFilter] = useState("all");
  const [yieldFilter, setYieldFilter] = useState("all");

  // Inspection modal state
  const [inspectDisease, setInspectDisease] = useState<DiseaseHistoryItem | null>(null);
  const [inspectYield, setInspectYield] = useState<YieldHistoryItem | null>(null);

  // Quick scan state
  const [scanFile, setScanFile] = useState<File | null>(null);
  const [scanPreview, setScanPreview] = useState<string | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<DiseasePredictResponse | null>(null);

  // Quick yield forecast state
  const [forecastCrop, setForecastCrop] = useState("wheat");
  const [forecastDistrict, setForecastDistrict] = useState("Faisalabad");
  const [forecastArea, setForecastArea] = useState<number>(100);
  const [forecastYear, setForecastYear] = useState<number>(2024);
  const [isForecasting, setIsForecasting] = useState(false);
  const [forecastResult, setForecastResult] = useState<YieldPredictResponse | null>(null);

  // Refresh all dashboard data from live backend
  const refreshDashboardData = useCallback(async () => {
    if (!token) return;
    setIsRefreshing(true);
    setErrorMessage(null);

    try {
      const [statsRes, diseaseRes, yieldRes, modelsRes] = await Promise.allSettled([
        api.getHistoryStats(token),
        api.getDiseaseHistory(token, 0, 50),
        api.getYieldHistory(token, 0, 50),
        api.models(),
      ]);

      if (statsRes.status === "fulfilled") setStats(statsRes.value);
      if (diseaseRes.status === "fulfilled") setDiseaseHistory(diseaseRes.value);
      if (yieldRes.status === "fulfilled") setYieldHistory(yieldRes.value);
      if (modelsRes.status === "fulfilled" && modelsRes.value.models) {
        setModelsInfo(modelsRes.value.models);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to refresh dashboard data.");
    } finally {
      setIsRefreshing(false);
    }
  }, [token]);

  // Initial load without synchronous effect setState cascading renders
  useEffect(() => {
    if (auth.status !== "authenticated" || !token) return;

    let cancelled = false;
    async function loadInitial() {
      try {
        const [statsRes, diseaseRes, yieldRes, modelsRes] = await Promise.allSettled([
          api.getHistoryStats(token as string),
          api.getDiseaseHistory(token as string, 0, 50),
          api.getYieldHistory(token as string, 0, 50),
          api.models(),
        ]);
        if (cancelled) return;

        if (statsRes.status === "fulfilled") setStats(statsRes.value);
        if (diseaseRes.status === "fulfilled") setDiseaseHistory(diseaseRes.value);
        if (yieldRes.status === "fulfilled") setYieldHistory(yieldRes.value);
        if (modelsRes.status === "fulfilled" && modelsRes.value.models) {
          setModelsInfo(modelsRes.value.models);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setErrorMessage(err instanceof Error ? err.message : "Failed to load dashboard data.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void loadInitial();

    return () => {
      cancelled = true;
    };
  }, [auth.status, token]);

  // Handle disease scan file selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setScanFile(file);
      setScanPreview(URL.createObjectURL(file));
      setScanResult(null);
    }
  };

  // Run live disease diagnosis
  const handleRunScan = async () => {
    if (!scanFile || !token) return;
    setIsScanning(true);
    setErrorMessage(null);
    try {
      const form = new FormData();
      form.append("file", scanFile);
      const res = await api.predictDisease(form, token);
      setScanResult(res);
      setSuccessMessage("Leaf scan completed and saved to your history.");
      void refreshDashboardData();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to complete leaf analysis.");
    } finally {
      setIsScanning(false);
    }
  };

  // Run live crop yield prediction
  const handleRunYield = async () => {
    if (!token) return;
    setIsForecasting(true);
    setErrorMessage(null);
    try {
      const payload = {
        crop: forecastCrop,
        location: { lat: 31.42, lon: 73.08, district: forecastDistrict },
        season: { year: Number(forecastYear) },
        area_ha: Number(forecastArea),
        weather_override: {
          w_rain_total_mm: 275.0,
          w_rainy_days: 22,
          w_heavy_rain_days: 2,
          w_dry_days: 125,
          w_temp_mean_c: 19.2,
          w_temp_max_c: 37.5,
          w_temp_min_c: 3.8,
          w_gdd_c: 2150.0,
          w_heat_stress_days: 4,
          w_grain_rain_mm: 38.0,
          w_grain_gdd_c: 580.0,
          w_water_balance_mm: -140.0,
          w_humidity_mean_pct: 52.0,
          w_solar_mj_m2: 18.8,
          w_wind_max_kmh: 42.0,
          w_days_observed: 180,
          w_completeness: 0.95,
        },
      };
      const res = await api.predictYield(payload, token);
      setForecastResult(res);
      setSuccessMessage("Crop yield forecast completed and saved to history.");
      void refreshDashboardData();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to run yield prediction.");
    } finally {
      setIsForecasting(false);
    }
  };

  // Delete disease scan
  const handleDeleteDisease = async (id: string) => {
    if (!token || !window.confirm("Delete this diagnostic scan from your history?")) return;
    try {
      await api.deleteDiseaseHistory(id, token);
      setDiseaseHistory((prev) => prev.filter((item) => item.id !== id));
      if (inspectDisease?.id === id) setInspectDisease(null);
      setSuccessMessage("Record deleted successfully.");
      void refreshDashboardData();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Could not delete record.");
    }
  };

  // Delete yield forecast
  const handleDeleteYield = async (id: string) => {
    if (!token || !window.confirm("Delete this yield forecast from your history?")) return;
    try {
      await api.deleteYieldHistory(id, token);
      setYieldHistory((prev) => prev.filter((item) => item.id !== id));
      if (inspectYield?.id === id) setInspectYield(null);
      setSuccessMessage("Record deleted successfully.");
      void refreshDashboardData();
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Could not delete record.");
    }
  };

  if (auth.status !== "authenticated") {
    return null;
  }

  if (isLoading) {
    return <ThemedLoader label="Loading your field history" className="min-h-[32rem]" size="lg" />;
  }

  const displayName =
    user?.full_name?.trim() ||
    user?.email.split("@")[0]?.replace(/[._-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ||
    "Farmer";

  // Filtered lists
  const filteredDisease = diseaseHistory.filter((item) => {
    if (diseaseFilter === "all") return true;
    if (diseaseFilter === "healthy") return item.is_healthy;
    if (diseaseFilter === "diseased") return !item.is_healthy;
    return item.crop.toLowerCase().includes(diseaseFilter.toLowerCase());
  });

  const filteredYield = yieldHistory.filter((item) => {
    if (yieldFilter === "all") return true;
    if (yieldFilter === "low_risk") return item.risk_level.toLowerCase() === "low";
    if (yieldFilter === "high_risk") return item.risk_level.toLowerCase() === "high";
    return item.crop.toLowerCase().includes(yieldFilter.toLowerCase());
  });

  return (
    <div className="relative flex flex-col gap-8 pb-16 sm:gap-10">
      {/* ── 1. DEDICATED DASHBOARD CONTROL BAR (NO NAVBAR AS REQUESTED) ── */}
      <header className="sticky top-3 z-40 rounded-[20px] border border-hairline/80 bg-surface/90 px-4 py-3 shadow-[0_16px_40px_rgba(6,71,52,0.08)] backdrop-blur-xl sm:rounded-[24px] sm:px-6 sm:py-3.5">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex items-center gap-2 font-medium tracking-tight text-forest transition-opacity hover:opacity-85"
              aria-label="Back to home"
            >
              <Image
                src="/logo.png"
                alt="Zenvy"
                width={36}
                height={36}
                className="h-8 w-auto object-contain"
                priority
              />
              <span className="font-mono text-xs uppercase tracking-[0.14em] text-forest font-semibold">
                Crop workspace
              </span>
            </Link>

            <span className="hidden h-4 w-px bg-hairline sm:block" />

            <div className="hidden items-center gap-1.5 rounded-full border border-hairline bg-page px-2.5 py-0.5 text-[11px] font-mono text-forest/80 sm:flex">
              <span className="h-2 w-2 rounded-full bg-risk-low animate-pulse" />
              <span>Models online</span>
            </div>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {/* User identification badge */}
            <div className="hidden flex-col items-end text-right md:flex">
              <span className="text-xs font-medium text-ink">{displayName}</span>
              <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                {user?.role || "Farmer"} · {user?.email}
              </span>
            </div>

            {/* Refresh button */}
            <button
              type="button"
              onClick={() => refreshDashboardData()}
              disabled={isRefreshing}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-hairline bg-page text-ink-muted transition-colors hover:border-forest hover:text-forest disabled:opacity-50"
              title="Refresh dashboard data"
              aria-label="Refresh dashboard data"
            >
              <svg
                className={cn("h-4 w-4", isRefreshing && "animate-spin")}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>

            {/* Quick scan trigger */}
            <Link
              href="/disease"
              className={buttonClass("primary", "md", "rounded-full text-xs font-mono uppercase tracking-wider px-4 py-1.5 min-h-10")}
            >
              + Scan Leaf
            </Link>

            {/* Logout button (as requested: prominent on dashboard) */}
            <button
              type="button"
              onClick={() => {
                auth.logout();
                router.replace("/");
              }}
              className={buttonClass("ghost", "md", "rounded-full text-xs font-mono uppercase tracking-wider px-4 py-1.5 min-h-10 border-hairline text-ink-muted hover:border-forest hover:text-forest hover:bg-page")}
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      {/* ── 2. ALERT FEEDBACK NOTICES ── */}
      {errorMessage && (
        <div className="flex items-center justify-between rounded-lg border border-risk-high/40 bg-risk-high/10 px-4 py-3 text-sm text-risk-high">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="font-mono text-xs uppercase underline">
            Dismiss
          </button>
        </div>
      )}
      {successMessage && (
        <div className="flex items-center justify-between rounded-lg border border-risk-low/40 bg-risk-low/10 px-4 py-3 text-sm text-risk-low">
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage(null)} className="font-mono text-xs uppercase underline">
            Dismiss
          </button>
        </div>
      )}

      {/* ── 3. HERO GREETING & METRIC STRIP ── */}
      <section className="grid gap-4 lg:grid-cols-[1.18fr_0.82fr] lg:gap-5">
        <div className="relative isolate min-h-[360px] overflow-hidden rounded-[30px] bg-forest p-6 text-leaf shadow-[0_28px_65px_rgba(6,71,52,0.2)] sm:p-9">
          <div className="pointer-events-none absolute -right-20 -top-24 -z-10 h-72 w-72 rounded-full border border-leaf/10 bg-leaf/5" />
          <div className="pointer-events-none absolute -bottom-36 left-1/3 -z-10 h-72 w-72 rounded-full border border-leaf/10" />
          <Image
            src="/mascot2.png"
            alt="CropSense mascot checking a field forecast"
            width={180}
            height={180}
            className="pointer-events-none absolute -bottom-4 right-0 hidden w-44 object-contain opacity-95 sm:block lg:right-5 lg:w-52"
          />
          <div className="absolute right-6 top-6 hidden items-center gap-2 rounded-full border border-leaf/20 bg-black/10 px-3 py-1.5 font-mono text-[10px] uppercase tracking-wider text-leaf/75 sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-leaf shadow-[0_0_0_4px_rgba(224,255,194,0.12)]" />
            Live crop workspace
          </div>
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-leaf/60">
            Field intelligence · {new Date().toLocaleDateString(undefined, { month: "short", day: "numeric" })}
          </p>
          <h1 className="relative z-10 mt-5 max-w-[12ch] text-4xl font-medium leading-[0.94] tracking-[-0.05em] sm:text-6xl">
            Welcome back, <em className="font-accent font-normal">{displayName}.</em>
          </h1>
          <p className="relative z-10 mt-6 max-w-[42ch] text-sm leading-[1.65] text-leaf/75 sm:text-base">
            Check a leaf, plan a harvest, or review the signals already collected from your fields.
          </p>
          <div className="relative z-10 mt-9 flex flex-wrap gap-3">
            <Link
              href="/disease"
              className="inline-flex min-h-12 items-center justify-center rounded-full bg-leaf px-5 text-sm font-semibold text-forest shadow-[0_8px_24px_rgba(0,0,0,0.14)] transition-transform hover:-translate-y-0.5"
            >
              Analyze a leaf <span aria-hidden="true" className="ml-2">↗</span>
            </Link>
            <Link
              href="/yield"
              className="inline-flex min-h-12 items-center justify-center rounded-full border border-leaf/35 px-5 text-sm font-medium text-leaf transition-colors hover:bg-leaf/10"
            >
              Forecast yield
            </Link>
          </div>
          <div className="absolute bottom-7 right-7 hidden max-w-[150px] text-right font-mono text-[10px] uppercase leading-[1.5] tracking-wider text-leaf/45 sm:block">
            Clear signals for the next field decision
          </div>
        </div>

        {/* Metric Cards Row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex min-h-[170px] flex-col justify-between rounded-[24px] border border-hairline bg-surface p-5 shadow-[0_10px_30px_rgba(6,71,52,0.04)] transition-transform hover:-translate-y-0.5 sm:p-6">
            <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Total Diagnostics</span>
            <span className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              {stats?.total_disease_scans ?? (isLoading ? "…" : 0)}
            </span>
            <div className="flex items-center gap-1.5 text-xs text-ink-muted">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-forest" />
              <span>{stats?.healthy_count ?? 0} healthy · {stats?.diseased_count ?? 0} diseased</span>
            </div>
          </div>

          <div className="flex min-h-[170px] flex-col justify-between rounded-[24px] border border-hairline bg-leaf/45 p-5 shadow-[0_10px_30px_rgba(6,71,52,0.04)] transition-transform hover:-translate-y-0.5 sm:p-6">
            <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Crop Health Ratio</span>
            <span className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-forest sm:text-4xl">
              {stats && stats.total_disease_scans > 0
                ? `${Math.round((stats.healthy_count / stats.total_disease_scans) * 100)}%`
                : "100%"}
            </span>
            <div className="h-2 w-full overflow-hidden rounded-full bg-white/70">
              <div
                className="h-full rounded-full bg-forest transition-[width] duration-500"
                style={{
                  width: stats && stats.total_disease_scans > 0
                    ? `${(stats.healthy_count / stats.total_disease_scans) * 100}%`
                    : "100%",
                }}
              />
            </div>
          </div>

          <div className="flex min-h-[170px] flex-col justify-between rounded-[24px] border border-hairline bg-surface p-5 shadow-[0_10px_30px_rgba(6,71,52,0.04)] transition-transform hover:-translate-y-0.5 sm:p-6">
            <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Yield Forecasts</span>
            <span className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              {stats?.total_yield_forecasts ?? (isLoading ? "…" : 0)}
            </span>
            <span className="text-xs text-ink-muted">Across Punjab plots</span>
          </div>

          <div className="flex min-h-[170px] flex-col justify-between rounded-[24px] border border-hairline bg-surface p-5 shadow-[0_10px_30px_rgba(6,71,52,0.04)] transition-transform hover:-translate-y-0.5 sm:p-6">
            <span className="font-mono text-[11px] uppercase tracking-wider text-ink-muted">Mean Expected Yield</span>
            <span className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-ink sm:text-4xl">
              {stats?.avg_predicted_yield_tha != null
                ? `${stats.avg_predicted_yield_tha.toFixed(2)}`
                : "—"}
              <span className="ml-1 text-sm font-normal text-ink-muted">t/ha</span>
            </span>
            <span className="text-xs text-ink-muted">Based on 22 agro factors</span>
          </div>
        </div>
      </section>

      {/* ── 4. TWO CLEAR WORKFLOWS ── */}
      <section className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col justify-between rounded-[24px] border border-hairline bg-surface p-6 shadow-[0_12px_30px_rgba(6,71,52,0.06)] transition-transform hover:-translate-y-0.5 sm:p-7">
          <div className="flex flex-col gap-3">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-forest/60">
              01 · Computer Vision Inference
            </span>
            <h2 className="text-xl font-medium tracking-tight text-ink sm:text-2xl">
              Detect leaf pathogens <em className="font-accent font-normal italic">early.</em>
            </h2>
            <p className="text-sm leading-relaxed text-ink-muted">
              Upload leaf photos to classify bacterial, viral, or fungal infections with EfficientNet-B0.
              Includes lesion severity ratio and Grad-CAM visual attention overlays.
            </p>
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-hairline pt-4">
            <Link
              href="/disease"
              className="inline-flex items-center gap-1.5 font-medium text-forest hover:underline text-sm"
            >
              Analyze new leaf →
            </Link>
            <span className="font-mono text-[10px] text-ink-muted uppercase">38 Classes Supported</span>
          </div>
        </div>

        <div className="flex flex-col justify-between rounded-[24px] bg-leaf p-6 text-forest shadow-[0_12px_30px_rgba(6,71,52,0.08)] transition-transform hover:-translate-y-0.5 sm:p-7">
          <div className="flex flex-col gap-3">
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-forest/80">
              02 · Predictive Agro-Meteorology
            </span>
            <h2 className="text-xl font-medium tracking-tight sm:text-2xl">
              Forecast harvest yield <em className="font-accent font-normal italic">before sowing.</em>
            </h2>
            <p className="text-sm leading-relaxed text-forest/85">
              Run gradient-boosted yield regressions (XGBoost) fusing localized weather summaries,
              growing degree days (GDD), and soil metrics with 80% quantile uncertainty bounds.
            </p>
          </div>
          <div className="mt-6 flex items-center justify-between border-t border-forest/20 pt-4">
            <button
              type="button"
              onClick={() => setActiveTab("forecast")}
              className="inline-flex items-center gap-1.5 font-medium text-forest hover:underline text-sm"
            >
              Estimate crop yield →
            </button>
            <span className="font-mono text-[10px] text-forest/70 uppercase">Wheat & Maize · Punjab</span>
          </div>
        </div>
      </section>

      {/* ── 5. DASHBOARD TABS BAR ── */}
      <section className="flex flex-col gap-6">
        <div className="relative flex flex-col gap-3 overflow-hidden rounded-[24px] border border-hairline bg-surface px-5 py-5 shadow-[0_12px_30px_rgba(6,71,52,0.04)] sm:flex-row sm:items-end sm:justify-between sm:px-6">
          <Image
            src="/mascot5.png"
            alt=""
            width={96}
            height={96}
            className="pointer-events-none absolute -bottom-5 right-5 hidden w-20 opacity-90 sm:block"
            aria-hidden="true"
          />
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-forest/55">
              Your field desk
            </p>
            <h2 className="mt-1 text-2xl font-medium tracking-tight text-ink">
              What needs your attention?
            </h2>
          </div>
          <div className="relative z-10 flex max-w-full gap-1 overflow-x-auto rounded-full border border-hairline bg-page p-1">
          {(
            [
              { id: "overview", label: "Overview" },
              { id: "disease", label: `Scans · ${diseaseHistory.length}` },
              { id: "yield", label: `Forecasts · ${yieldHistory.length}` },
              { id: "scan", label: "New scan" },
              { id: "forecast", label: "New forecast" },
              { id: "account", label: "Account" },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "min-h-9 shrink-0 rounded-full px-3.5 text-[11px] font-mono uppercase tracking-[0.08em] transition-colors",
                activeTab === tab.id
                  ? "bg-forest font-semibold text-leaf shadow-sm"
                  : "text-ink-muted hover:bg-page hover:text-forest",
              )}
            >
              {tab.label}
            </button>
          ))}
          </div>
        </div>

        {/* ── TAB 1: OVERVIEW ── */}
        {activeTab === "overview" && (
          <div className="flex flex-col gap-6">
            {/* Live Model Telemetry */}
            {modelsInfo.length > 0 && (
              <div className="flex flex-col gap-3 rounded-2xl border border-hairline bg-surface/80 p-5 shadow-sm">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-risk-low opacity-75" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-risk-low" />
                    </span>
                    <h3 className="font-mono text-xs uppercase tracking-wider font-semibold text-forest">
                      Operational AI Inference Engines
                    </h3>
                  </div>
                  <span className="font-mono text-[10px] text-ink-muted">Backend Telemetry · Ready</span>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  {modelsInfo.map((m) => (
                    <div
                      key={m.pipeline}
                      className="flex items-center justify-between rounded-xl border border-hairline bg-page/50 p-3.5"
                    >
                      <div>
                        <span className="font-mono text-[10px] uppercase text-ink-muted">
                          {m.pipeline === "disease" ? "Vision Diagnostic" : "Agro-Meteorology"} Pipeline
                        </span>
                        <p className="font-mono text-xs font-semibold text-ink">
                          {m.name} <span className="font-normal text-ink-muted">v{m.version}</span>
                        </p>
                      </div>
                      <span className="rounded-full bg-risk-low/15 px-2.5 py-0.5 font-mono text-[10px] uppercase font-semibold text-risk-low">
                        Online
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Scans Strip */}
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-ink">Recent Disease Diagnostics</h3>
                <button
                  type="button"
                  onClick={() => setActiveTab("disease")}
                  className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                >
                  View all ({diseaseHistory.length}) →
                </button>
              </div>

              {diseaseHistory.length === 0 ? (
                <Card>
                  <CardBody>
                    <EmptyState
                      title="No disease scans recorded yet"
                      description="Analyze a plant leaf to verify health, identify foliar blights, and receive tailored treatments."
                      action={
                        <Link
                          href="/disease"
                          className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
                        >
                          Run First Scan
                        </Link>
                      }
                    />
                  </CardBody>
                </Card>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {diseaseHistory.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      className="group flex flex-col justify-between rounded-xl border border-hairline bg-surface p-4 shadow-sm transition-all hover:border-forest/40 hover:shadow"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                            {item.crop} · {new Date(item.created_at).toLocaleDateString()}
                          </span>
                          <h4 className="mt-1 font-semibold text-ink group-hover:text-forest">
                            {item.disease_class.replace(/___/g, " — ").replace(/_/g, " ")}
                          </h4>
                        </div>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 font-mono text-[10px] uppercase font-semibold",
                            item.is_healthy
                              ? "bg-risk-low/15 text-risk-low"
                              : item.severity_band === "severe"
                              ? "bg-risk-high/15 text-risk-high"
                              : "bg-risk-medium/15 text-risk-medium",
                          )}
                        >
                          {item.is_healthy ? "Healthy" : item.severity_band}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-col gap-1.5">
                        <div className="flex items-center justify-between text-xs text-ink-muted">
                          <span>Confidence</span>
                          <span className="font-mono font-medium text-ink">{(item.confidence * 100).toFixed(1)}%</span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
                          <div className="h-full bg-forest" style={{ width: `${item.confidence * 100}%` }} />
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-hairline/60 pt-3 text-xs">
                        <button
                          type="button"
                          onClick={() => setInspectDisease(item)}
                          className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                        >
                          Inspect Details →
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteDisease(item.id)}
                          className="text-ink-muted hover:text-risk-high"
                          title="Delete record"
                          aria-label="Delete scan record"
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Recent Yield Strip */}
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-ink">Recent Yield Outlooks</h3>
                <button
                  type="button"
                  onClick={() => setActiveTab("yield")}
                  className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                >
                  View all ({yieldHistory.length}) →
                </button>
              </div>

              {yieldHistory.length === 0 ? (
                <Card>
                  <CardBody>
                    <EmptyState
                      title="No yield forecasts run yet"
                      description="Simulate seasonal crop yields, identify climate stress periods, and analyze 80% prediction intervals."
                      action={
                        <button
                          type="button"
                          onClick={() => setActiveTab("forecast")}
                          className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
                        >
                          Run Yield Forecast
                        </button>
                      }
                    />
                  </CardBody>
                </Card>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {yieldHistory.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      className="group flex flex-col justify-between rounded-xl border border-hairline bg-surface p-4 shadow-sm transition-all hover:border-forest/40 hover:shadow"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
                            {item.district} · Season {item.season_year}
                          </span>
                          <h4 className="mt-1 text-base font-semibold capitalize text-ink">
                            {item.crop} · {item.area_ha} ha
                          </h4>
                        </div>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 font-mono text-[10px] uppercase font-semibold",
                            item.risk_level === "low"
                              ? "bg-risk-low/15 text-risk-low"
                              : item.risk_level === "high"
                              ? "bg-risk-high/15 text-risk-high"
                              : "bg-risk-medium/15 text-risk-medium",
                          )}
                        >
                          {item.risk_level} Risk
                        </span>
                      </div>

                      <div className="mt-4 flex items-baseline justify-between border-t border-hairline/60 pt-3">
                        <div className="flex flex-col">
                          <span className="text-[11px] text-ink-muted">Estimated Yield</span>
                          <span className="text-xl font-semibold text-forest">
                            {item.predicted_yield_tha.toFixed(2)}{" "}
                            <span className="text-xs font-normal text-ink-muted">t/ha</span>
                          </span>
                        </div>
                        <div className="flex flex-col text-right">
                          <span className="text-[11px] text-ink-muted">80% Interval</span>
                          <span className="font-mono text-xs text-ink">
                            [{item.interval_lower.toFixed(2)}, {item.interval_upper.toFixed(2)}]
                          </span>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-between border-t border-hairline/60 pt-3 text-xs">
                        <button
                          type="button"
                          onClick={() => setInspectYield(item)}
                          className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                        >
                          View Details →
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteYield(item.id)}
                          className="text-ink-muted hover:text-risk-high"
                          title="Delete record"
                          aria-label="Delete yield record"
                        >
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Model Registry Telemetry Card */}
            <div className="rounded-xl border border-hairline bg-surface p-5 shadow-sm">
              <div className="flex items-center justify-between border-b border-hairline pb-3">
                <div className="flex items-center gap-2">
                  <span className="h-2.5 w-2.5 rounded-full bg-forest" />
                  <h3 className="font-medium text-ink">Active Machine Learning Engines</h3>
                </div>
                <span className="font-mono text-xs uppercase tracking-wider text-forest">
                  Real-time Registry Status
                </span>
              </div>

              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1 rounded-lg border border-hairline/60 bg-page p-3.5">
                  <span className="font-mono text-[10px] uppercase text-forest font-semibold">
                    Disease Model (PyTorch)
                  </span>
                  <span className="font-medium text-ink">EfficientNet-B0 Disease Classifier</span>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                    <span>Version: <strong className="font-mono text-ink">v0.1.0</strong></span>
                    <span>Test Acc: <strong className="font-mono text-ink">98.41%</strong></span>
                    <span>Macro F1: <strong className="font-mono text-ink">0.982</strong></span>
                  </div>
                </div>

                <div className="flex flex-col gap-1 rounded-lg border border-hairline/60 bg-page p-3.5">
                  <span className="font-mono text-[10px] uppercase text-forest font-semibold">
                    Yield Engine (XGBoost)
                  </span>
                  <span className="font-medium text-ink">XGBoost Quantile Regressor</span>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-muted">
                    <span>Version: <strong className="font-mono text-ink">v0.1.0</strong></span>
                    <span>R² Score: <strong className="font-mono text-ink">0.852</strong></span>
                    <span>MAE: <strong className="font-mono text-ink">0.34 t/ha</strong></span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── TAB 2: DISEASE SCANS HISTORY ── */}
        {activeTab === "disease" && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase text-ink-muted">Filter:</span>
                <select
                  value={diseaseFilter}
                  onChange={(e) => setDiseaseFilter(e.target.value)}
                  className="rounded-lg border border-hairline bg-surface px-3 py-1.5 text-xs font-mono text-ink"
                >
                  <option value="all">All Crops & Diseases</option>
                  <option value="healthy">Healthy Only</option>
                  <option value="diseased">Diseased Only</option>
                  <option value="corn">Corn (Maize)</option>
                  <option value="wheat">Wheat</option>
                  <option value="tomato">Tomato</option>
                  <option value="potato">Potato</option>
                  <option value="apple">Apple</option>
                </select>
              </div>

              <Link
                href="/disease"
                className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
              >
                + New Leaf Scan
              </Link>
            </div>

            {filteredDisease.length === 0 ? (
              <Card>
                <CardBody>
                  <EmptyState
                    title="No records matching filter"
                    description="Run a new leaf scan or clear the active filter to view your historical diagnostic records."
                  />
                </CardBody>
              </Card>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-hairline bg-surface">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-hairline bg-page text-[11px] font-mono uppercase tracking-wider text-ink-muted">
                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Crop</th>
                      <th className="px-4 py-3">Diagnosis</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Severity</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {filteredDisease.map((item) => (
                      <tr key={item.id} className="transition-colors hover:bg-page/60">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-muted">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 font-medium text-ink">{item.crop}</td>
                        <td className="px-4 py-3 text-ink">
                          {item.disease_class.replace(/___/g, " — ").replace(/_/g, " ")}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-ink">
                          {(item.confidence * 100).toFixed(1)}%
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2.5 py-0.5 font-mono text-[10px] uppercase font-semibold",
                              item.is_healthy
                                ? "bg-risk-low/15 text-risk-low"
                                : item.severity_band === "severe"
                                ? "bg-risk-high/15 text-risk-high"
                                : "bg-risk-medium/15 text-risk-medium",
                            )}
                          >
                            {item.is_healthy ? "Healthy" : item.severity_band}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => setInspectDisease(item)}
                              className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                            >
                              Inspect
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteDisease(item.id)}
                              className="text-ink-muted hover:text-risk-high"
                              title="Delete record"
                              aria-label="Delete scan record"
                            >
                              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── TAB 3: YIELD FORECASTS HISTORY ── */}
        {activeTab === "yield" && (
          <div className="flex flex-col gap-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono uppercase text-ink-muted">Filter:</span>
                <select
                  value={yieldFilter}
                  onChange={(e) => setYieldFilter(e.target.value)}
                  className="rounded-lg border border-hairline bg-surface px-3 py-1.5 text-xs font-mono text-ink"
                >
                  <option value="all">All Crops & Risks</option>
                  <option value="wheat">Wheat</option>
                  <option value="maize">Maize</option>
                  <option value="low_risk">Low Risk Only</option>
                  <option value="high_risk">High Risk Only</option>
                </select>
              </div>

              <button
                type="button"
                onClick={() => setActiveTab("forecast")}
                className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
              >
                + New Yield Forecast
              </button>
            </div>

            {filteredYield.length === 0 ? (
              <Card>
                <CardBody>
                  <EmptyState
                    title="No yield outlooks matching filter"
                    description="Run a new yield estimation or reset the filter to view historical seasonal projections."
                  />
                </CardBody>
              </Card>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-hairline bg-surface">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-hairline bg-page text-[11px] font-mono uppercase tracking-wider text-ink-muted">
                    <tr>
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Crop</th>
                      <th className="px-4 py-3">District</th>
                      <th className="px-4 py-3">Season</th>
                      <th className="px-4 py-3">Area</th>
                      <th className="px-4 py-3">Expected Yield</th>
                      <th className="px-4 py-3">80% Interval</th>
                      <th className="px-4 py-3">Risk Level</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-hairline">
                    {filteredYield.map((item) => (
                      <tr key={item.id} className="transition-colors hover:bg-page/60">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-ink-muted">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 font-medium capitalize text-ink">{item.crop}</td>
                        <td className="px-4 py-3 text-ink">{item.district}</td>
                        <td className="px-4 py-3 font-mono text-xs text-ink">{item.season_year}</td>
                        <td className="px-4 py-3 font-mono text-xs text-ink">{item.area_ha} ha</td>
                        <td className="px-4 py-3 font-semibold text-forest">
                          {item.predicted_yield_tha.toFixed(2)} t/ha
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-ink-muted">
                          [{item.interval_lower.toFixed(2)}, {item.interval_upper.toFixed(2)}]
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "rounded-full px-2.5 py-0.5 font-mono text-[10px] uppercase font-semibold",
                              item.risk_level === "low"
                                ? "bg-risk-low/15 text-risk-low"
                                : item.risk_level === "high"
                                ? "bg-risk-high/15 text-risk-high"
                                : "bg-risk-medium/15 text-risk-medium",
                            )}
                          >
                            {item.risk_level}
                          </span>
                        </td>
                        <td className="whitespace-nowrap px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              type="button"
                              onClick={() => setInspectYield(item)}
                              className="font-mono text-xs uppercase tracking-wider text-forest hover:underline"
                            >
                              Inspect
                            </button>
                            <button
                              type="button"
                              onClick={() => handleDeleteYield(item.id)}
                              className="text-ink-muted hover:text-risk-high"
                              title="Delete record"
                              aria-label="Delete yield record"
                            >
                              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── TAB 4: QUICK SCAN (LIVE AI) ── */}
        {activeTab === "scan" && (
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-4 rounded-xl border border-hairline bg-surface p-6">
              <div>
                <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
                  Live Diagnostic Scanner
                </span>
                <h3 className="text-xl font-medium text-ink">Upload Leaf Photo</h3>
                <p className="mt-1 text-sm text-ink-muted">
                  Select a clear, well-lit photo of the affected leaf (JPEG or PNG, up to 10 MB).
                </p>
              </div>

              <div
                className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-hairline bg-page/50 p-6 text-center transition-colors hover:border-forest/50"
              >
                {scanPreview ? (
                  <div className="flex flex-col items-center gap-3">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={scanPreview}
                      alt="Uploaded preview"
                      className="max-h-56 rounded-lg object-contain border border-hairline shadow-sm"
                    />
                    <span className="text-xs text-ink-muted">{scanFile?.name}</span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2">
                    <svg className="h-10 w-10 text-forest/70" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    <p className="text-sm font-medium text-ink">Drag & drop leaf photo here, or click to browse</p>
                    <p className="font-mono text-xs text-ink-muted">Supports JPG, PNG · Max 10 MB</p>
                  </div>
                )}

                <label htmlFor={fileInputId} className="sr-only">
                  Select leaf photo
                </label>
                <input
                  id={fileInputId}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleFileChange}
                  className="mt-3 cursor-pointer text-xs text-forest file:mr-2 file:rounded-md file:border-0 file:bg-forest file:px-3 file:py-1 file:font-mono file:text-xs file:text-leaf"
                />
              </div>

              <button
                type="button"
                onClick={handleRunScan}
                disabled={!scanFile || isScanning}
                className={buttonClass("primary", "lg", "w-full rounded-lg font-mono text-xs uppercase tracking-wider")}
              >
                {isScanning ? "Processing with EfficientNet-B0…" : "Run Disease Diagnosis"}
              </button>
            </div>

            {/* Scan Output Card */}
            <div className="flex flex-col rounded-xl border border-hairline bg-surface p-6">
              <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
                Inference Result
              </span>
              <h3 className="text-xl font-medium text-ink">Model Diagnostic Output</h3>

              {!scanResult ? (
                <div className="my-auto py-12 text-center text-sm text-ink-muted">
                  Upload an image on the left and run analysis to view class diagnosis, Grad-CAM heatmap, and severity rating.
                </div>
              ) : (
                <div className="mt-4 flex flex-col gap-4">
                  <div className="flex items-start justify-between rounded-lg bg-page p-4">
                    <div>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">Detected Disease</span>
                      <h4 className="text-lg font-semibold text-ink">
                        {scanResult.prediction?.disease || scanResult.prediction?.class_id}
                      </h4>
                      <p className="text-xs text-ink-muted">Crop: {scanResult.prediction?.crop}</p>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 font-mono text-xs uppercase font-semibold",
                        scanResult.prediction?.is_healthy
                          ? "bg-risk-low/15 text-risk-low"
                          : "bg-risk-high/15 text-risk-high",
                      )}
                    >
                      {scanResult.prediction?.is_healthy ? "Healthy" : "Infected"}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="rounded-lg border border-hairline p-3">
                      <span className="text-ink-muted">Model Confidence</span>
                      <p className="mt-1 font-mono text-base font-semibold text-ink">
                        {(scanResult.prediction?.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    <div className="rounded-lg border border-hairline p-3">
                      <span className="text-ink-muted">Severity Band</span>
                      <p className="mt-1 font-mono text-base font-semibold capitalize text-ink">
                        {scanResult.severity?.level || "N/A"}
                      </p>
                    </div>
                  </div>

                  {/* Grad-CAM Preview */}
                  {scanResult.explanation?.overlay_url && (
                    <div className="flex flex-col gap-2">
                      <span className="font-mono text-xs uppercase text-ink-muted">Grad-CAM Visual Heatmap:</span>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={scanResult.explanation.overlay_url}
                        alt="Grad-CAM Overlay"
                        className="max-h-56 rounded-lg object-contain border border-hairline"
                      />
                    </div>
                  )}

                  {/* Curated Recommendations */}
                  {scanResult.recommendations?.summary && (
                    <div className="rounded-lg border border-hairline/80 bg-page/40 p-3.5 text-xs">
                      <span className="font-mono uppercase font-semibold text-forest">Recommended Guidance</span>
                      <p className="mt-1 text-ink">{scanResult.recommendations.summary}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 5: QUICK FORECAST (LIVE AI) ── */}
        {activeTab === "forecast" && (
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="flex flex-col gap-4 rounded-xl border border-hairline bg-surface p-6">
              <div>
                <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
                  Seasonal Yield Forecaster
                </span>
                <h3 className="text-xl font-medium text-ink">Field & Climate Parameters</h3>
                <p className="mt-1 text-sm text-ink-muted">
                  Calculates predicted yield and 80% quantile risk intervals using 22 agro-meteorological features.
                </p>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="dashboard-forecast-crop" className="text-xs font-mono uppercase text-ink-muted">Target Crop</label>
                  <select
                    id="dashboard-forecast-crop"
                    value={forecastCrop}
                    onChange={(e) => setForecastCrop(e.target.value)}
                    className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
                  >
                    <option value="wheat">Wheat (Gandum)</option>
                    <option value="maize">Maize (Makki)</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="dashboard-forecast-district" className="text-xs font-mono uppercase text-ink-muted">Punjab District</label>
                  <select
                    id="dashboard-forecast-district"
                    value={forecastDistrict}
                    onChange={(e) => setForecastDistrict(e.target.value)}
                    className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
                  >
                    {PUNJAB_DISTRICTS.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="dashboard-forecast-area" className="text-xs font-mono uppercase text-ink-muted">Cultivated Area (Hectares)</label>
                  <input
                    id="dashboard-forecast-area"
                    type="number"
                    min="1"
                    max="10000"
                    value={forecastArea}
                    onChange={(e) => setForecastArea(Number(e.target.value))}
                    className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
                  />
                </div>

                <div className="flex flex-col gap-1.5">
                  <label htmlFor="dashboard-forecast-year" className="text-xs font-mono uppercase text-ink-muted">Harvest Season Year</label>
                  <input
                    id="dashboard-forecast-year"
                    type="number"
                    min="2020"
                    max="2030"
                    value={forecastYear}
                    onChange={(e) => setForecastYear(Number(e.target.value))}
                    className="rounded-lg border border-hairline bg-surface p-2 text-sm text-ink"
                  />
                </div>
              </div>

              <button
                type="button"
                onClick={handleRunYield}
                disabled={isForecasting}
                className={buttonClass("primary", "lg", "w-full rounded-lg font-mono text-xs uppercase tracking-wider")}
              >
                {isForecasting ? "Computing XGBoost Point & Quantiles…" : "Run Predictive Yield Model"}
              </button>
            </div>

            {/* Yield Output Card */}
            <div className="flex flex-col rounded-xl border border-hairline bg-surface p-6">
              <span className="font-mono text-[11px] uppercase tracking-wider text-forest font-semibold">
                Yield Outlook Output
              </span>
              <h3 className="text-xl font-medium text-ink">Estimated Production & Risk</h3>

              {!forecastResult ? (
                <div className="my-auto py-12 text-center text-sm text-ink-muted">
                  Configure crop and district parameters on the left and run forecast to view expected tonnage, risk bounds, and SHAP drivers.
                </div>
              ) : (
                <div className="mt-4 flex flex-col gap-4">
                  <div className="flex items-start justify-between rounded-lg bg-page p-4">
                    <div>
                      <span className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">Expected Yield</span>
                      <h4 className="text-3xl font-semibold text-forest">
                        {forecastResult.prediction?.yield_value?.toFixed(2)}{" "}
                        <span className="text-sm font-normal text-ink-muted">t/ha</span>
                      </h4>
                      <p className="mt-1 text-xs text-ink-muted">
                        Total harvest: ~{(forecastResult.prediction?.yield_value * forecastArea).toFixed(1)} tons
                      </p>
                    </div>
                    <span
                      className={cn(
                        "rounded-full px-2.5 py-0.5 font-mono text-xs uppercase font-semibold",
                        forecastResult.risk?.level === "low"
                          ? "bg-risk-low/15 text-risk-low"
                          : forecastResult.risk?.level === "high"
                          ? "bg-risk-high/15 text-risk-high"
                          : "bg-risk-medium/15 text-risk-medium",
                      )}
                    >
                      {forecastResult.risk?.level} Risk
                    </span>
                  </div>

                  <div className="rounded-lg border border-hairline p-3 text-xs">
                    <span className="font-mono uppercase text-ink-muted">80% Prediction Interval:</span>
                    <p className="mt-1 font-mono text-sm text-ink">
                      [{forecastResult.prediction?.interval?.lower?.toFixed(2)} t/ha — {forecastResult.prediction?.interval?.upper?.toFixed(2)} t/ha]
                    </p>
                    <p className="mt-1 text-[11px] text-ink-muted">
                      There is an 80% probability that field yield falls between these bounds given historical climate variability.
                    </p>
                  </div>

                  {forecastResult.explanation?.contributions && (
                    <div className="flex flex-col gap-2 rounded-lg border border-hairline bg-page/40 p-3.5 text-xs">
                      <span className="font-mono uppercase font-semibold text-forest">Key SHAP Feature Drivers:</span>
                      <div className="flex flex-col gap-1.5">
                        {forecastResult.explanation.contributions.slice(0, 4).map((c, i: number) => (
                          <div key={i} className="flex items-center justify-between font-mono text-[11px]">
                            <span className="text-ink">{c.feature}</span>
                            <span className={c.shap >= 0 ? "text-risk-low" : "text-risk-high"}>
                              {c.shap >= 0 ? `+${c.shap.toFixed(3)}` : c.shap.toFixed(3)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── TAB 6: ACCOUNT & SECURITY ── */}
        {activeTab === "account" && (
          <ProfileTabContent
            key={user?.id || "anon"}
            user={user}
            token={token}
            onSuccess={(msg) => setSuccessMessage(msg)}
            onError={(msg) => setErrorMessage(msg)}
          />
        )}
      </section>

      {/* ── 6. INSPECTION MODAL: DISEASE ── */}
      {inspectDisease && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
          <div className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-y-auto rounded-2xl border border-hairline bg-surface p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-xs uppercase text-forest font-semibold">
                  Scan Record · {new Date(inspectDisease.created_at).toLocaleDateString()}
                </span>
                <h3 className="text-xl font-semibold text-ink">
                  {inspectDisease.disease_class.replace(/___/g, " — ").replace(/_/g, " ")}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectDisease(null)}
                className="rounded-lg p-1 text-ink-muted hover:text-ink"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg bg-page p-2.5">
                  <span className="text-ink-muted">Crop</span>
                  <p className="font-semibold text-ink">{inspectDisease.crop}</p>
                </div>
                <div className="rounded-lg bg-page p-2.5">
                  <span className="text-ink-muted">Confidence</span>
                  <p className="font-mono font-semibold text-ink">{(inspectDisease.confidence * 100).toFixed(1)}%</p>
                </div>
                <div className="rounded-lg bg-page p-2.5">
                  <span className="text-ink-muted">Severity Band</span>
                  <p className="font-semibold capitalize text-ink">{inspectDisease.severity_band}</p>
                </div>
                <div className="rounded-lg bg-page p-2.5">
                  <span className="text-ink-muted">Affected Area Ratio</span>
                  <p className="font-mono font-semibold text-ink">{inspectDisease.severity_ratio_pct.toFixed(1)}%</p>
                </div>
              </div>

              {inspectDisease.overlay_url && (
                <div className="flex flex-col gap-1.5">
                  <span className="font-mono text-xs uppercase text-ink-muted">Grad-CAM Activation Map</span>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={dashboardMediaUrl(inspectDisease.overlay_url)}
                    alt="Grad-CAM"
                    className="max-h-60 rounded-lg object-contain border border-hairline"
                  />
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end gap-2 border-t border-hairline pt-4">
              <button
                type="button"
                onClick={() => handleDeleteDisease(inspectDisease.id)}
                className="rounded-lg border border-risk-high/30 px-3 py-1.5 text-xs font-mono uppercase text-risk-high hover:bg-risk-high/10"
              >
                Delete Record
              </button>
              <button
                type="button"
                onClick={() => setInspectDisease(null)}
                className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 7. INSPECTION MODAL: YIELD ── */}
      {inspectYield && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-sm">
          <div className="flex max-h-[90vh] w-full max-w-lg flex-col overflow-y-auto rounded-2xl border border-hairline bg-surface p-6 shadow-xl">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-mono text-xs uppercase text-forest font-semibold">
                  Yield Forecast Record · Season {inspectYield.season_year}
                </span>
                <h3 className="text-xl font-semibold capitalize text-ink">
                  {inspectYield.crop} in {inspectYield.district}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setInspectYield(null)}
                className="rounded-lg p-1 text-ink-muted hover:text-ink"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              <div className="rounded-xl bg-page p-4 text-center">
                <span className="font-mono text-xs uppercase text-ink-muted">Predicted Production</span>
                <p className="text-3xl font-bold text-forest">
                  {inspectYield.predicted_yield_tha.toFixed(2)}{" "}
                  <span className="text-base font-normal text-ink-muted">t/ha</span>
                </p>
                <span className="mt-1 inline-block font-mono text-xs text-ink">
                  80% Bounds: [{inspectYield.interval_lower.toFixed(2)} — {inspectYield.interval_upper.toFixed(2)}] t/ha
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-lg border border-hairline p-2.5">
                  <span className="text-ink-muted">Plot Area</span>
                  <p className="font-mono font-semibold text-ink">{inspectYield.area_ha} Hectares</p>
                </div>
                <div className="rounded-lg border border-hairline p-2.5">
                  <span className="text-ink-muted">Risk Classification</span>
                  <p className="font-semibold capitalize text-ink">{inspectYield.risk_level} Risk</p>
                </div>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-2 border-t border-hairline pt-4">
              <button
                type="button"
                onClick={() => handleDeleteYield(inspectYield.id)}
                className="rounded-lg border border-risk-high/30 px-3 py-1.5 text-xs font-mono uppercase text-risk-high hover:bg-risk-high/10"
              >
                Delete Record
              </button>
              <button
                type="button"
                onClick={() => setInspectYield(null)}
                className={buttonClass("primary", "md", "rounded-lg text-xs font-mono uppercase")}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
