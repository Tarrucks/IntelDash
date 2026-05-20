"use client";

import { ScatterplotLayer } from "@deck.gl/layers";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type FlightSnapshot, type LiveFlights } from "@/lib/api";
import { useMap } from "@/lib/map-context";

const AVIATION_RGBA: [number, number, number, number] = [251, 191, 36, 230];

export default function AviationPage() {
  const { bbox, setLayer, removeLayer } = useMap();
  const [data, setData] = useState<LiveFlights | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<FlightSnapshot | null>(null);

  const fetchFlights = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.aviation.live(bbox, 50);
      setData(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to fetch flights");
    } finally {
      setBusy(false);
    }
  }, [bbox]);

  useEffect(() => {
    void fetchFlights();
  }, [fetchFlights]);

  // Aircraft layer — small icon-style triangle. ScatterplotLayer is
  // sufficient for the v1 demo; an IconLayer with a rotating chevron
  // can replace this once we mint an SVG sprite.
  useEffect(() => {
    if (!data) {
      removeLayer("aviation-flights");
      return;
    }
    const layer = new ScatterplotLayer({
      id: "aviation-flights",
      data: data.flights,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => (selected?.hex === d.hex ? 12 : 7),
      radiusUnits: "pixels",
      getFillColor: AVIATION_RGBA,
      pickable: true,
      stroked: true,
      getLineColor: [15, 23, 42, 220],
      lineWidthMinPixels: 1,
    });
    setLayer({ id: "aviation-flights", domain: "aviation", layer });
  }, [data, selected, setLayer, removeLayer]);

  async function openFlight(hex: string) {
    try {
      const f = await api.aviation.flight(hex);
      setSelected(f);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Flight lookup failed");
    }
  }

  return (
    <div className="space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <span
            className="inline-block h-2 w-2 rounded-full bg-domain-aviation align-middle"
            aria-hidden
          />
          <h1 className="ml-2 inline align-middle text-lg font-semibold">Aviation Tracking</h1>
        </div>
        <button onClick={fetchFlights} className="btn" disabled={busy}>
          {busy ? "Refreshing…" : "Refresh"}
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {data && (
        <div className="surface p-3 text-xs">
          <span className="font-mono">{data.flights.length}</span> aircraft tracked ·{" "}
          <span className="text-fg-subtle">sources: {data.sources.join(", ")}</span>
        </div>
      )}

      <ul className="surface divide-y divide-border overflow-hidden">
        {data?.flights.map((f) => (
          <li key={f.fr24_id}>
            <button
              onClick={() => openFlight(f.hex)}
              className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-bg-elevated ${
                selected?.hex === f.hex ? "bg-bg-elevated" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-fg">
                  {f.callsign ?? f.flight ?? f.hex}
                </div>
                <div className="text-fg-subtle">
                  {f.type ?? "?"} · {f.reg ?? "—"}
                  {f.orig_iata && f.dest_iata ? ` · ${f.orig_iata}→${f.dest_iata}` : ""}
                </div>
              </div>
              <div className="shrink-0 text-right">
                <div className="font-mono text-fg">
                  {f.alt != null ? `${f.alt.toLocaleString()} ft` : "—"}
                </div>
                <div className="text-fg-subtle">
                  {f.gspeed != null ? `${f.gspeed} kts` : ""}
                </div>
              </div>
            </button>
          </li>
        ))}
        {data && data.flights.length === 0 && (
          <li className="px-3 py-4 text-center text-xs text-fg-subtle">
            No aircraft in current view. Pan the map.
          </li>
        )}
      </ul>

      {selected && (
        <div className="surface space-y-2 p-3 text-xs">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-fg">
              {selected.callsign ?? selected.flight ?? selected.hex}
            </div>
            <button
              onClick={() => setSelected(null)}
              className="btn px-2 py-0.5 text-[10px]"
              aria-label="Close detail"
            >
              Close
            </button>
          </div>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-fg-muted">
            <dt>Hex</dt>
            <dd className="font-mono text-fg">{selected.hex}</dd>
            <dt>Type</dt>
            <dd className="text-fg">{selected.type ?? "—"}</dd>
            <dt>Registration</dt>
            <dd className="font-mono text-fg">{selected.reg ?? "—"}</dd>
            {selected.orig_iata && selected.dest_iata && (
              <>
                <dt>Route</dt>
                <dd className="text-fg">
                  {selected.orig_iata} → {selected.dest_iata}
                </dd>
              </>
            )}
            <dt>Altitude</dt>
            <dd className="text-fg">
              {selected.alt != null ? `${selected.alt.toLocaleString()} ft` : "—"}
            </dd>
            <dt>Ground speed</dt>
            <dd className="text-fg">
              {selected.gspeed != null ? `${selected.gspeed} kts` : "—"}
            </dd>
            <dt>Position</dt>
            <dd className="font-mono text-fg">
              {selected.lat.toFixed(3)}, {selected.lon.toFixed(3)}
            </dd>
          </dl>
        </div>
      )}
    </div>
  );
}
