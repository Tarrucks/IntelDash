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

// -------- Cyber ------------------------------------------------------------

export const cyberBannerSchema = z.object({
  port: z.number(),
  transport: z.string(),
  product: z.string().nullable().optional(),
  version: z.string().nullable().optional(),
  banner: z.string().nullable().optional(),
  timestamp: z.string().nullable().optional(),
});

export const cyberHostSchema = z.object({
  ip: z.string(),
  hostnames: z.array(z.string()),
  ports: z.array(z.number()),
  country_code: z.string().nullable().optional(),
  city: z.string().nullable().optional(),
  org: z.string().nullable().optional(),
  isp: z.string().nullable().optional(),
  asn: z.string().nullable().optional(),
  latitude: z.number().nullable().optional(),
  longitude: z.number().nullable().optional(),
  last_update: z.string().nullable().optional(),
  banners: z.array(cyberBannerSchema),
  source: z.string(),
});
export type CyberHost = z.infer<typeof cyberHostSchema>;

export const cyberSearchMatchSchema = z.object({
  ip: z.string(),
  port: z.number(),
  org: z.string().nullable().optional(),
  product: z.string().nullable().optional(),
  location: z.record(z.string(), z.unknown()).nullable().optional(),
  timestamp: z.string().nullable().optional(),
});

export const cyberSearchSchema = z.object({
  total: z.number(),
  query: z.string(),
  sources: z.array(z.string()),
  matches: z.array(cyberSearchMatchSchema),
});
export type CyberSearch = z.infer<typeof cyberSearchSchema>;

// -------- Aviation ---------------------------------------------------------

export const flightSnapshotSchema = z.object({
  fr24_id: z.string(),
  hex: z.string(),
  callsign: z.string().nullable().optional(),
  lat: z.number(),
  lon: z.number(),
  track: z.number().nullable().optional(),
  alt: z.number().nullable().optional(),
  gspeed: z.number().nullable().optional(),
  timestamp: z.string(),
  reg: z.string().nullable().optional(),
  type: z.string().nullable().optional(),
  flight: z.string().nullable().optional(),
  orig_iata: z.string().nullable().optional(),
  dest_iata: z.string().nullable().optional(),
  source: z.string(),
});
export type FlightSnapshot = z.infer<typeof flightSnapshotSchema>;

export const liveFlightsSchema = z.object({
  bbox: z
    .object({
      latmin: z.number(),
      latmax: z.number(),
      lonmin: z.number(),
      lonmax: z.number(),
    })
    .nullable()
    .optional(),
  fetched_at: z.string(),
  sources: z.array(z.string()),
  flights: z.array(flightSnapshotSchema),
});
export type LiveFlights = z.infer<typeof liveFlightsSchema>;

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

  cyber: {
    host: (ip: string) => request("GET", `/cyber/hosts/${ip}`, undefined, cyberHostSchema),
    search: (q: string, limit = 10) => {
      const qs = new URLSearchParams({ q, limit: String(limit) }).toString();
      return request("GET", `/cyber/search?${qs}`, undefined, cyberSearchSchema);
    },
  },

  aviation: {
    live: (
      bbox?: { latmin: number; latmax: number; lonmin: number; lonmax: number },
      limit?: number,
    ) => {
      const params = new URLSearchParams();
      if (bbox) {
        params.set("latmin", String(bbox.latmin));
        params.set("latmax", String(bbox.latmax));
        params.set("lonmin", String(bbox.lonmin));
        params.set("lonmax", String(bbox.lonmax));
      }
      if (limit) params.set("limit", String(limit));
      const qs = params.toString();
      return request("GET", `/aviation/live${qs ? "?" + qs : ""}`, undefined, liveFlightsSchema);
    },
    flight: (hex: string) =>
      request("GET", `/aviation/flights/${hex}`, undefined, flightSnapshotSchema),
  },

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
