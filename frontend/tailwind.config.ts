import type { Config } from "tailwindcss";

// Aperture defaults to dark mode (per Phase 8 brief). Light mode is a
// toggle on top — Tailwind's "class" strategy makes that trivial later.
const config: Config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tokens kept terse and semantic so we can repaint without churning
        // markup. Values picked for legible contrast on a dark canvas.
        bg: {
          DEFAULT: "hsl(220 13% 8%)",
          elevated: "hsl(220 13% 12%)",
          panel: "hsl(220 13% 15%)",
        },
        fg: {
          DEFAULT: "hsl(210 20% 92%)",
          muted: "hsl(220 8% 65%)",
          subtle: "hsl(220 8% 45%)",
        },
        border: {
          DEFAULT: "hsl(220 13% 22%)",
          strong: "hsl(220 13% 30%)",
        },
        accent: {
          DEFAULT: "hsl(195 90% 55%)",
          fg: "hsl(220 13% 8%)",
        },
        // Cross-domain palette — same hues as the map layer overlays
        // so the UI and the map agree on what "maritime" means.
        domain: {
          maritime: "hsl(200 80% 55%)",
          aviation: "hsl(40 95% 60%)",
          cyber: "hsl(280 70% 65%)",
          web: "hsl(150 60% 55%)",
          case: "hsl(0 0% 90%)",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
