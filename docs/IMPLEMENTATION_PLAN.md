# Latest evidence - 2026-11-17

The traceability table below is historical. Current verified delivery includes typed test publication, live Gemini research, staging AI drafts and Google OAuth/metrics code with owner-account acceptance blocked. Full suite: 170. STATUS.md and NOV17_PROGRESS_SI.md supersede old coverage counts. The full specification has substantial pending work.

# Implementation plan and specification traceability

Source of truth: [PRODUCT_SPECIFICATION.txt](PRODUCT_SPECIFICATION.txt), preserved verbatim from the attachment. Started 2026-11-16. This is a multi-milestone product; foundation delivery does not complete the project. Check STATUS.md for evidence before treating any item as verified.

Legend: implemented = source exists; verified = named checks passed; pending = authorized local work remains; external = needs owner setup. A milestone is accepted only when its acceptance checks pass.

| Spec section | Deliverable / milestone | Current coverage and remaining work |
|---|---|---|
| 1 Objective/context | All milestones | Internal multi-site Django app; PowerShell detected. Full SEO lifecycle pending. UTC-aware storage, Colombo default. |
| 2 Architecture | M1, M4, M6, M7 | Django/DRF/PostgreSQL/Celery/Redis/n8n Compose; compiled Tailwind/Alpine. Bounded public HTTP and single-page audit implemented. AI, LangGraph, full crawling, charts and storage adapter pending. |
| 3 Scope/status | Every milestone | Full specification, this traceability table, STATUS and owner setup preserved. |
| 4 Identity/authorization | M1 + M8 hardening | Custom user first migration, memberships, permission bundles, assignments, invitation expiry, login throttling, CSRF, logout and authorization tests. Password recovery, TOTP MFA, full action grants UI and queued actor checks pending. MFA is a release blocker. Audit queued-actor revocation checks are now tested; publication checks await M4. |
| 5 Onboarding | M1/M2/M4 | Save/edit incomplete business profiles and site timezone. Connection wizard, encrypted credentials, capabilities, freshness, policy/budgets pending. |
| 6 Reference research | M3 | Manual/CSV reference input and validation implemented/tested. Research crawling, source-backed keywords, clusters, metrics imports/exports and locking pending. No actual reference URLs provided. |
| 7 Standalone WP plugin | M2/M4 | Partial renderer/conflict modes, read-only versioned REST/custom read capability, ZIP and local WP tests implemented. Durable write ledger, restore and full installation matrix pending. |
| 7.1 Metadata/output | M2/M5 | Singular/archive contexts, core title/robots/canonical, schema validation, social, sitemap, breadcrumbs, privacy and reciprocal hreflang tests pending. |
| 7.2 Ownership | M2 | Explicit modes/known conflict detection and custom-theme duplicate-output checks passed. Migration previews and real third-party plugin tests pending. No external SEO write adapters claimed. |
| 7.3 Security | M2/M4 | HTTPS Application Passwords, object capabilities, encrypted secret rotation, bounded APIs, writes-off and optional signed events pending. |
| 7.4 Connector contract | M2/M4 | Capabilities/pages/SEO/content-map/preview/apply/status/restore/health pending; no arbitrary meta endpoints. |
| 8 Content compatibility | M5 | Metadata first; Gutenberg parsing, custom mapped fields and safe Elementor allowlist pending. |
| 8.1 Metadata | M2 | Custom-theme and Elementor Canvas HTTP output tests pending. |
| 8.2 Standard content | M5 | Block-preserving field operations pending. |
| 8.3 Custom fields/theme | M5/M8 | Registered meta/ACF field mapping and code-change tasks pending. |
| 8.4 Elementor | M5 | Supported document save path/version investigation, readonly unsupported widgets, snapshots and screenshot verification pending; Pro not assumed. |
| 9 Audit/features | M2/M5/M8 | Five deterministic HTTP/head rules and snapshot/issue evidence implemented. Full technical/content/local/ecommerce/off-page/international features pending. No ranking promises. |
| 10 Health scoring | M2 | Versioned applicability-aware rubric 30/25/20/10/15 unit-tested. Site aggregation remains pending; insufficient coverage reports unknown. |
| 11 Knowledge/AI | M4 | Profile facts/rules stored; source approval, retrieval, Pydantic schemas, Gemini, budgets and durable LangGraph checkpoints pending. Live credential external. |
| 12 Change lifecycle | M4 | Immutable approval hashes, policy recheck, remote idempotency, reconciliation, public verification, conflict-aware restore pending. All new sites paused. |
| 13 Analytics | M6 | GSC OAuth, GA4 events, PSI lab and CrUX field data pending. Google authorization external. Charts must use actual metrics. |
| 14 n8n | M7 | Isolated n8n service/database prepared. Ten required parameterized workflows, scoped service auth, outbox/inbox, due schedule owner, import/run checks and licensing review pending. |
| 15 UX | M1–M8 | Templates for login/invite, overview, profile, staff/permissions, references and public-audit job evidence. Remaining evidence/audit/research/editor/review/performance/automation/integrations/reports/MFA screens pending. |
| 16 Data/API | M1–M8 | Normalized identity/site/access/audit tables and read-only paginated /api/v1/sites; request IDs and authenticated OpenAPI schema. Durable Job/Page/PageSnapshot/AuditIssue models and read-only job API now implemented; remaining SEO/change/provider models pending. |
| 17 Repository | Every milestone | Requested folder layout started, lockfiles and Docker build. Plugin ZIP/workflow exports produced only when functional, not placeholder artifacts. |
| 18 Operations | M1/M8 | Localhost UIs, internal DB/Redis, named volumes, healthchecks, nonroot app, secret generation and logical backup helper. WP/MariaDB profile, disposable logical restore and manual queue recovery passed local checks; DNS-pinned protected single-page fetch implemented. Proxy/production, full crawler/browser egress and automated reconciliation remain pending. |
| 19 Tests | Every milestone | 49 PostgreSQL/component tests, 13 local WordPress checks, real HTTP output and disposable DB restoration passed. Remaining publication/Elementor/provider/workflow/browser/full-volume recovery acceptance remains. Exact results in STATUS. |
| 20 Milestones | Below | M1 local acceptance passed; M2 partial and M3 inputs implemented; remaining M2–M8 work pending. Do not mark M4 as final delivery. |
| 21 Owner guide | Every milestone | Sinhala setup plus exact current commands; later external steps explicitly marked pending. |
| 22 Handoff | Every milestone | README, STATUS, manual steps and feature matrix must reflect tested behavior only. |

