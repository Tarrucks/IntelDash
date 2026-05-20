"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { api, ApiError } from "@/lib/api";
import { writeAuth } from "@/lib/auth";

export default function RegisterPage() {
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
      await api.register(email, password);
      // Auto-login so the analyst lands inside the app immediately.
      const tok = await api.login(email, password);
      writeAuth(tok.access_token, tok.role);
      router.push("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex h-full items-center justify-center px-4">
      <form
        onSubmit={onSubmit}
        className="surface w-full max-w-sm space-y-4 p-6"
        aria-label="Create an Aperture account"
      >
        <header>
          <h1 className="text-xl font-semibold">Create account</h1>
          <p className="mt-1 text-xs text-fg-muted">
            Already have one?{" "}
            <Link href="/login" className="underline underline-offset-2 hover:text-fg">
              Sign in
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
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            className="input"
          />
          <p className="mt-1 text-[10px] text-fg-subtle">At least 8 characters.</p>
        </div>

        {error && (
          <div role="alert" className="rounded-md border border-red-900/60 bg-red-950/40 p-2 text-xs text-red-300">
            {error}
          </div>
        )}

        <button type="submit" className="btn btn-primary w-full" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </main>
  );
}
