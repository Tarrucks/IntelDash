"use client";

import { ScatterplotLayer } from "@deck.gl/layers";
import { useEffect, useState } from "react";

import { api, ApiError, type CyberHost, type CyberSearch } from "@/lib/api";
import { useMap } from "@/lib/map-context";

const CYBER_RGBA: [number, number, number, number] = [192, 132, 252, 230];

export default function CyberPage() {
  const { setLayer, removeLayer } = useMap();
  const [ip, setIp] = useState("");
  const [host, setHost] = useState<CyberHost | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CyberSearch | null>(null);
  const [busy, setBusy] = useState<"host" | "search" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("host");
    try {
      const h = await api.cyber.host(ip.trim());
      setHost(h);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Host lookup failed");
    } finally {
      setBusy(null);
    }
  }

  async function runSearch(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("search");
    try {
      const r = await api.cyber.search(query.trim(), 20);
      setResults(r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Search failed");
    } finally {
      setBusy(null);
    }
  }

  // Plot the looked-up host on the map if we have geo.
  useEffect(() => {
    if (!host || host.latitude == null || host.longitude == null) {
      removeLayer("cyber-host");
      return;
    }
    const layer = new ScatterplotLayer({
      id: "cyber-host",
      data: [{ lon: host.longitude, lat: host.latitude, ip: host.ip }],
      getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat],
      getRadius: 10,
      radiusUnits: "pixels",
      getFillColor: CYBER_RGBA,
      stroked: true,
      lineWidthMinPixels: 2,
      getLineColor: [15, 23, 42, 230],
      pickable: true,
    });
    setLayer({ id: "cyber-host", domain: "cyber", layer });
  }, [host, setLayer, removeLayer]);

  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-cyber align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Cyber Surface</h1>
      </header>

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {/* Host lookup */}
      <form onSubmit={lookup} className="surface space-y-2 p-3">
        <label className="label" htmlFor="cyber-ip">
          Host lookup
        </label>
        <div className="flex gap-2">
          <input
            id="cyber-ip"
            placeholder="203.0.113.10"
            value={ip}
            onChange={(e) => setIp(e.target.value)}
            className="input flex-1"
            required
          />
          <button type="submit" className="btn btn-primary" disabled={busy === "host"}>
            {busy === "host" ? "…" : "Lookup"}
          </button>
        </div>
      </form>

      {host && (
        <div className="surface space-y-2 p-3 text-xs">
          <div className="flex items-center justify-between">
            <div className="font-mono text-fg">{host.ip}</div>
            <span className="rounded bg-bg-panel px-1.5 py-0.5 font-mono text-[10px] uppercase text-fg-muted">
              {host.source}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-fg-muted">
            {host.hostnames.length > 0 && (
              <>
                <dt>Hostnames</dt>
                <dd className="truncate text-fg">{host.hostnames.join(", ")}</dd>
              </>
            )}
            {host.org && (
              <>
                <dt>Org</dt>
                <dd className="text-fg">{host.org}</dd>
              </>
            )}
            {host.asn && (
              <>
                <dt>ASN</dt>
                <dd className="font-mono text-fg">{host.asn}</dd>
              </>
            )}
            {host.country_code && (
              <>
                <dt>Location</dt>
                <dd className="text-fg">
                  {host.city ? `${host.city}, ` : ""}
                  {host.country_code}
                </dd>
              </>
            )}
            <dt>Open ports</dt>
            <dd className="font-mono text-fg">{host.ports.join(", ") || "—"}</dd>
          </dl>

          {host.banners.length > 0 && (
            <div className="mt-2">
              <div className="mb-1 text-[10px] uppercase tracking-wider text-fg-subtle">
                Banners
              </div>
              <ul className="space-y-1">
                {host.banners.map((b, idx) => (
                  <li
                    key={`${b.port}-${idx}`}
                    className="rounded border border-border bg-bg-elevated p-2 font-mono text-[10px] text-fg-muted"
                  >
                    <div className="mb-1 text-fg">
                      :{b.port}/{b.transport} · {b.product ?? "?"}
                      {b.version ? ` ${b.version}` : ""}
                    </div>
                    <div className="truncate">{b.banner ?? ""}</div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Search */}
      <form onSubmit={runSearch} className="surface space-y-2 p-3">
        <label className="label" htmlFor="cyber-q">
          Host search
        </label>
        <div className="flex gap-2">
          <input
            id="cyber-q"
            placeholder='product:"nginx" country:"US"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="input flex-1"
            required
          />
          <button type="submit" className="btn btn-primary" disabled={busy === "search"}>
            {busy === "search" ? "…" : "Search"}
          </button>
        </div>
      </form>

      {results && (
        <div className="surface text-xs">
          <div className="border-b border-border p-3 text-fg-muted">
            <span className="font-mono text-fg">{results.total}</span> matches for{" "}
            <span className="font-mono text-fg">{results.query}</span>
          </div>
          <ul className="divide-y divide-border">
            {results.matches.map((m, idx) => (
              <li
                key={`${m.ip}-${m.port}-${idx}`}
                className="flex items-center justify-between gap-2 px-3 py-2"
              >
                <button
                  onClick={() => {
                    setIp(m.ip);
                    void api.cyber.host(m.ip).then(setHost).catch(() => undefined);
                  }}
                  className="truncate text-left font-mono text-fg hover:underline"
                >
                  {m.ip}:{m.port}
                </button>
                <span className="text-fg-subtle">
                  {m.product ?? ""} {m.org ? `· ${m.org}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
