/**
 * "Active case" state for cross-dashboard pinning.
 *
 * Lives in localStorage and is sourced by the Case File dashboard when
 * the analyst selects a case. Other dashboards read it via
 * `useActiveCase()` and offer "Pin to active case" buttons.
 */

import { useEffect, useState } from "react";

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
