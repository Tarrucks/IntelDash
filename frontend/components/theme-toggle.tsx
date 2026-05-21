"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { readTheme, writeTheme, type Theme } from "@/lib/theme";

export function ThemeToggle() {
  // Read current theme post-hydration so SSR markup matches the
  // class-on-html applied by the inline init script.
  const [theme, setTheme] = useState<Theme>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setTheme(readTheme());
    setMounted(true);
  }, []);

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    writeTheme(next);
    setTheme(next);
  }

  // Don't render the icon contents until mounted, so the SSR HTML
  // (which can't see localStorage) doesn't claim a different state.
  // We keep the button's outline so layout doesn't jump.
  return (
    <button
      onClick={toggle}
      className="btn px-2"
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      aria-pressed={theme === "dark"}
      type="button"
    >
      {mounted && (theme === "dark" ? <Sun size={14} /> : <Moon size={14} />)}
    </button>
  );
}