## Ordered milestone backlog

- [x] M1 Foundation: clean Compose boot/migrations, PostgreSQL authorization tests, secure owner setup and HTTP UI smoke checks passed. Visual browser checks remain unverified.
- [ ] M2 Plugin/read-only audit: WP/MariaDB fixture, installable plugin with exactly-once head output, read APIs, protected HTTP crawler, deterministic issue evidence and coverage-aware scores. Verify custom theme and Elementor separately.
- [ ] M3 Research: managed versus reference URL separation, CSV imports, bounded crawl, traceable candidates/clusters/map/export; metrics unknown unless supplied.
- [ ] M4 Deterministic draft/review/publish/verify/restore first; then live Gemini adapter and checkpointed LangGraph. Test stale hashes, revoked users, duplicate jobs, remote timeouts and policy changes.
- [ ] M5 Content: blocks, mapped fields and tested Elementor widget/version allowlist; unsupported cases become manual tasks.
- [ ] M6 Google/performance: fixtures for OAuth/pagination/errors, property selection, GSC/GA4, PSI/CrUX. Live checks depend on account authorization.
- [ ] M7 n8n: scoped auth, durable jobs/outbox/inbox, all ten workflows, one scheduler, real import and scheduled audit/approved dispatch test.
- [ ] M8 Hardening: MFA, password recovery, local/international/ecommerce/off-page tasks, reports, backups/restoration, browser checks, least-privilege DB roles, production deployment guide. External providers/licenses remain clearly blocked when unavailable.

## Decisions

Use Django 5.2 LTS with DRF 3.16 and Python 3.14; exact installed pins in backend/requirements.lock. Model migrations are generated using Django, never with a SQLite substitute. The development web process uses Django runserver to serve compiled assets; production requires a static-serving proxy and Gunicorn configuration. n8n owns business schedules when M7 lands; no Celery Beat service. Separate n8n PostgreSQL service avoids app-table access. No customer credentials, external publication, outbound email or synthetic production metrics are introduced.

## Latest verified boundary (2026-11-16)

M1 is locally accepted. M2 now includes an installable partial read-only connector/renderer, synthetic custom-theme WordPress fixture, limited public-page audit jobs, stored snapshots/issues, protected transport components and unit-tested coverage-aware scoring. M3 includes manual/CSV reference inputs only. See STATUS for 49-test PostgreSQL suite, 13 WordPress checks, real HTTP output, restart and disposable restore evidence. The table above remains a full backlog; metadata breadth, Elementor, Django connection setup, full crawling/research, publication, providers and workflows are still open. No partial milestone is counted as full specification completion.

## Live-read/automation progress (2026-11-16)

Encrypted SiteConnection and KnowledgeSource are implemented with owner-only integration UI, revocation, provenance and separate-key storage. Denim Yard's real HTTPS Application Password connection/capabilities and 22 public inventory records were verified. Owner-provided business facts take precedence over observed marketing claims. Six bounded public source pages were researched; this does not complete keyword discovery/clustering/maps.

Two inactive-by-default n8n exports are importable and executed with encrypted runtime credential bindings; the local example is published and daily read-only audit enabled. Both authenticated initial execution and an actual clock-trigger?scoped API?Celery?Denim Yard evidence succeeded. Django owns next_due; n8n checks due work once per minute. Revoked/expired service credentials cannot run queued jobs. The full M7 remains open for the other eight workflows, durable event outbox/inbox and generalized multi-site dispatch; M2 still needs broader metadata/Elementor/sitemap tests. Full new suite: 70 passed. No live-site writes performed; M4 publication remains pending.
