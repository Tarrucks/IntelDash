"use client";

/**
 * `<MapCanvas>` — MapLibre + Deck.gl in interleaved mode.
 *
 * Per CLAUDE.md, Kepler.gl ships its own MapLibre+Deck integration, but
 * for the dashboard map we manage them directly so we own the lifecycle.
 * Deck layers are injected via `useMap().layers`; updating the array
 * triggers a re-render of the overlay.
 *
 * Client-only — wrapped at the call site with `next/dynamic` so SSR
 * doesn't try to evaluate MapLibre's WebGL code.
 */

import { useEffect, useRef } from "react";
import maplibregl, { type Map as MaplibreMap } from "maplibre-gl";

import "maplibre-gl/dist/maplibre-gl.css";
import { useMap } from "./map-context";

const STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://demotiles.maplibre.org/style.json";

export function MapCanvas({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const { viewState, setViewState } = useMap();

  // Initial mount + teardown.
  useEffect(() => {
    if (!ref.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: ref.current,
      style: STYLE_URL,
      center: [viewState.longitude, viewState.latitude],
      zoom: viewState.zoom,
      pitch: viewState.pitch,
      bearing: viewState.bearing,
      attributionControl: { compact: true },
    });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    mapRef.current = map;

    const sync = () => {
      const c = map.getCenter();
      setViewState({
        longitude: c.lng,
        latitude: c.lat,
        zoom: map.getZoom(),
        pitch: map.getPitch(),
        bearing: map.getBearing(),
      });
    };
    map.on("moveend", sync);

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // We intentionally only mount the map once; the sync handler keeps
    // context in step with user gestures.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={ref} className={className ?? "h-full w-full"} aria-label="Map" />;
}
