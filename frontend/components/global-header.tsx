"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";

import { clearAuth, isAuthenticated, readRole } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { ThemeToggle } from "@/components/theme-toggle";

import { LogOut, Search } from "lucide-react";

export function GlobalHeader() {
  const router = useRouter();
  const authed = isAuthenticated();
  const role = readRole();

  function logout() {
    clearAuth();
    router.push("/login");
  }

  return (
    <header className="flex h-14 items-center justify-between border-b border-border bg-bg-elevated px-4">
      <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full bg-accent shadow-[0_0_12px_2px_hsl(195_90%_55%/0.6)]"
        />
        Aperture
        <span className="text-xs font-normal text-fg-subtle">OSINT Fusion</span>
      </Link>

      <div className="mx-4 flex flex-1 max-w-xl">
        <EntitySearch />
      </div>

      <div className="flex items-center gap-3 text-sm">
        <ThemeToggle />
        {authed ? (
          <>
            <span className="text-fg-muted">role:</span>
            <span className={cn("font-mono text-xs uppercase", "text-accent")}>{role}</span>
            <button onClick={logout} className="btn" aria-label="Sign out">
              <LogOut size={14} /> Sign out
            </button>
          </>
        ) : (
          <Link href="/login" className="btn btn-primary">
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}

function EntitySearch() {
  return (
    <form
      role="search"
      className="relative flex w-full items-center"
      onSubmit={(e) => {
        e.preventDefault();
        // Routes lit up in Phase 5+. For now this is the visual element only.
      }}
    >
      <Search
        size={14}
        className="pointer-events-none absolute left-3 text-fg-subtle"
        aria-hidden
      />
      <input
        type="search"
        placeholder="Search vessels, aircraft, hosts, URLs…"
        className="input pl-9"
        aria-label="Global entity search"
      />
    </form>
  );
}
