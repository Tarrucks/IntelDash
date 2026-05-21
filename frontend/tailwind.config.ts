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
        // Tokens reference CSS variables defined in globals.css under
        // ``:root`` (light) and ``.dark``. Tailwind's
        // ``<alpha-value>`` placeholder lets utility classes apply
        // alpha without us redefining a colour per opacity.
        bg: {
          DEFAULT: "hsl(var(--bg) / <alpha-value>)",
          elevated: "hsl(var(--bg-elevated) / <alpha-value>)",
          panel: "hsl(var(--bg-panel) / <alpha-value>)",
        },
        fg: {
          DEFAULT: "hsl(var(--fg) / <alpha-value>)",
          muted: "hsl(var(--fg-muted) / <alpha-value>)",
          subtle: "hsl(var(--fg-subtle) / <alpha-value>)",
        },
        border: {
          DEFAULT: "hsl(var(--border) / <alpha-value>)",
          strong: "hsl(var(--border-strong) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          fg: "hsl(var(--accent-fg) / <alpha-value>)",
        },
        domain: {
          maritime: "hsl(var(--domain-maritime) / <alpha-value>)",
          aviation: "hsl(var(--domain-aviation) / <alpha-value>)",
          cyber: "hsl(var(--domain-cyber) / <alpha-value>)",
          web: "hsl(var(--domain-web) / <alpha-value>)",
          case: "hsl(var(--domain-case) / <alpha-value>)",
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
