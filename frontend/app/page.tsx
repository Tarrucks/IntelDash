import Link from "next/link";

import { GlobalHeader } from "@/components/global-header";

export default function Home() {
  return (
    <div className="flex h-full flex-col">
      <GlobalHeader />
      <main className="flex flex-1 flex-col items-center justify-center gap-8 px-4">
        <div className="max-w-2xl text-center">
          <h1 className="text-4xl font-semibold tracking-tight">Aperture</h1>
          <p className="mt-3 text-fg-muted">
            OSINT fusion across cyber, maritime, aviation, and open-web — on a single map.
          </p>
        </div>

        <div className="grid w-full max-w-4xl grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <DomainCard
            href="/maritime"
            title="Maritime Domain Awareness"
            blurb="Live AIS, historic tracks, anomaly flags."
            domain="maritime"
          />
          <DomainCard
            href="/aviation"
            title="Aviation Tracking"
            blurb="Live flight positions, routes, airports."
            domain="aviation"
          />
          <DomainCard
            href="/cyber"
            title="Cyber Surface"
            blurb="Shodan hosts, banners, surface monitoring."
            domain="cyber"
          />
          <DomainCard
            href="/web"
            title="AI Web Search"
            blurb="Exa semantic search + answer synthesis."
            domain="web"
          />
          <DomainCard
            href="/case"
            title="Analyst Case File"
            blurb="Pin entities across domains, export STIX/PDF."
            domain="case"
          />
        </div>

        <div className="text-xs text-fg-subtle">
          New here?{" "}
          <Link href="/register" className="underline underline-offset-2 hover:text-fg">
            Create an account
          </Link>{" "}
          ·{" "}
          <Link href="/login" className="underline underline-offset-2 hover:text-fg">
            Sign in
          </Link>
        </div>
      </main>
    </div>
  );
}

function DomainCard({
  href,
  title,
  blurb,
  domain,
}: {
  href: string;
  title: string;
  blurb: string;
  domain: "maritime" | "aviation" | "cyber" | "web" | "case";
}) {
  return (
    <Link
      href={href}
      className="surface group block p-4 transition-colors hover:border-border-strong hover:bg-bg-elevated"
    >
      <div className="flex items-center gap-2">
        <span
          className={`inline-block h-2 w-2 rounded-full bg-domain-${domain}`}
          aria-hidden
        />
        <span className="text-sm font-medium">{title}</span>
      </div>
      <p className="mt-1 text-xs text-fg-muted">{blurb}</p>
    </Link>
  );
}
