"use client";

/**
 * `<MapCanvas>` — MapLibre + Deck.gl in interleaved mode.
 *
 * Layers come from `useMap().layers`; updating that array re-pushes
 * them into the deck overlay. `interleaved: true` lets Deck render
 * into MapLibre's WebGL2 context so 3D extrusions and depth-buffer
 * tricks work as expected.
 *
 * Client-only via `next/dynamic` (`ssr: false`) at the call site.
 */

import { MapboxOverlay } from "@deck.gl/mapbox";
import maplibregl, { type Map as MaplibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { useMap } from "./map-context";

const STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://demotiles.maplibre.org/style.json";

export function MapCanvas({ className }: { className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MaplibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const { viewState, setViewState, layers } = useMap();

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

    // Interleaved mode places Deck layers inside MapLibre's WebGL2 ctx.
    const overlay = new MapboxOverlay({ interleaved: true, layers: [] });
    map.addControl(overlay as unknown as maplibregl.IControl);

    mapRef.current = map;
    overlayRef.current = overlay;

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
      overlayRef.current = null;
    };
    // Map mounts once; sync handler keeps context fresh on user gestures.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push layer changes through to the deck overlay.
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    // The shape of `layer` is unknown to the context (it stays decoupled
    // from deck.gl typings) so we cast at the boundary.
    overlay.setProps({ layers: layers.map((l) => l.layer) as never });
  }, [layers]);

  return <div ref={ref} className={className ?? "h-full w-full"} aria-label="Map" />;
}
