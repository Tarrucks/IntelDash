#!/usr/bin/env bash
# Aperture setup helper. Idempotent.
# - Copies .env.example to .env if missing.
# - Generates a JWT_SECRET if blank.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[setup] created .env from template"
fi

# Generate JWT_SECRET if the line is present and empty.
if grep -qE '^JWT_SECRET=\s*$' .env; then
  SECRET="$(openssl rand -hex 32 2>/dev/null || python3 -c 'import secrets;print(secrets.token_hex(32))')"
  # In-place edit that works on BSD and GNU sed.
  sed -i.bak -E "s|^JWT_SECRET=.*$|JWT_SECRET=${SECRET}|" .env
  rm -f .env.bak
  echo "[setup] generated JWT_SECRET"
fi

echo "[setup] done. Next: docker compose up -d db redis"
