export default function WebPage() {
  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-web align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">AI Web Search</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Exa semantic search + synthesised answers. Wired up in Phase 5.
        </p>
      </header>
      <div className="surface p-4 text-xs text-fg-muted">
        Search box + result list render here.
      </div>
    </div>
  );
}
