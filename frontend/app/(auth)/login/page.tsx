"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { api, ApiError } from "@/lib/api";
import { writeAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const tok = await api.login(email, password);
      writeAuth(tok.access_token, tok.role);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-full items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="surface w-full max-w-sm space-y-4 p-6"
        aria-label="Sign in to Aperture"
      >
        <header>
          <h1 className="text-xl font-semibold">Sign in</h1>
          <p className="mt-1 text-xs text-fg-muted">
            New here?{" "}
            <Link href="/register" className="underline underline-offset-2 hover:text-fg">
              Create an account
            </Link>
          </p>
        </header>

        <div>
          <label className="label" htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="input"
          />
        </div>

        <div>
          <label className="label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="input"
          />
        </div>

        {error && (
          <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
            {error}
          </div>
        )}

        <button type="submit" className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
