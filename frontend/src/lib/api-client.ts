/**
 * Typed client for the AgriSense API (ARCH §7.2, §13).
 *
 * Every failure is normalised to `ApiError` carrying the stable `code` from the
 * backend envelope, so UI messages are driven by codes rather than prose
 * (FR-UI-005). Request-id is preserved for support/debugging.
 */

import { env } from "./env";

const DEFAULT_TIMEOUT_MS = 20_000;

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
}

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details: Record<string, unknown>;
  readonly requestId?: string;

  constructor(options: {
    code: string;
    message: string;
    status: number;
    details?: Record<string, unknown>;
    requestId?: string;
  }) {
    super(options.message);
    this.name = "ApiError";
    this.code = options.code;
    this.status = options.status;
    this.details = options.details ?? {};
    this.requestId = options.requestId;
  }

  /** True when retrying the same request could plausibly succeed. */
  get isRetryable(): boolean {
    return (
      this.code === "NETWORK_ERROR" ||
      this.code === "TIMEOUT" ||
      this.status === 429 ||
      this.status >= 500
    );
  }
}

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  env: string;
  uptime_s: number;
}

export type DependencyState = "ok" | "not_configured" | "not_checked" | "error";

export interface ReadinessResponse {
  status: "ready" | "degraded" | "not_ready";
  version: string;
  dependencies: { name: string; status: DependencyState; detail: string | null }[];
}

export interface ModelInfo {
  pipeline: "disease" | "yield";
  name: string;
  version: string;
  metrics: Record<string, unknown>;
}

export interface ModelsResponse {
  registry: "configured" | "unconfigured";
  models: ModelInfo[];
}

export interface WeatherResponse {
  provider: string;
  lat: number;
  lon: number;
  start_date: string;
  end_date: string;
  total_rain_mm: number;
  rainy_days_count: number;
  mean_temp_c: number;
  max_temp_c: number;
  min_temp_c: number;
  gdd_c: number;
  heat_stress_days: number;
  water_balance_mm: number;
  daily_records_count: number;
}

export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  phone_number?: string | null;
  role: "farmer" | "agronomist" | "researcher";
  preferred_language: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface DiseaseHistoryItem {
  id: string;
  image_url: string;
  overlay_url: string;
  crop: string;
  disease_class: string;
  confidence: number;
  is_healthy: boolean;
  severity_band: string;
  severity_ratio_pct: number;
  created_at: string;
}

export interface YieldHistoryItem {
  id: string;
  crop: string;
  district: string;
  season_year: number;
  area_ha: number;
  predicted_yield_tha: number;
  interval_lower: number;
  interval_upper: number;
  risk_level: string;
  created_at: string;
}

export interface HistoryStats {
  total_disease_scans: number;
  healthy_count: number;
  diseased_count: number;
  total_yield_forecasts: number;
  avg_predicted_yield_tha?: number | null;
}

export interface DiseasePredictResponse {
  prediction: {
    class_id: string;
    crop: string;
    disease: string;
    is_healthy: boolean;
    confidence: number;
    top_k: Array<{ class_id: string; confidence: number }>;
  };
  severity: {
    level: "low" | "moderate" | "severe" | "unknown";
    ratio: number;
    method: string;
    note: string;
  };
  explanation: {
    method: string;
    overlay_url: string;
    original_url: string;
    quality_warnings?: string[];
    leaf_focus_fraction?: number | null;
  };
  recommendations: {
    summary: string;
    actions: Array<{ type: string; text: string }>;
    prevention: string[];
    sources: Array<{ title: string; url: string }>;
    disclaimer: string;
  };
  prediction_id: string;
  status: "ok" | "uncertain" | "not_a_leaf";
  model: { name: string; version: string };
  latency_ms: number;
}

export interface DiseaseClassItem {
  class_id: string;
  crop: string;
  disease_name: string;
  is_healthy: boolean;
}

export interface DiseaseClassesResponse {
  total_classes: number;
  classes: DiseaseClassItem[];
}

