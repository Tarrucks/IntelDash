export default function CasePage() {
  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-case align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Analyst Case File</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Pin entities across domains, build a timeline, export STIX/PDF.
        </p>
      </header>
      <div className="surface p-4 text-xs text-fg-muted">
        Case list + pinned entities + timeline render here.
      </div>
    </div>
  );
}
