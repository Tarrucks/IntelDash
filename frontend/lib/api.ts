/**
 * Typed Aperture API client.
 *
 * One thin wrapper around `fetch`. Token storage lives in `auth.ts`; this
 * file only knows how to call the backend with an optional bearer token.
 *
 * Schemas mirror the Pydantic models in `backend/app/schemas/`. Keep
 * them in sync by hand for v1 — a codegen pipeline is out of scope.
 */

import { z } from "zod";

import { readToken } from "./auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  schema?: z.ZodType<T>,
): Promise<T> {
  const token = readToken();
  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body == null ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  let parsed: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = text;
    }
  }

  if (!res.ok) {
    const message =
      (parsed as { detail?: string } | null)?.detail ?? `HTTP ${res.status} ${res.statusText}`;
    throw new ApiError(typeof message === "string" ? message : JSON.stringify(message), res.status, parsed);
  }

  if (schema) {
    return schema.parse(parsed);
  }
  return parsed as T;
}

// -------- Schemas (mirror backend pydantic models) --------------------------

export const userSchema = z.object({
  id: z.number(),
  email: z.string(),
  role: z.enum(["viewer", "analyst", "admin"]),
  is_active: z.boolean(),
});
export type User = z.infer<typeof userSchema>;

export const tokenSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  role: z.enum(["viewer", "analyst", "admin"]),
});
export type TokenResponse = z.infer<typeof tokenSchema>;

export const healthSchema = z.object({
  status: z.string(),
  checks: z.record(z.string(), z.string()),
});
export type Health = z.infer<typeof healthSchema>;

// -------- Calls -------------------------------------------------------------

export const api = {
  health: () => request("GET", "/health", undefined, healthSchema),

  register: (email: string, password: string) =>
    request("POST", "/auth/register", { email, password }, userSchema),

  login: (email: string, password: string) =>
    request("POST", "/auth/login", { email, password }, tokenSchema),

  me: () => request("GET", "/auth/me", undefined, userSchema),
};