export interface YieldPredictResponse {
  prediction_id: string;
  status: "ok" | "degraded" | "out_of_bounds";
  prediction: {
    yield_value: number;
    unit: string;
    interval: {
      lower: number;
      upper: number;
      level: number;
    };
  };
  risk: {
    level: "low" | "medium" | "high";
    baseline_yield: number;
    ratio_to_baseline: number;
    rationale: string;
    advisories: string[];
  };
  explanation: {
    method: string;
    base_value: number;
    contributions: Array<{
      feature: string;
      value: number;
      shap: number;
      direction: "increase" | "decrease" | "neutral";
      text: string;
    }>;
  };
  weather_summary: {
    source: string;
    temp_mean: number;
    rain_total: number;
    heat_stress_days: number;
    water_balance: number;
  };
  model: { name: string; version: string };
  latency_ms: number;
}

export interface YieldDistrictOption {
  name: string;
  lat: number;
  lon: number;
  zone: string;
  is_barani: boolean;
  supported_crops: string[];
}

export interface YieldOptionsResponse {
  districts: YieldDistrictOption[];
  supported_crops: string[];
  default_year: number;
  target_unit: string;
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  const url = `${env.apiBaseUrl}/api/v1${path}`;
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers,
      signal: init.signal ?? AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
    });
  } catch (cause) {
    const timedOut = cause instanceof DOMException && cause.name === "TimeoutError";
    throw new ApiError({
      code: timedOut ? "TIMEOUT" : "NETWORK_ERROR",
      message: timedOut
        ? "The server took too long to respond."
        : "Could not reach the server. Check your connection and try again.",
      status: 0,
    });
  }

  if (!response.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await response.json()) as ApiErrorBody;
    } catch {
      // Non-JSON error body (proxy, host timeout page, …).
    }
    throw new ApiError({
      code: body?.error?.code ?? "INTERNAL_ERROR",
      message: body?.error?.message ?? `Request failed (HTTP ${response.status}).`,
      status: response.status,
      details: body?.error?.details,
      requestId: body?.error?.request_id ?? response.headers.get("X-Request-ID") ?? undefined,
    });
  }

  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  readiness: () => request<ReadinessResponse>("/health/ready"),

  models: () => request<ModelsResponse>("/models"),

  // --- Auth & User ---
  register: (payload: {
    email: string;
    password: string;
    full_name?: string;
    phone_number?: string;
    role?: string;
    preferred_language?: string;
  }) => request<AuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),

  login: (payload: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),

  getMe: (token: string) => request<User>("/auth/me", {}, token),

  updateMe: (
    payload: { full_name?: string; phone_number?: string; preferred_language?: string },
    token: string,
  ) => request<User>("/auth/me", { method: "PUT", body: JSON.stringify(payload) }, token),

  changePassword: (
    payload: { old_password: string; new_password: string },
    token: string,
  ) => request<{ status: string; message: string }>("/auth/change-password", { method: "POST", body: JSON.stringify(payload) }, token),

  // --- History & Stats ---
  getDiseaseHistory: (token: string, skip: number = 0, limit: number = 50) =>
    request<DiseaseHistoryItem[]>(`/auth/history/disease?skip=${skip}&limit=${limit}`, {}, token),

  deleteDiseaseHistory: (id: string, token: string) =>
    request<{ status: string; message: string }>(`/auth/history/disease/${id}`, { method: "DELETE" }, token),

  getYieldHistory: (token: string, skip: number = 0, limit: number = 50) =>
    request<YieldHistoryItem[]>(`/auth/history/yield?skip=${skip}&limit=${limit}`, {}, token),

  deleteYieldHistory: (id: string, token: string) =>
    request<{ status: string; message: string }>(`/auth/history/yield/${id}`, { method: "DELETE" }, token),

  getHistoryStats: (token: string) =>
    request<HistoryStats>("/auth/history/stats", {}, token),

  // --- Predictions ---
  diseaseClasses: () => request<DiseaseClassesResponse>("/disease/classes"),

  predictDisease: (form: FormData, token?: string) =>
    request<DiseasePredictResponse>("/disease/predict", { method: "POST", body: form }, token),

  predictYield: (payload: unknown, token?: string) =>
    request<YieldPredictResponse>("/yield/predict", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token),

  yieldOptions: () => request<YieldOptionsResponse>("/yield/options"),

  weather: (params: {
    lat: number;
    lon: number;
    start_date: string;
    end_date: string;
    crop: string;
  }) => request<WeatherResponse>(`/weather?${new URLSearchParams({
    lat: String(params.lat),
    lon: String(params.lon),
    start_date: params.start_date,
    end_date: params.end_date,
    crop: params.crop,
  })}`),
} as const;
