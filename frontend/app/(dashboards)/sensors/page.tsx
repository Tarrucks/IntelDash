"use client";

import { useEffect, useState } from "react";

import { api, ApiError, type WokwiProject } from "@/lib/api";

export default function SensorSimPage() {
  const [projects, setProjects] = useState<WokwiProject[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sensors
      .projects()
      .then((p) => {
        setProjects(p);
        setSelectedId(p[0]?.id ?? null);
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Failed to load Wokwi projects"),
      );
  }, []);

  const selected = projects.find((p) => p.id === selectedId);

  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-case align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Sensor Sim</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Embedded{" "}
          <a
            href="https://wokwi.com"
            target="_blank"
            rel="noopener noreferrer"
            className="underline hover:text-fg"
          >
            Wokwi
          </a>{" "}
          projects for prototyping sensors that feed Aperture (GPS, AIS receivers, etc.).
        </p>
      </header>

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      <div className="surface space-y-2 p-3">
        <label className="label" htmlFor="wokwi-pick">
          Project
        </label>
        <select
          id="wokwi-pick"
          value={selectedId ?? ""}
          onChange={(e) => setSelectedId(e.target.value)}
          className="input"
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
      </div>

      {selected && (
        <div className="surface space-y-2 p-3 text-xs">
          <div className="font-semibold text-fg">{selected.title}</div>
          <p className="text-fg-muted">{selected.description}</p>
          <a
            href={selected.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-fg-subtle underline hover:text-fg"
          >
            Open on wokwi.com →
          </a>
          {selected.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 pt-1">
              {selected.tags.map((t) => (
                <span
                  key={t}
                  className="rounded bg-bg-elevated px-1.5 py-0.5 text-[10px] uppercase text-fg-muted"
                >
                  {t}
                </span>
              ))}
            </div>
          )}

          {/* The iframe is allow-listed for scripts so the simulator boots,
              but kept sandboxed otherwise — Wokwi runs the user's MCU code
              inside its own page. */}
          <div className="mt-2 overflow-hidden rounded border border-border bg-bg">
            <iframe
              key={selected.id}
              src={selected.url}
              title={`Wokwi: ${selected.title}`}
              className="h-[480px] w-full"
              sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
              loading="lazy"
            />
          </div>
        </div>
      )}
    </div>
  );
}
