/**
 * Runtime-validated environment. Fails loudly at startup instead of producing
 * "undefined/api/v1/..." request URLs in the browser.
 */

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function parseBaseUrl(value: string | undefined): string {
  const candidate = (value ?? DEFAULT_API_BASE_URL).trim().replace(/\/+$/, "");
  try {
    // Validates the shape without relying on a specific zod string method.
    new URL(candidate);
  } catch {
    throw new Error(
      `NEXT_PUBLIC_API_BASE_URL is not a valid URL: "${candidate}". ` +
        `Set it in frontend/.env.local (see .env.local.example).`,
    );
  }
  return candidate;
}

export const env = {
  apiBaseUrl: parseBaseUrl(process.env.NEXT_PUBLIC_API_BASE_URL),
} as const;
