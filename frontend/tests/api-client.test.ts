import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api-client";

describe("typed API client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("adds the bearer token and parses successful responses", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () =>
      new Response(JSON.stringify({ status: "ok", service: "api" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(api.health()).resolves.toMatchObject({ status: "ok" });
    await expect(api.getMe("test-token")).resolves.toMatchObject({ status: "ok" });

    const [, init] = fetchMock.mock.calls[1] ?? [];
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer test-token");
  });

  it("normalizes backend error envelopes and preserves retry semantics", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        error: {
          code: "MODEL_TIMEOUT",
          message: "The model timed out.",
          request_id: "req-123",
        },
      }), {
        status: 504,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(api.models()).rejects.toMatchObject({
      code: "MODEL_TIMEOUT",
      status: 504,
      requestId: "req-123",
      isRetryable: true,
    });
  });

  it("encodes weather query parameters", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ provider: "test" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await api.weather({
      lat: 31.52,
      lon: 74.35,
      start_date: "2025-01-01",
      end_date: "2025-12-31",
      crop: "wheat",
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "crop=wheat",
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("lat=31.52");
  });
});
