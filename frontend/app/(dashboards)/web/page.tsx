"use client";

import { useState } from "react";

import { api, ApiError, type WebAnswer, type WebSearch } from "@/lib/api";

type Tab = "search" | "answer";

export default function WebPage() {
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<Tab>("search");
  const [search, setSearch] = useState<WebSearch | null>(null);
  const [answer, setAnswer] = useState<WebAnswer | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (tab === "search") {
        setSearch(await api.web.search(q.trim(), { numResults: 8, mode: "fast" }));
      } else {
        setAnswer(await api.web.answer(q.trim()));
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-web align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">AI Web Search</h1>
      </header>

      {/* Mode toggle */}
      <div className="flex gap-1 rounded-md border border-border bg-bg-elevated p-1 text-xs">
        {(["search", "answer"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded px-2 py-1 capitalize transition-colors ${
              tab === t ? "bg-bg-panel text-fg" : "text-fg-muted hover:text-fg"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <form onSubmit={run} className="surface space-y-2 p-3">
        <label className="label" htmlFor="web-q">
          Query
        </label>
        <textarea
          id="web-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          required
          minLength={2}
          rows={3}
          className="input resize-y"
          placeholder={tab === "search" ? "Find articles about…" : "Ask a research question…"}
        />
        <button type="submit" className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Working…" : tab === "search" ? "Search" : "Get answer"}
        </button>
      </form>

      {error && (
        <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {tab === "search" && search && (
        <div className="space-y-2 text-xs">
          <div className="text-fg-subtle">
            <span className="font-mono text-fg">{search.results.length}</span> results ·{" "}
            {search.autoprompt && (
              <span className="italic">improved: “{search.autoprompt}”</span>
            )}
          </div>
          <ul className="space-y-2">
            {search.results.map((r) => (
              <li key={r.id} className="surface p-3">
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block font-medium text-fg hover:underline"
                >
                  {r.title ?? r.url}
                </a>
                <div className="mt-0.5 truncate text-fg-subtle">{r.url}</div>
                {r.text && (
                  <p className="mt-1 line-clamp-3 text-fg-muted">{r.text}</p>
                )}
                <div className="mt-1 flex items-center gap-2 text-[10px] text-fg-subtle">
                  {r.score != null && (
                    <span className="font-mono">{r.score.toFixed(2)}</span>
                  )}
                  {r.author && <span>· {r.author}</span>}
                  {r.published_date && <span>· {r.published_date.slice(0, 10)}</span>}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === "answer" && answer && (
        <div className="surface space-y-3 p-3 text-xs">
          <div className="text-fg-subtle">
            Sources: <span className="font-mono">{answer.sources.join(", ")}</span>
          </div>
          <p className="whitespace-pre-wrap text-fg">{answer.answer}</p>
          <div>
            <div className="mb-1 text-[10px] uppercase tracking-wider text-fg-subtle">
              Citations
            </div>
            <ul className="space-y-1">
              {answer.citations.map((c, idx) => (
                <li key={idx}>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block truncate text-fg hover:underline"
                  >
                    {c.title ?? c.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
