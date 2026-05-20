export default function MaritimePage() {
  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-maritime align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">
          Maritime Domain Awareness
        </h1>
        <p className="mt-1 text-xs text-fg-muted">
          Live AIS, historic tracks, anomaly flags. Wired up in Phase 5.
        </p>
      </header>
      <div className="surface p-4 text-xs text-fg-muted">
        Vessel list + filters render here. The map on the right shares state
        across every dashboard.
      </div>
    </div>
  );
}
