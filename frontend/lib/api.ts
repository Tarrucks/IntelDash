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

// -------- Maritime ---------------------------------------------------------

export const vesselSnapshotSchema = z.object({
  mmsi: z.string(),
  name: z.string().nullable().optional(),
  imo: z.string().nullable().optional(),
  call_sign: z.string().nullable().optional(),
  vessel_type: z.string().nullable().optional(),
  time: z.string(),
  lat: z.number(),
  lon: z.number(),
  sog: z.number().nullable().optional(),
  cog: z.number().nullable().optional(),
  heading: z.number().nullable().optional(),
  nav_status: z.string().nullable().optional(),
  source: z.string(),
});
export type VesselSnapshot = z.infer<typeof vesselSnapshotSchema>;

export const liveVesselsSchema = z.object({
  bbox: z.object({
    latmin: z.number(),
    latmax: z.number(),
    lonmin: z.number(),
    lonmax: z.number(),
  }),
  fetched_at: z.string(),
  sources: z.array(z.string()),
  vessels: z.array(vesselSnapshotSchema),
});
export type LiveVessels = z.infer<typeof liveVesselsSchema>;

export const vesselDetailSchema = z.object({
  mmsi: z.string(),
  name: z.string().nullable().optional(),
  imo: z.string().nullable().optional(),
  call_sign: z.string().nullable().optional(),
  vessel_type: z.string().nullable().optional(),
  length_m: z.number().nullable().optional(),
  width_m: z.number().nullable().optional(),
  flag: z.string().nullable().optional(),
  last_position: vesselSnapshotSchema.nullable().optional(),
  position_history_count: z.number(),
});
export type VesselDetail = z.infer<typeof vesselDetailSchema>;

// GeoJSON FeatureCollection of LineStrings; loosely typed.
export const featureCollectionSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(z.record(z.string(), z.unknown())),
});

export const vesselTracksSchema = z.object({
  mmsi: z.string(),
  source: z.string(),
  tracks: featureCollectionSchema,
});
export type VesselTracks = z.infer<typeof vesselTracksSchema>;

// -------- Calls -------------------------------------------------------------

export const api = {
  health: () => request("GET", "/health", undefined, healthSchema),

  register: (email: string, password: string) =>
    request("POST", "/auth/register", { email, password }, userSchema),

  login: (email: string, password: string) =>
    request("POST", "/auth/login", { email, password }, tokenSchema),

  me: () => request("GET", "/auth/me", undefined, userSchema),

  maritime: {
    live: (bbox: { latmin: number; latmax: number; lonmin: number; lonmax: number }) => {
      const q = new URLSearchParams(
        Object.fromEntries(Object.entries(bbox).map(([k, v]) => [k, String(v)])),
      );
      return request("GET", `/maritime/live?${q.toString()}`, undefined, liveVesselsSchema);
    },
    vessel: (mmsi: string) =>
      request("GET", `/maritime/vessels/${mmsi}`, undefined, vesselDetailSchema),
    tracks: (mmsi: string) =>
      request("GET", `/maritime/vessels/${mmsi}/tracks`, undefined, vesselTracksSchema),
  },
};
