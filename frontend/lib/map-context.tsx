"use client";

/**
 * Map context provider.
 *
 * Single source of truth for the shared map state (centre, zoom, bbox)
 * and for an injectable list of Deck.gl layers. Every dashboard reads
 * from this context, so switching tabs preserves view state.
 *
 * We mount MapLibre in `interleaved` mode with Deck.gl, per the CLAUDE.md
 * decision — Deck layers render into MapLibre's WebGL2 context so they
 * participate in the depth buffer (3D extrusions etc. render correctly).
 *
 * The actual MapLibre + Deck instantiation lives in `<MapCanvas>`; this
 * file only owns the state.
 */

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
};

export type BBox = { latmin: number; latmax: number; lonmin: number; lonmax: number };

// Deck.gl layer instances are intentionally typed `unknown` here so the
// context doesn't carry a heavy import in pages that don't render the map.
type DeckLayer = unknown;

export type LayerEntry = {
  id: string;
  domain: "maritime" | "aviation" | "cyber" | "web" | "case";
  layer: DeckLayer;
};

type MapContextValue = {
  viewState: ViewState;
  setViewState: (next: ViewState) => void;
  layers: LayerEntry[];
  setLayer: (entry: LayerEntry) => void;
  removeLayer: (id: string) => void;
  bbox: BBox;
};

const DEFAULT_VIEW: ViewState = {
  longitude: 12,
  latitude: 56,
  zoom: 5,
  pitch: 0,
  bearing: 0,
};

const MapContext = createContext<MapContextValue | null>(null);

function bboxFromView(view: ViewState): BBox {
  // Rough degree padding around the centre proportional to zoom. Good
  // enough for "give me vessels near here" queries; the real bbox comes
  // from the MapLibre canvas once it's mounted (Phase 5).
  const span = 30 / Math.pow(2, view.zoom - 3);
  return {
    latmin: view.latitude - span,
    latmax: view.latitude + span,
    lonmin: view.longitude - span,
    lonmax: view.longitude + span,
  };
}

export function MapProvider({ children }: { children: ReactNode }) {
  const [viewState, setViewStateRaw] = useState<ViewState>(DEFAULT_VIEW);
  const [layers, setLayers] = useState<LayerEntry[]>([]);

  const setViewState = useCallback((next: ViewState) => {
    setViewStateRaw(next);
  }, []);

  const setLayer = useCallback((entry: LayerEntry) => {
    setLayers((prev) => {
      const idx = prev.findIndex((l) => l.id === entry.id);
      if (idx === -1) return [...prev, entry];
      const copy = [...prev];
      copy[idx] = entry;
      return copy;
    });
  }, []);

  const removeLayer = useCallback((id: string) => {
    setLayers((prev) => prev.filter((l) => l.id !== id));
  }, []);

  const bbox = useMemo(() => bboxFromView(viewState), [viewState]);

  const value = useMemo(
    () => ({ viewState, setViewState, layers, setLayer, removeLayer, bbox }),
    [viewState, setViewState, layers, setLayer, removeLayer, bbox],
  );

  return <MapContext.Provider value={value}>{children}</MapContext.Provider>;
}

export function useMap(): MapContextValue {
  const ctx = useContext(MapContext);
  if (!ctx) {
    throw new Error("useMap must be called inside <MapProvider>");
  }
  return ctx;
}
