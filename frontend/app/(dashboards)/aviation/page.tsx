export default function AviationPage() {
  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-aviation align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Aviation Tracking</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Live flight positions, routes, airports. Wired up in Phase 5.
        </p>
      </header>
      <div className="surface p-4 text-xs text-fg-muted">
        Flight list + filters render here.
      </div>
    </div>
  );
}
