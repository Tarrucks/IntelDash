/**
 * Theme persistence + initial-paint script.
 *
 * The brief sets dark as the default with a light toggle. We honour
 * (in priority order):
 *   1. localStorage("aperture.theme"), if set by the user
 *   2. `prefers-color-scheme: light`, if matched
 *   3. dark
 *
 * The initial paint runs as an inline `<script>` before React hydrates
 * (see `app/layout.tsx`) so the first paint matches the persisted
 * preference and we avoid a flash of the wrong theme.
 */

export type Theme = "light" | "dark";

export const THEME_STORAGE_KEY = "aperture.theme";

/**
 * Inline script body that runs before hydration.
 *
 * Inlined verbatim into the `<head>` so it's blocking and synchronous
 * — the document never paints in the wrong theme.
 */
export const themeInitScript = `(function() {
  try {
    var stored = window.localStorage.getItem(${JSON.stringify(THEME_STORAGE_KEY)});
    var theme = stored;
    if (!theme) {
      theme = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches
        ? 'light'
        : 'dark';
    }
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  } catch (_e) {
    document.documentElement.classList.add('dark');
  }
})();`;

export function readTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

export function writeTheme(theme: Theme) {
  if (typeof window === "undefined") return;
  if (theme === "dark") {
    document.documentElement.classList.add("dark");
  } else {
    document.documentElement.classList.remove("dark");
  }
  window.localStorage.setItem(THEME_STORAGE_KEY, theme);
}
