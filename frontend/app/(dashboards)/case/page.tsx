"use client";

import { ScatterplotLayer } from "@deck.gl/layers";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  api,
  ApiError,
  type CaseDetail,
  type CasePublic,
} from "@/lib/api";
import { setActiveCase } from "@/lib/active-case";
import { useMap } from "@/lib/map-context";

const KIND_COLOR: Record<string, [number, number, number, number]> = {
  vessel: [56, 189, 248, 230],
  aircraft: [251, 191, 36, 230],
  host: [192, 132, 252, 230],
  url: [16, 185, 129, 200],
  domain: [16, 185, 129, 200],
};

const STATUS_COLOR: Record<string, string> = {
  open: "text-emerald-400",
  closed: "text-fg-muted",
  archived: "text-fg-subtle",
};

export default function CaseFilePage() {
  const { setLayer, removeLayer } = useMap();
  const [cases, setCases] = useState<CasePublic[]>([]);
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);

  const refreshList = useCallback(async () => {
    try {
      setCases(await api.cases.list());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load cases");
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  async function openCase(id: string) {
    try {
      const d = await api.cases.get(id);
      setSelected(d);
      setActiveCase({ id: d.id, title: d.title });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to load case");
    }
  }

  // Render pinned entities on the map if their extra carries geo.
  const mapDots = useMemo(() => {
    if (!selected) return [];
    type Dot = { kind: string; lat: number; lon: number; label: string };
    const out: Dot[] = [];
    for (const p of selected.pins) {
      const extra = (p.entity.extra ?? {}) as Record<string, unknown>;
      const lat = Number(extra.lat ?? extra.latitude);
      const lon = Number(extra.lon ?? extra.longitude);
      if (Number.isFinite(lat) && Number.isFinite(lon)) {
        out.push({ kind: p.entity.kind, lat, lon, label: p.entity.label });
      }
    }
    return out;
  }, [selected]);

  useEffect(() => {
    if (mapDots.length === 0) {
      removeLayer("case-pins");
      return;
    }
    const layer = new ScatterplotLayer({
      id: "case-pins",
      data: mapDots,
      getPosition: (d: { lon: number; lat: number }) => [d.lon, d.lat],
      getRadius: 9,
      radiusUnits: "pixels",
      getFillColor: (d: { kind: string }) =>
        KIND_COLOR[d.kind] ?? [226, 232, 240, 220],
      stroked: true,
      lineWidthMinPixels: 2,
      getLineColor: [15, 23, 42, 230],
      pickable: true,
    });
    setLayer({ id: "case-pins", domain: "case", layer });
  }, [mapDots, setLayer, removeLayer]);

  async function unpin(pinId: number) {
    if (!selected) return;
    try {
      await api.cases.unpin(selected.id, pinId);
      await openCase(selected.id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Unpin failed");
    }
  }

  async function updateStatus(status: "open" | "closed" | "archived") {
    if (!selected) return;
    try {
      await api.cases.update(selected.id, { status });
      await openCase(selected.id);
      await refreshList();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Update failed");
    }
  }

  return (
    <div className="space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <span
            className="inline-block h-2 w-2 rounded-full bg-domain-case align-middle"
            aria-hidden
          />
          <h1 className="ml-2 inline align-middle text-lg font-semibold">Analyst Case File</h1>
        </div>
        <button onClick={() => setShowNew((v) => !v)} className="btn btn-primary">
          {showNew ? "Cancel" : "New case"}
        </button>
      </header>

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {showNew && (
        <NewCaseForm
          onCreated={async (created) => {
            setShowNew(false);
            await refreshList();
            await openCase(created.id);
          }}
          onError={setError}
        />
      )}

      {/* Case list */}
      <ul className="surface divide-y divide-border overflow-hidden">
        {cases.map((c) => (
          <li key={c.id}>
            <button
              onClick={() => openCase(c.id)}
              className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-xs hover:bg-bg-elevated ${
                selected?.id === c.id ? "bg-bg-elevated" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-fg">{c.title}</div>
                <div className="text-fg-subtle">
                  {c.pin_count} pin{c.pin_count === 1 ? "" : "s"} ·{" "}
                  <span className={STATUS_COLOR[c.status] ?? "text-fg-muted"}>{c.status}</span>
                </div>
              </div>
              <span className="text-[10px] text-fg-subtle">
                {new Date(c.updated_at).toLocaleDateString()}
              </span>
            </button>
          </li>
        ))}
        {cases.length === 0 && (
          <li className="px-3 py-4 text-center text-xs text-fg-subtle">
            No cases yet. Create your first investigation.
          </li>
        )}
      </ul>

      {/* Selected case detail */}
      {selected && (
        <div className="surface space-y-3 p-3 text-xs">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="truncate text-sm font-semibold text-fg">{selected.title}</div>
              {selected.summary && (
                <p className="mt-0.5 text-fg-muted">{selected.summary}</p>
              )}
            </div>
            <div className="flex shrink-0 gap-1">
              {(["open", "closed", "archived"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => updateStatus(s)}
                  className={`btn px-2 py-0.5 text-[10px] capitalize ${
                    selected.status === s ? "border-accent text-accent" : ""
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <PinForm
            caseId={selected.id}
            onPinned={() => openCase(selected.id)}
            onError={setError}
          />

          <div>
            <div className="mb-1 flex items-center justify-between text-[10px] uppercase tracking-wider text-fg-subtle">
              <span>Pinned entities</span>
              <span>{selected.pins.length}</span>
            </div>
            <ul className="space-y-1">
              {selected.pins.map((p) => (
                <li
                  key={p.id}
                  className="flex items-center justify-between rounded border border-border bg-bg-elevated p-2"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-bg-panel px-1.5 py-0.5 font-mono text-[10px] uppercase text-fg-muted">
                        {p.entity.kind}
                      </span>
                      <span className="truncate font-medium text-fg">
                        {p.entity.label}
                      </span>
                    </div>
                    <div className="mt-0.5 truncate font-mono text-[10px] text-fg-subtle">
                      {p.entity.ref_id}
                    </div>
                    {p.notes && (
                      <div className="mt-0.5 text-fg-muted">{p.notes}</div>
                    )}
                  </div>
                  <button
                    onClick={() => unpin(p.id)}
                    className="btn shrink-0 px-2 py-0.5 text-[10px]"
                    aria-label={`Unpin ${p.entity.label}`}
                  >
                    Unpin
                  </button>
                </li>
              ))}
              {selected.pins.length === 0 && (
                <li className="rounded border border-border bg-bg-elevated p-3 text-center text-fg-subtle">
                  No pins yet. Use the form above or pin from a dashboard.
                </li>
              )}
            </ul>
          </div>

          <div className="flex flex-wrap gap-2">
            <button
              onClick={async () => {
                try {
                  await api.cases.downloadStix(
                    selected.id,
                    `aperture-${selected.title.replace(/\s+/g, "-").toLowerCase()}.stix.json`,
                  );
                } catch (e) {
                  setError(e instanceof ApiError ? e.message : "Export failed");
                }
              }}
              className="btn"
            >
              Export STIX 2.1
            </button>
            <span className="self-center text-[10px] text-fg-subtle">
              PDF export lands in Phase 7.2.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function NewCaseForm({
  onCreated,
  onError,
}: {
  onCreated: (c: CasePublic) => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const c = await api.cases.create(title.trim(), summary.trim() || undefined);
      await onCreated(c);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="surface space-y-2 p-3">
      <div>
        <label className="label" htmlFor="case-title">
          Title
        </label>
        <input
          id="case-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
          minLength={1}
          maxLength={256}
          className="input"
        />
      </div>
      <div>
        <label className="label" htmlFor="case-summary">
          Summary (optional)
        </label>
        <textarea
          id="case-summary"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
          rows={2}
          className="input resize-y"
        />
      </div>
      <button type="submit" className="btn btn-primary w-full" disabled={busy}>
        {busy ? "Creating…" : "Create case"}
      </button>
    </form>
  );
}

function PinForm({
  caseId,
  onPinned,
  onError,
}: {
  caseId: string;
  onPinned: () => void | Promise<void>;
  onError: (msg: string) => void;
}) {
  const [kind, setKind] = useState("vessel");
  const [refId, setRefId] = useState("");
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.cases.pin(caseId, {
        kind,
        ref_id: refId.trim(),
        label: label.trim() || refId.trim(),
        notes: notes.trim() || undefined,
      });
      setRefId("");
      setLabel("");
      setNotes("");
      await onPinned();
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Pin failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-border bg-bg-elevated p-2">
      <div className="text-[10px] uppercase tracking-wider text-fg-subtle">Pin entity</div>
      <div className="grid grid-cols-3 gap-1">
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="input"
          aria-label="Entity kind"
        >
          <option value="vessel">vessel</option>
          <option value="aircraft">aircraft</option>
          <option value="host">host</option>
          <option value="url">url</option>
          <option value="domain">domain</option>
          <option value="person">person</option>
        </select>
        <input
          value={refId}
          onChange={(e) => setRefId(e.target.value)}
          placeholder="ref id (mmsi, ip, …)"
          required
          className="input col-span-2"
        />
      </div>
      <input
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        placeholder="label (display name; defaults to ref id)"
        className="input"
      />
      <input
        value={notes}
        onChange={(e) => setNotes(e.target.value)}
        placeholder="notes (optional)"
        className="input"
      />
      <button type="submit" className="btn btn-primary w-full" disabled={busy}>
        {busy ? "Pinning…" : "Pin to case"}
      </button>
    </form>
  );
}
