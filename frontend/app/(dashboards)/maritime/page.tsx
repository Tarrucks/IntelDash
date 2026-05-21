"use client";

import { ScatterplotLayer, PathLayer } from "@deck.gl/layers";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  api,
  ApiError,
  type LiveVessels,
  type VesselAnomalies,
  type VesselAnomaly,
  type VesselDetail,
  type VesselTracks,
} from "@/lib/api";
import { usePinToActiveCase } from "@/lib/active-case";
import { useMap } from "@/lib/map-context";

// Cross-source colour map (RGBA). Matches Tailwind's `domain-maritime`
// hue family so the panel chip and the map dot agree visually.
const SOURCE_COLOR: Record<string, [number, number, number, number]> = {
  aishub: [56, 189, 248, 220],
  kaggle: [125, 211, 252, 200],
  barentswatch: [14, 165, 233, 220],
  marinecadastre: [125, 211, 252, 180],
  mock: [148, 163, 184, 180],
};

export default function MaritimePage() {
  const { bbox, setLayer, removeLayer } = useMap();
  const { active: activeCase, pinned, pin, reset: resetPin } = usePinToActiveCase();
  const [data, setData] = useState<LiveVessels | null>(null);
  const [anomalies, setAnomalies] = useState<VesselAnomalies | null>(null);
  const [showAnomalies, setShowAnomalies] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<VesselDetail | null>(null);
  const [replay, setReplay] = useState<VesselTracks | null>(null);

  async function pinToActiveCase() {
    if (!selected || !selected.last_position) return;
    await pin({
      kind: "vessel",
      ref_id: selected.mmsi,
      label: selected.name ?? `MMSI ${selected.mmsi}`,
      extra: {
        lat: selected.last_position.lat,
        lon: selected.last_position.lon,
        vessel_type: selected.vessel_type,
        imo: selected.imo,
      },
    });
  }

  const fetchVessels = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      if (showAnomalies) {
        const r = await api.maritime.anomalies(bbox);
        setAnomalies(r);
        // Mirror the snapshots into ``data`` so the list still renders.
        setData({
          bbox: r.bbox,
          fetched_at: r.fetched_at,
          sources: r.sources,
          vessels: r.vessels,
        });
      } else {
        setAnomalies(null);
        setData(await api.maritime.live(bbox));
      }
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to fetch vessels");
    } finally {
      setBusy(false);
    }
  }, [bbox, showAnomalies]);

  // Initial fetch + refetch when the user pans/zooms or toggles the mode.
  useEffect(() => {
    void fetchVessels();
  }, [fetchVessels]);

  // Quick map from mmsi -> anomaly info for the dot-recolour pass.
  const anomalyByMmsi = useMemo(() => {
    if (!anomalies) return null;
    const m = new Map<string, VesselAnomaly>();
    for (const v of anomalies.vessels) m.set(v.mmsi, v);
    return m;
  }, [anomalies]);

  // Push the vessel layer into the shared map context.
  useEffect(() => {
    if (!data) {
      removeLayer("maritime-vessels");
      return;
    }
    const layer = new ScatterplotLayer({
      id: "maritime-vessels",
      data: data.vessels,
      getPosition: (d) => [d.lon, d.lat],
      // Highlight any vessel currently selected by drawing a slightly
      // larger ring on top via radiusScale; the picking layer handles
      // hover regardless.
      getRadius: (d) => (selected?.mmsi === d.mmsi ? 12 : 7),
      radiusUnits: "pixels",
      // In anomaly mode, paint flagged vessels red and keep normals dimmed,
      // so the eye is drawn to the outliers.
      getFillColor: (d) => {
        if (anomalyByMmsi) {
          const a = anomalyByMmsi.get(d.mmsi);
          if (a?.is_anomaly) return [248, 113, 113, 235];
          return [148, 163, 184, 120];
        }
        return SOURCE_COLOR[d.source] ?? SOURCE_COLOR.mock;
      },
      pickable: true,
      stroked: true,
      lineWidthMinPixels: 1,
      getLineColor: [15, 23, 42, 220],
      // Re-render when anomaly map identity changes.
      updateTriggers: { getFillColor: anomalyByMmsi },
    });
    setLayer({ id: "maritime-vessels", domain: "maritime", layer });
  }, [data, selected, anomalyByMmsi, setLayer, removeLayer]);

  // Replay track layer — only present while one is loaded.
  useEffect(() => {
    if (!replay) {
      removeLayer("maritime-replay");
      return;
    }
    const paths = replay.tracks.features
      .filter(
        (f) =>
          (f.geometry as { type?: string } | undefined)?.type === "LineString" &&
          Array.isArray((f.geometry as { coordinates?: unknown[] }).coordinates),
      )
      .map((f) => ({
        path: (f.geometry as { coordinates: [number, number][] }).coordinates,
      }));
    const layer = new PathLayer({
      id: "maritime-replay",
      data: paths,
      getPath: (d) => d.path,
      getColor: [56, 189, 248, 220],
      getWidth: 3,
      widthUnits: "pixels",
    });
    setLayer({ id: "maritime-replay", domain: "maritime", layer });
  }, [replay, setLayer, removeLayer]);

  async function openVessel(mmsi: string) {
    setSelected(null);
    setReplay(null);
    resetPin();
    try {
      const d = await api.maritime.vessel(mmsi);
      setSelected(d);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Vessel lookup failed");
    }
  }

  async function loadReplay(mmsi: string) {
    try {
      const t = await api.maritime.tracks(mmsi);
      setReplay(t);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Replay failed");
    }
  }

  const counts = useMemo(() => {
    if (!data) return null;
    const bySource = new Map<string, number>();
    for (const v of data.vessels) {
      bySource.set(v.source, (bySource.get(v.source) ?? 0) + 1);
    }
    return bySource;
  }, [data]);

  return (
    <div className="space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <span
            className="inline-block h-2 w-2 rounded-full bg-domain-maritime align-middle"
            aria-hidden
          />
          <h1 className="ml-2 inline align-middle text-lg font-semibold">
            Maritime Domain Awareness
          </h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAnomalies((v) => !v)}
            className={`btn ${showAnomalies ? "border-red-500/60 text-red-300" : ""}`}
            aria-pressed={showAnomalies}
          >
            {showAnomalies ? "Hide anomalies" : "Show anomalies"}
          </button>
          <button onClick={fetchVessels} className="btn" disabled={busy}>
            {busy ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      {anomalies && (
        <div className="surface px-3 py-2 text-xs text-fg-muted">
          <span className="font-mono text-red-300">
            {anomalies.vessels.filter((v) => v.is_anomaly).length}
          </span>{" "}
          flagged of {anomalies.vessels.length} ·{" "}
          <span className="text-fg-subtle">
            isolation-forest trained on {anomalies.model_trained_on} positions
          </span>
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {data && (
        <div className="surface p-3 text-xs">
          <div className="text-fg-muted">
            <span className="font-mono">{data.vessels.length}</span> vessel
            {data.vessels.length === 1 ? "" : "s"} in current view
          </div>
          <div className="mt-1 flex flex-wrap gap-2 text-fg-subtle">
            {counts &&
              Array.from(counts.entries()).map(([src, n]) => (
                <span key={src} className="rounded bg-bg-elevated px-1.5 py-0.5">
                  <span className="font-mono">{n}</span>{" "}
                  <span className="uppercase tracking-wider">{src}</span>
                </span>
              ))}
            <span className="ml-auto">
              sources: {data.sources.join(", ") || "—"}
            </span>
          </div>
        </div>
      )}

      {/* Vessel list */}
      <ul className="surface divide-y divide-border overflow-hidden">
        {data?.vessels.map((v) => (
          <li key={v.mmsi}>
            <button
              onClick={() => openVessel(v.mmsi)}
              className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-bg-elevated ${
                selected?.mmsi === v.mmsi ? "bg-bg-elevated" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-fg">
                  {v.name ?? `MMSI ${v.mmsi}`}
                </div>
                <div className="text-fg-subtle">
                  {v.mmsi} · {v.vessel_type ?? "unknown"}{" "}
                  {v.sog != null ? `· ${v.sog.toFixed(1)} kts` : ""}
                </div>
              </div>
              <span
                className="shrink-0 rounded bg-bg-panel px-1.5 py-0.5 font-mono text-[10px] uppercase text-fg-muted"
                aria-label={`source ${v.source}`}
              >
                {v.source}
              </span>
            </button>
          </li>
        ))}
        {data && data.vessels.length === 0 && (
          <li className="px-3 py-4 text-center text-xs text-fg-subtle">
            No vessels in current view. Pan the map.
          </li>
        )}
      </ul>

      {/* Detail card */}
      {selected && (
        <div className="surface space-y-2 p-3 text-xs">
          <div className="flex items-center justify-between">
            <div className="font-semibold text-fg">
              {selected.name ?? `MMSI ${selected.mmsi}`}
            </div>
            <button
              onClick={() => {
                setSelected(null);
                setReplay(null);
              }}
              className="btn px-2 py-0.5 text-[10px]"
              aria-label="Close detail"
            >
              Close
            </button>
          </div>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-fg-muted">
            <dt>MMSI</dt>
            <dd className="font-mono text-fg">{selected.mmsi}</dd>
            {selected.imo && (
              <>
                <dt>IMO</dt>
                <dd className="font-mono text-fg">{selected.imo}</dd>
              </>
            )}
            {selected.call_sign && (
              <>
                <dt>Call sign</dt>
                <dd className="font-mono text-fg">{selected.call_sign}</dd>
              </>
            )}
            {selected.vessel_type && (
              <>
                <dt>Type</dt>
                <dd className="text-fg">{selected.vessel_type}</dd>
              </>
            )}
            {selected.length_m && (
              <>
                <dt>Dimensions</dt>
                <dd className="text-fg">
                  {selected.length_m}m × {selected.width_m ?? "?"}m
                </dd>
              </>
            )}
            <dt>History</dt>
            <dd className="text-fg">{selected.position_history_count} positions</dd>
          </dl>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => loadReplay(selected.mmsi)}
              className="btn btn-primary"
              disabled={!!replay}
            >
              {replay ? "Replay loaded" : "Replay last 24h"}
            </button>
            {replay && (
              <button onClick={() => setReplay(null)} className="btn">
                Clear track
              </button>
            )}
            {activeCase && (
              <button onClick={pinToActiveCase} className="btn" disabled={pinned}>
                {pinned ? `Pinned to "${activeCase.title}"` : `Pin to "${activeCase.title}"`}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
