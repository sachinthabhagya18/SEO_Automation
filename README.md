# SEO Automation Platform

Current operation: [Nov 17 results](docs/NOV17_PROGRESS_SI.md), [Google setup](docs/GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md). Start with `powershell -ExecutionPolicy Bypass -File scripts/start-platform.ps1` (add `-SkipBuild` when unchanged). Real Gemini research is verified on 3.5 Flash-Lite; Google metrics need account setup. Full specification remains under implementation.

Internal Django platform under active implementation. The full product specification is preserved in [docs/PRODUCT_SPECIFICATION.txt](docs/PRODUCT_SPECIFICATION.txt); [STATUS](docs/STATUS.md) records tested behavior and [the plan](docs/IMPLEMENTATION_PLAN.md) tracks the full scope.

Start Docker Desktop with Linux containers, then run in PowerShell from this folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose exec web python manage.py bootstrap_owner --email you@example.com --company "Your company"
```

Open the private one-time invitation link printed by the bootstrap command and choose a password. No fixed admin password or automatic Django superuser is created. Invitation URLs are sensitive; keep them private. Open [the app](http://localhost:8000) and [n8n](http://localhost:5679) only after startup succeeds. n8n requires its own owner setup.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
docker compose ps
docker compose logs --tail 80 web migrate worker
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backup.ps1
```

Services use dedicated project named volumes. Never use `docker compose down -v` as routine troubleshooting. Existing .env is preserved; changing initialization credentials does not rotate credentials in existing PostgreSQL volumes. No database/Redis host ports or Docker socket mounts. No public deployment is authorized.

Current build supports accounts, assignments, profiles, URL-only onboarding, bounded public research, source-linked heading candidates, search/social previews, metadata drafts with separate review, and local-only verified publication/restore. Local plugin source includes private SEO history CPT records. Gemini profile suggestions require private configuration and live-provider acceptance. See [URL research and preview](docs/URL_RESEARCH_AND_PREVIEW.md), [owner instructions](docs/OWNER_SETUP.md), [security](docs/SECURITY.md), [compatibility](docs/COMPATIBILITY.md) and [feature matrix](docs/FEATURE_MATRIX.md).

Denim Yard has a verified encrypted WordPress read connection, public inventory, and authenticated/timer-triggered daily n8n public audits. Live writes remain disabled. See [connection and automation evidence](docs/DENIM_YARD_CONNECTION_AND_AUTOMATION.md). Complete competitor research, AI drafting, production publication, analytics and the remaining workflows are unfinished.
