/**
 * "Active case" state for cross-dashboard pinning.
 *
 * Lives in localStorage and is sourced by the Case File dashboard when
 * the analyst selects a case. Other dashboards read it via
 * `useActiveCase()` and offer "Pin to active case" buttons.
 */

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "./api";

const KEY = "aperture.active_case";
const EVENT = "aperture:active-case-changed";

export type ActiveCase = { id: string; title: string };

export function readActiveCase(): ActiveCase | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ActiveCase;
  } catch {
    return null;
  }
}

export function setActiveCase(active: ActiveCase | null) {
  if (typeof window === "undefined") return;
  if (active) window.localStorage.setItem(KEY, JSON.stringify(active));
  else window.localStorage.removeItem(KEY);
  // Custom event lets other tabs/components in the same window react.
  window.dispatchEvent(new CustomEvent(EVENT));
}

export function useActiveCase(): ActiveCase | null {
  const [active, setActive] = useState<ActiveCase | null>(null);
  useEffect(() => {
    setActive(readActiveCase());
    const onChange = () => setActive(readActiveCase());
    window.addEventListener(EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);
  return active;
}

/**
 * "Pin to active case" — shared logic for every dashboard.
 *
 * Returns `null` if there's no active case (caller should hide the
 * button); otherwise an object the caller can wire into a button.
 */
export type PinPayload = {
  kind: string;
  ref_id: string;
  label: string;
  extra?: Record<string, unknown>;
  notes?: string;
};

export function usePinToActiveCase(): {
  active: ActiveCase | null;
  pinned: boolean;
  error: string | null;
  pin: (payload: PinPayload) => Promise<void>;
  reset: () => void;
} {
  const active = useActiveCase();
  const [pinned, setPinned] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pin = useCallback(
    async (payload: PinPayload) => {
      if (!active) return;
      setPinned(false);
      setError(null);
      try {
        await api.cases.pin(active.id, payload);
        setPinned(true);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Pin failed");
      }
    },
    [active],
  );

  const reset = useCallback(() => {
    setPinned(false);
    setError(null);
  }, []);

  return { active, pinned, error, pin, reset };
}
