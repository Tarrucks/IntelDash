import type { ReactNode } from "react";
import dynamic from "next/dynamic";

import { GlobalHeader } from "@/components/global-header";
import { Sidebar } from "@/components/sidebar";
import { MapProvider } from "@/lib/map-context";

// MapLibre uses WebGL2; loading it during SSR throws on the missing
// `window`. `ssr: false` keeps the canvas client-only.
const MapCanvas = dynamic(() => import("@/lib/map-canvas").then((m) => m.MapCanvas), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-bg-panel" />,
});

export default function DashboardsLayout({ children }: { children: ReactNode }) {
  return (
    <MapProvider>
      <a href="#dashboard-panel" className="skip-link">
        Skip to dashboard
      </a>
      <div className="flex h-full flex-col">
        <GlobalHeader />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar />
          {/* Two-pane split: panel on the left, shared map on the right. */}
          <main className="flex flex-1 overflow-hidden">
            <section
              id="dashboard-panel"
              className="flex w-[420px] flex-col overflow-y-auto border-r border-border bg-bg p-4"
              aria-label="Dashboard panel"
            >
              {children}
            </section>
            <section
              className="relative flex-1 bg-bg-panel"
              aria-label="Geospatial map"
            >
              <MapCanvas className="h-full w-full" />
            </section>
          </main>
        </div>
      </div>
    </MapProvider>
  );
}
