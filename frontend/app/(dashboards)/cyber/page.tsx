export default function CyberPage() {
  return (
    <div className="space-y-3">
      <header>
        <span
          className="inline-block h-2 w-2 rounded-full bg-domain-cyber align-middle"
          aria-hidden
        />
        <h1 className="ml-2 inline align-middle text-lg font-semibold">Cyber Surface</h1>
        <p className="mt-1 text-xs text-fg-muted">
          Shodan host lookup and surface monitoring. Wired up in Phase 5.
        </p>
      </header>
      <div className="surface p-4 text-xs text-fg-muted">
        Host lookup form + results render here.
      </div>
    </div>
  );
}
