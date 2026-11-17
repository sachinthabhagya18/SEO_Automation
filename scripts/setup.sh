#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo 'First run scripts/setup.ps1 from PowerShell to generate local secrets, or securely create .env from .env.example.' >&2
  exit 1
fi
docker info >/dev/null
docker compose config --quiet
docker compose up -d --build --wait
