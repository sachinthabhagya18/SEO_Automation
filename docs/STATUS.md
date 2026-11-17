# Current update - 2026-11-17, Asia/Colombo

Current operating steps: [today's Sinhala update](NOV17_PROGRESS_SI.md), [Google account setup](GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md). This supersedes older dated status sections below.

- Existing services were stopped; restarted without resetting data/accounts. Long-lived restart policies and scripts/start-platform.ps1 were tested; selected services reached healthy.
- Existing Gemini key authenticated. Today's gemini-3.8-flash probe returned 503. A gemini-3.5-flash-lite probe succeeded, then configuration was changed to that verified alternative. Real source-site research 77db53b9-32c7-4aa7-864d-7a883b9db328 accepted source/schema-validated AI profile/homepage suggestions. A test-site call still returned 503; availability remains intermittent. Four reservations used today; allowance not bypassed.
- Validated primary AI homepage proposal was prepared against fresh staging evidence/revision as a98c7d2f-24e8-42ed-96be-695f56520b82, pending_review. Origin audited; preparation idempotent; no approval/publication transferred or additional AI call. Production remains paused/unchanged.
- Search Console OAuth, actor/session/site/client/version-bound single-use state, PKCE, encrypted tokens, bounded fixed-origin HTTP, refresh/revoke, matching authorized properties, callback log redaction and sync_search_metrics permissions are implemented.
- Durable Google sync uses final last-28-day data ending three Pacific days ago, website-prefix filtering, separate daily totals/detail samples, 3,000 detail-row cap and neutralized scoped CSV. Missing data stays unknown. Rotated/revoked/partial data cannot commit. Account consent and actual Google data are not fabricated.
- Daily Search Console n8n workflow som67c9baa118704c49a9183257fdba7029 imported/published and actual webhook tested: blocked/google_property_connection_required. Owner confirmed no property or OAuth client exists. Private .env fields and exact owner setup guide are ready.
- Full PostgreSQL regression: **170 passed in 345.78s**. Earlier focused integration set: 19 passed in 59.55s; extra refresh/pagination cases included in full 170. Live AI acceptance, startup helper, page rendering and n8n blocked state passed. Google-provider tests use mocked responses; real OAuth/metrics remain externally blocked.

Remaining: real Google account acceptance, six other specification workflows, verified competitor/demand discovery, content/Elementor adapters, expanded audits, reporting, financial budgets/MFA/recovery and production deployment/hardening. Four workflow definitions exist; one is account-blocked. This milestone is not full product completion.

---

# Approval, typed metadata and n8n update ? 2026-11-16

This section supersedes earlier statuses below. Operating guide: [Approval and results](METADATA_APPROVAL_AND_RESULTS_SI.md).

The reported approval issue was a self-review block: the owner last edited draft 5bb1992d..., then submitted it; no approval or attempt existed. UI now explains the block, hides invalid approve controls, names the exact target/storage and automatically polls active job status. Already-approved paused test drafts can be started by an authorized automation owner; failure rolls back unpause. The edited draft was not re-authored or self-approved.

Following explicit user-message authorization, independent assistant test drafts were approved with an audit event and actually applied/verified on the existing protected test copy: product 17 (960d6813...), homepage 0 (bbc06949...), Wide Leg category 17 (128b0565...), Women's Denim category 16 (85911ddc...). Exact title/description and noindex were verified from actual HTTP HTML. Production Site 1 remains paused and unchanged on plugin 0.1.0.

Connector 0.3.0 adds typed dynamic-home/category inventory, homepage options / category term-meta rendering, separate transactional InnoDB archive ledger, payload/target/revision binding, idempotent replay and conflict-safe restore. Static front pages continue using native post metadata. Category and post IDs cannot be confused. Tested ZIP: dist/company-seo-connector-0.3.0.zip. The private CPT mirrors both ledgers.

Real n8n research workflow imported, published and executed: sorf0b6a926a7744a329521fb8a953c59d2. It supports manual/authenticated webhook and a configured seven-day 06:00 Asia/Colombo trigger. Scoped research credentials cannot approve/publish; revocation/expiry is rechecked by queued workers. Trigger registration readiness was fixed. The newest actual run c12060f2... succeeded and returned pending-review drafts plus ai_budget_exhausted; no paid retry was made. Three workflows are now implemented; seven specification workflows remain pending. The weekly timer is configured, not elapsed-time tested.

Gemini model metadata authentication returned HTTP 200. Generation is now enabled under the existing 5-call daily organization allowance, which is already exhausted today. No valid live generation is claimed. Failed reservations count; key replacement does not reset the app allowance.

Validation: complete PostgreSQL suite 146 passed (337.83s); final focused adapter/research/assistant checks 19 passed (70.69s); approval UI and paused-test checks 8 passed (23.00s). WordPress native ledger/CPT 25 and archive 28 checks passed. PHP syntax, portable ZIP, JS stale-response protection, Django check, migration drift and OpenAPI passed. Full 146-test run preceded the final narrow UI/priority changes, covered by focused checks. Browser visual automation was unavailable.

Remaining: live connector deployment/publication, verified Google account/property/OAuth/metrics, search-backed competitor/demand provider, other workflows, content-body/Elementor editing, expanded audits, reporting/budgets/MFA/hardening. This is a completed test metadata path, not the entire platform specification.

---

# Verified current update ? 2026-11-16, Denim Yard workflow

Validation: complete PostgreSQL suite **139 passed in 258.00s**; final focused caching/staging/approval transaction checks **10 passed in 36.26s**; JavaScript late-response/edit-preservation checks passed. Django check, migration drift and OpenAPI validation passed. Browser visual acceptance has not been automated.

This section supersedes historical statements below about missing staging, credentials, keyword maps or assistant drafts. Current instructions: [Denim Yard workflow](DENIM_YARD_CURRENT_WORKFLOW_SI.md).

- Existing primary Site 1 remains Denim Yard production, paused and unchanged. Existing Site 12 is its protected child test copy, hidden from the primary portfolio. No additional customer site was created.
- VPS test copy is sanitized, authenticated, noindex, mail/outbound/checkout guarded and reader/editor connected. Public DNS is unresolved; only the explicit staging origin uses its verified certificate and fixed IP. TLS checks remain enabled.
- Fresh primary research `a5f446e1-ec8a-4160-8409-fc0c41ad9021` succeeded with five pages and two assistant drafts pending review. A transient earlier read failed; a subsequent bounded read succeeded. No generation calls were used.
- Metadata preview reads now use version-bound snapshots and durable background refresh. Fresh WordPress revision reads remain mandatory when saving and publishing. Measured cached JSON read: 14 ms. Research HTML measured 34,374 bytes versus 186,055 before (about 82% smaller); timings are local observations, not guarantees.
- The test-only publisher supports an explicit HTTPS staging host, related production parent, organization binding, separate metadata-staging queue, current permissions/approval/revision and pause checks. Production is always rejected. The app exposes human Approve & run on test copy; it does not approve on behalf of the owner.
- Existing test-copy editor has native WooCommerce object-edit capabilities; core REST mutation remains blocked. Actual staging dry-run preview passed and reported no writes. Fresh review draft: `5bb1992d-ad03-4685-a5bf-4608cfe340a0`. Actual external staging apply remains unverified until the owner approves this exact diff.
- Local fixture: 25 WordPress ledger/CPT checks plus actual HTTP concurrent replay/conflict/restore and actual Celery apply/public verification/restore passed after these changes. Fixture credentials revoked and writes disabled after checks.
- Gemini model authentication worked previously, but real generation timed out/503. Five daily reservations consumed; current AI setting is disabled. No accepted live Gemini generation. Public evidence and deterministic drafts work without AI.
- Google ownership/OAuth/metrics, search-backed competitors and demand, homepage/category/content adapters, eight remaining n8n workflows, expanded audits, budgets/MFA/reporting and production hardening remain pending. This is not a complete autonomous SEO platform.

---

# Current implementation update — 2026-11-16

This section supersedes older milestone notes below. The full product remains unfinished.

Gemini configuration follow-up (2026-11-16, Asia/Colombo): owner supplied private configuration; key/model presence verified without revealing secrets, AI enabled, and authenticated model metadata request returned HTTP 200. Four explicitly budgeted research attempts were made (one outbound generation request maximum each); no valid AI suggestions were accepted. Diagnostic attempt `2ddf9fec-627d-4a52-ab94-d3c4b1645c20` ended `provider_timeout`; after setting low thinking and a bounded 90-second timeout, `fda8b2c4-4408-4141-ab96-48a9cefc2f56` ended `provider_http_503`. This is not live-provider acceptance. Public evidence remained usable. No additional calls were sent after the 503. Safe provider status and uncertainty text are now visible in reports; response bodies/keys are not logged. Updated research/preview regression: **16 passed in 32.74s**; Django check passed. Earlier full 97-test run predates this narrow diagnostic change.

Final acceptance for this update: **97 PostgreSQL tests passed in 161.47s**; **25 WordPress metadata/CPT checks passed**; actual HTTP apply/concurrent replay/conflict/restore and actual Celery queued apply/public verification/restore passed. Temporary fixture credentials were revoked and fixture writes disabled. Django check, migration drift check and OpenAPI validation passed. Gemini's real SDK was exercised with mocked HTTP, including request serialization and strict one-outbound-request transport; no paid live provider call was made.

Actual Denim Yard read-only research `d0518659-0e33-4b7e-869b-7316de233b1b` succeeded: homepage, Wide Leg, Women's Denim, About and Contact (five pages), eight observed heading candidates, no skipped pages, zero AI calls. Report: http://localhost:8000/sites/1/research/ . Migrations 0010/0011 applied. The local 0.2.0 plugin ZIP was rebuilt and PHP syntax/archive structure verified.

- Deterministic metadata drafts, separate reviewer approval, immutable payload/source/policy bindings, durable attempts, local-only apply/status/restore, conflict checks, public HTML verification and queued worker smoke are implemented. The previous complete PostgreSQL run passed 82 tests; local WordPress ledger checks passed 22 before the CPT addition. Concurrent same-key requests and restore conflicts were tested against the disposable fixture. No live publication is enabled.
- Site 1 remains production, paused, live plugin 0.1.0 read-only. An unapproved product-89 description draft exists at `/sites/1/changes/51dde149-c177-42d2-915e-f7c0ca688083/`. The homepage is not mapped to a WordPress object; `homepage_mapping_missing` is tracked. Product metadata is not a homepage adapter.
- URL-only onboarding, bounded five-page public research, source-backed heading candidates, observations and explicit unknown metrics are implemented. Research is a PostgreSQL/Celery job; it does not overwrite owner business facts. Duplicate active runs and revoked users are checked. `recover_research` re-dispatches queued work and expires abandoned executions without paid retries.
- Google/Facebook/X/LinkedIn approximate previews are implemented in a standalone page and draft editor, with escaped HTML inspection and a protected bounded image proxy. Browser visual acceptance remains unverified.
- Official Gemini structured-profile adapter is implemented but disabled by default and not live-provider verified. The local key and model were both absent when checked (presence only; no secrets printed). One call/run, 2,048 output tokens, five reserved calls/org/day, no automatic paid retry, no model tools or publishing. These limits are not a monetary budget. CrewAI/LangGraph are not running in this milestone.
- Local plugin 0.2.0 now mirrors applied/restored metadata into the private admin-only `cseo_record` CPT. Native post metadata renders tags; the transactional ledger remains authoritative. All 25 WordPress metadata/CPT checks passed. CPT mirror reconciliation remains pending.
- Owner confirmed Draft → owner approval → staging test, private history CPT, and private local Gemini configuration. No staging copy exists yet. Owner approval does not bypass the separate-reviewer rule; a creator/last editor cannot approve their own change.
- Remaining work includes search-backed competitors, demand/keyword mapping, automated page-specific AI drafts, homepage/category/content adapters, full audit coverage, Google integrations, remaining eight n8n workflows, generalized financial budgets, MFA/recovery, reporting and production hardening. See `URL_RESEARCH_AND_PREVIEW.md` for exact current operation and limitations.

---

# Current status

2026-11-16, Asia/Colombo. **M1 passed. M2 live read connection and M7 two-workflow audit slice are verified; M3 inputs/provenance are implemented. Remaining full-platform milestones are unfinished.**

## Implemented source

- Empty workspace inspected; no pre-existing application or AGENTS.md found.
- Full attached specification preserved as PRODUCT_SPECIFICATION.txt.
- Django custom user, organization membership, org-scoped group permission bundles, site assignments and per-action grants.
- Owner role separate from Django superuser/is_staff. Site list/detail/API share authorization predicates.
- Single-use 24-hour invitation tokens stored as SHA-256 digests, password validators, session login/logout, CSRF, django-axes throttling and redacted audit events.
- Incomplete website profile onboarding, timezone validation, staff invitations/assignments/revocation, unknown-data site dashboard.
- Locally compiled Tailwind/Alpine, paginated site API, authenticated OpenAPI and request IDs.
- Compose web/worker/migrate/PostgreSQL/Redis/n8n/separate n8n DB, persistent volumes and localhost UIs. PowerShell preflight/setup/check/backup helpers.
- Read-only public-page audit: durable PostgreSQL job/idempotency/lease state, current actor checks before fetch and persistence, bounded queue (three active per site), manual Redis recovery, robots checks on each page hop, DNS-pinned public HTTP, bounded HTML extraction, deterministic issues and evidence screen. This is one page, not a sitewide audit or a WordPress connection.
- Applicability/coverage-aware health rubric is unit-tested but not presented as a site score from these limited checks.
- Site-scoped manual/CSV reference input, validation, duplicate skipping and removal; sources remain Not researched. No publishing target is created from references.
- Plugin 0.1.0 ZIP: local post title/description/OG text, canonical defaults, core robots/privacy, social text, local editor controls, conflict modes and authenticated read-only REST. No remote apply/restore/body/schema/term adapter is claimed.
- Optional local WordPress 7.1.4/PHP 8.3/MariaDB 11.4.8 fixture and synthetic custom theme; metadata persists independently of Django.

## Checks so far

- Initial docker version: engine unavailable and sandbox denied Docker config. Docker Desktop started via authorized terminal; subsequent elevated `docker version` succeeded: Docker Desktop 4.39.0, Engine 28.0.1 linux/amd64, Compose 2.33.1.
- Initial pip install blocked by sandbox sockets; authorized dependency install succeeded. Python 3.14.0.
- `python backend/manage.py check`: initially found duplicate built-in view_site permission; corrected; check now passes.
- `python backend/manage.py makemigrations platform_core`: generated initial custom-user migration. Initial host DB hostname not resolvable (expected before Compose); this is not a migrated-database check.
- `npm.cmd install`: successful, 0 reported vulnerabilities. Exact npm lockfile saved.
- `npm.cmd run build`: successful, Tailwind 4.2.1 and local Alpine asset.
- `scripts/setup.ps1`: generated ignored .env without printing secrets; preflight/config/build/migrations passed. Initial all-service boot encountered an occupied port 5678 from existing `n8n-docker-n8n-1`; left it untouched and changed this project's n8n to 5679. All eight current persistent services are healthy, migrate exited 0.
- `docker compose up -d --build --wait web worker`: clean builds/migrations successful, including 0001 custom user, 0002 references and 0003 job/page/snapshot/issue tables. Python container 3.14.0; actual n8n CLI reports 2.47.7.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`: full suite **49 passed** on PostgreSQL (latest full run 56.51 seconds); Django system check passes; no migration drift; OpenAPI validates with zero reported errors/warnings. Includes cross-org/site reads/body IDs, invitation reuse/expiry, CSRF/logout, login lockout, references/CSV limits, active-job budgets, durable idempotency, revoked queued access, duplicate delivery, robots denial, private/mixed DNS, private redirects, IP pinning/TLS host, evidence extraction and missing-data scoring. HTTP/provider calls in audit job tests are fixtures, not live-site research.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wordpress-fixture.ps1`: **13 WP checks passed**, covering read role, anonymous denial, authenticated read, draft denial, page bounds, missing write routes, renderer modes, synthetic conflict and metadata retention. First fixture attempt exited early because WP's install redirect ran; corrected WP_INSTALLING bootstrap and added required completion markers so exit 0 cannot masquerade as successful tests.
- `python scripts/smoke.py`: **passed** over real local HTTP: login, compiled CSS/Alpine, n8n health, WordPress title/description/canonical/robots/OG title exactly once and staging noindex preserved. No browser screenshots or keyboard/visual testing have run; no browser preview tool is connected.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package-plugin.ps1`: PHP 8.2.12 host syntax passes, ZIP root verified; artifact `dist/company-seo-connector-0.1.0.zip`. WordPress runtime executes PHP 8.3. Packaging has a Docker fallback if host PHP is absent.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/backup.ps1`: custom-format local DB dump saved under ignored backups/. `scripts/verify-restore.ps1`: source dumped and restored into random disposable database; **31 migration records matched**, temporary database removed, source unchanged. First verifier failed due to PowerShell nested SQL quoting; fixed by passing SQL through stdin, rerun passed.
- Restarted this project's db/redis/web/worker and waited for readiness; HTTP smoke passed afterward, WordPress fixture/data preserved. One check attempt was interrupted by the concurrent restart (exit 137); final check was rerun after restart and all 49 tests passed.
- Host PowerShell script execution was initially blocked by policy; documented process-scoped `-ExecutionPolicy Bypass` invocation. No persistent execution-policy change was made.

## Release blockers and remaining scope

The custom-theme WordPress metadata renderer and fixture REST checks are verified locally. Update: encrypted Django connection UI, live Denim Yard Application Password authentication and public inventory are now verified; see latest milestone entry below. Elementor/Canvas, archive pagination, taxonomy metadata, sitemap exclusions, schema/images/breadcrumbs/hreflang, migration adapters and real SEO-plugin interactions remain unverified/unimplemented. A synthetic Yoast constant check is not a real Yoast adapter test.

Full crawls/sitemaps/research candidate extraction, keyword metrics/maps, AI/Gemini/LangGraph, approval/publication/rollback, content adapters, Google sync, ten n8n exports, reports and MFA remain pending. MFA and secure password recovery are release blockers. Development Compose is not production-ready. No publisher exists; no publication/restore/remote exactly-once claims are made. Queue message-loss recovery is manual. Update: n8n daily read-only audit scheduling is now configured and clock-trigger verified for Denim Yard; other business schedules remain pending. DNS lookup latency is bounded only by OS resolver and worker hard timeout; proxy-level rate/egress policy and browser worker protection remain release work.

Owner must eventually supply managed/staging URLs separately from references, business facts, WordPress Application Passwords, Gemini credential/model, Google OAuth credentials/property consent and optional paid metrics/licenses. These do not block ordinary local implementation. No real customer site has been touched.

Next action: deterministic grounded draft/review and conflict-aware local apply/restore slice, remaining metadata contexts/sitemap and pinned Elementor tests. The encrypted live read connection is now verified. Then broaden public crawling/evidence and complete M3 research provenance. All M2–M8 acceptance criteria remain in IMPLEMENTATION_PLAN.md. Continue independent coding without waiting for live provider credentials.

## Local handoff

- App: http://localhost:8000 (running); n8n: http://localhost:5679 (running, separate owner setup); synthetic WP: http://localhost:8081 (running, privacy noindex).
- No product account or customer URL has been invented. Owner runs `docker compose exec web python manage.py bootstrap_owner --email you@example.com --company "Your company"`, opens the private 24-hour one-time link, then signs in. Staff are invited and assigned through UI.
- See OWNER_SETUP.md (Sinhala), API_CONTRACT.md, ARCHITECTURE.md, BACKUP_RESTORE.md, FEATURE_MATRIX.md and automation/n8n/README.md. Update: two runnable audit workflow JSON exports are now delivered and locally bound/tested; the remaining eight workflows are unfinished.

Specification integrity verified: SHA-256 of the preserved file exactly matches the original attachment (188A55D00E3AD9707A170FF5C9957BA0DF15D4FA77CCDDA69291793135BC9A08).

Latest full run exposed an unordered-pagination warning after adding real public-audit counts to website cards. Explicit name/ID ordering was added; a focused regression check promotes that warning to an error. Focused regression passed (1 passed in 3.18s, pagination warning treated as error); final OpenAPI validation and HTTP smoke also passed. All latest application containers are healthy.

Login/test guide follow-up: existing owner you@example.com was inactive with password setup pending. Added reissue_invitation for inactive invited accounts only; active accounts are refused, old invitation links expire, and no password is assigned. Targeted PostgreSQL tests: 2 passed in 3.75s. Rebuilt web/worker healthy. No real invitation was reissued by the agent; owner runs the command privately. Full walkthrough: LOCAL_TEST_GUIDE.md. Prior full suite remains 49 tests; the two new tests were run separately.

Password-setup CSRF follow-up: user reported Origin:null rejection. The prior no-referrer policy was incompatible with some CSRF flows; changed to strict-origin (origin only, no invitation path) and marked invitation responses never-cache/no-store. CSRF remains enabled and null origins remain denied; no trusted-origin bypass added. Official reference: https://docs.djangoproject.com/en/5.2/ref/middleware/#referrer-policy . Rebuilt app/worker healthy. Focused PostgreSQL tests: 6 passed in 4.49s (HTTP/HTTPS same-origin acceptance, HTTPS origin-only Referer fallback, null-origin rejection without consuming invitation, safe invitation reissue/refusal). Existing owner you@example.com remains inactive; no password/account reset performed. Owner should privately reissue a link and open it directly in a normal browser with a fresh page. Embedded-preview cause is possible, not browser-verified.

Denim Yard walkthrough/UI follow-up: read the owner request attachment. Fixed dashboard/API URL-name collision by using api-site/api-job router basenames; Open website and post-edit redirects now resolve to HTML under /sites/{id}/ rather than JSON. Added visible Edit and owner-only Delete from workspace actions with exact-name confirmation, reversible archive/restore, retained history/assignments, cancelled active audit jobs and hidden archived site/job API access. Added migration 0004_site_archived_at and field-level onboarding help. No actual customer website operations and no actual Denim Yard archive/delete performed. Public web fetch of denimyard.com could not be verified; product/market/CMS facts are not invented. Detailed Sinhala instructions: DENIM_YARD_WALKTHROUGH.md, linked from OWNER_SETUP.md. Local build/migrations/health passed; Django check and migration drift check passed; full PostgreSQL/component suite 59 passed in 72.49s; OpenAPI validation succeeded. n8n business workflows and Django-to-WordPress connection remain pending, not misrepresented as configured.

## Denim Yard live-read and n8n milestone (2026-11-16)

- Owner confirmed WordPress/WooCommerce, Sri Lanka, English, Wide Leg/Women?s Denim, COD, shipping setup unfinished and PayHere planned. Updated the existing site profile from those facts; Production environment and publishing pause retained. Six bounded robots-allowed public pages plus an owner-provided source stored with provenance. Conflicting public delivery/installment/exchange claims are not promoted to verified facts.
- Added SiteConnection/KnowledgeSource, separate Fernet key generation, encrypted credential UI, strict public HTTPS/pinned DNS/no Authorization redirects, revocation, capability validation and bounded public inventory. No credentials serialized or echoed. Owner entered the real credential privately through UI; live connection reports WP 7.1.4/plugin 0.1.0/standalone/remote_write=false. Live inventory read returned 22 records (23 stored URLs including prior audits); no orders, prices, stock, checkout, metadata or content writes.
- Added AuditSchedule/ServiceCredential, 30-day site-scoped bearer auth, dedicated unusable-password service actor with view_site/run_audit only, service-token rechecks in queued workers, due row locking/idempotency, next_due advancement, pause/revoke UI and safe runtime n8n credential import helpers.
- Tracked two inactive-by-default exports: onboarding_initial_audit.json and scheduled_audit.json. Installed n8n HTTP Request default version 4.5 inspected; imported 4.2 node compatibility verified by live execution. Runtime IDs/credential bindings ignored; secrets passed in memory through stdin to mode-0600 ephemeral import files, removed afterward, stored encrypted by n8n. No account credential IDs/secrets in exports.
- Initial n8n CLI execution did not produce a verified result; replaced acceptance with the running server's authenticated webhook. Successful initial live job: 29e9d983-90f4-48b8-b8ea-a37b40f18d10 (HTTP200, title Denim Yard, description_missing). Authenticated due dispatch also ran. Published read-only workflows; daily audit (1440 minutes), one-minute internal due checks; no Celery Beat schedule.
- Real Schedule Trigger ? scoped Django API ? Celery ? Denim Yard evidence verified: job 43bebc6b-c94a-4a48-a2bd-c7ed49771c55 succeeded. scripts/test-n8n-schedule.ps1 passed. Public source was read only; no customer-site mutation.
- Full Django/PostgreSQL suite: 70 passed in 102.79s; system check, migration drift and OpenAPI validation passed. Migrations 0005/0006 applied. Dedicated connection/automation tests previously 11 passed; real local WP HTTP Application Password, encrypted storage and 3 fixture inventory records verified, temporary app records rolled back and temporary WordPress password revoked. One fixture attempt initially failed until explicit local query-style REST routing was corrected.
- End-to-end facts guide: DENIM_YARD_CONNECTION_AND_AUTOMATION.md. Remaining scope: full crawl/research/map, AI/budgets/checkpoints, review/immutable approval, plugin apply/status/restore ledger and public verification, content adapters, Google metrics, eight dependent workflows, outbox/inbox/generalized multi-site dispatch, MFA/recovery/reporting/hardening. These milestones are not marked complete. No staging copy exists yet; develop writes against the disposable WP fixture before real-site publication.


Final credential-binding hardening: SiteConnection credentials are bound to their saved base URL. A site-profile URL edit cannot forward the existing Authorization to another domain/path; it returns url_changed and requires explicit credential re-save. Migration 0007 binds the existing verified record without exposing secrets. Final connection/automation regression: 12 passed in 23.88s, including URL-change no-network proof, actual private-IP rejection, service scope/revocation and due deduplication. Django system check, migration drift and OpenAPI validation pass; local WordPress real HTTP auth smoke passes again. Live Denim Yard connection remains connected with bound target matching, remote writes false and publishing paused. All three latest service audit jobs succeeded. Daily schedule enabled; next_due 2026-11-17 13:32:01 Asia/Colombo, processed by the next minute dispatcher tick. Earlier full suite was 70 passed; the final 12 are focused overlapping regression tests, not 12 additional distinct passing tests on top of 70.
