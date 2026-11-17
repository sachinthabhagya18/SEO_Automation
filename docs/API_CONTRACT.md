# Google and AI bridge additions - 2026-11-17

Session+CSRF manage_integrations: /sites/{id}/google/connection/ POST connect/properties/select/disconnect. GET /integrations/google/callback/ validates single-use state, same session/actor/site/client/version and expiry. Callback codes are redacted in server logs and never included in login redirect next URLs. Tokens encrypted; read-only webmasters scope.

/sites/{id}/analytics/ requires view_analytics. POST additionally requires sync_search_metrics and a durable UUID event key. /analytics/export/ requires view_analytics + export_report and a current successful snapshot; CSV cells neutralized.

Search-metrics bearer: POST /api/v1/automation/search-dispatch/ accepts site_id/event_id only. Missing Google property returns run_id:null,state:blocked,error_code:google_property_connection_required. GET /api/v1/automation/search/{uuid}/ is site-scoped. This credential cannot authorize Google, approve/publish, generate AI or use research/audit service scopes.

POST /sites/{source}/research/proposals/{id}/test-copy/ accepts a related visible target_site. An unchanged validated Gemini proposal, fresh target evidence/revision and new draft are required. Origin audited and repeat preparation idempotent; no approval copied.

# Typed target and research automation additions

- Connector GET contexts returns bounded dynamic-home/category inventory. GET contexts/{home|category}/{id}/seo returns a target-specific revision and metadata. The same prefix scopes changes/{preview|apply|uuid|uuid/restore}; ID 0 is only a dynamic home. Post routes remain unchanged. Separate SQL ledger/row locks prevent post/term ID confusion.
- Page.target_kind binds drafts, cache snapshots, immutable approval payloads (non-post only) and receipt validation. Old native-post approvals preserve their existing hash format.
- GET /sites/{site}/changes/{uuid}/status/ is scoped/private and never performs writes.
- POST /api/v1/automation/research-dispatch/ accepts site_id, event_id, optional use_ai only; deterministic event UUID and active-run reuse prevent duplicate work. Research-only service auth cannot reach audit/approval/publication endpoints. GET /api/v1/automation/research/{uuid}/ returns bounded status/draft links; drafting continues until mapped proposals are materialized or fail explicitly.
- Each research token is site-scoped, revocable and expires after 30 days. Rotation preserves separate audit tokens. Workers recheck revocation/expiry before research/AI/materialization. Model call reservations remain shared across all org actors.

# Current metadata read endpoints

- `GET /sites/{site}/pages/{page}/metadata/`: authenticated, view_site + edit_draft; bounded saved snapshot only when current verified connection credential version and bound URL match. Private/no-store; never calls WordPress synchronously.
- `POST /sites/{site}/pages/{page}/metadata/refresh/`: same scope + CSRF; 202 durable deduplicated background read, 409 if no verified inventory connection. Worker checks actor and credential version before and after network access. `recover_metadata_reads` redispatches queued requests and expires abandoned running work.
- `GET /sites/{site}/research/?run={uuid}`: one scoped full report plus lightweight history; malformed/foreign IDs rejected.
- `POST /sites/{site}/changes/{uuid}/action/`, `operation=approve_test`: human current approval, publish and automation permissions; explicit related staging target only. Transactionally approves exact payload, unpauses only that test copy and queues its operation. Failure rolls back approval/unpause. Production is rejected.

Cached reads never replace fresh revision checks for draft save/publication. No credentials are returned by these endpoints.

# Current browser workflow additions

Authenticated session + CSRF, with current per-site permission checks:

- `GET/POST /sites/discover/`: owner URL-only onboarding; creates/reuses a paused profile and queues public-only research.
- `GET/POST /sites/{id}/research/`: scoped research reports and explicit research enqueue. Optional Gemini requires configuration plus research/AI permissions; it does not publish.
- `GET/POST /sites/{id}/preview/`: approximate editable Google/social previews; optional protected own-site public HTML fetch.
- `GET /sites/{id}/preview/image/?url=...`: authenticated public-network/robots-checked bounded raster proxy. Query credentials, SVG and redirects are refused.
- `/sites/{id}/changes/`, `new/`, `{uuid}/`, `{uuid}/edit/`, `{uuid}/action/`: scoped manual/rule-based drafts, submit, separate approval/rejection, local-only apply/restore and public reverify. These are browser routes, not a new bearer publication API.

Local plugin **0.2.0** additionally implements POST `/changes/preview`, POST `/changes/apply`, GET `/changes/{uuid}`, POST `/changes/{uuid}/restore`. UUID idempotency, expected revision, separate write/restore capabilities and local/staging write switch are required. Django outgoing mutation is restricted to the fixed disposable `http://wordpress` fixture. Live Denim Yard remains plugin **0.1.0**, read-only. Private CPT history has no public REST endpoint. Older 0.1-only statements below describe that live version, not current local source.

---

# Implemented API v1

## Audit automation service API (implemented)

These endpoints use a separate site-scoped `Authorization: Bearer ...` credential; browser sessions are not accepted. Tokens have 30-day expiry, revocation, an unusable-password service actor and only view_site/run_audit permissions. The regular browser API does not accept these tokens.

- POST `/api/v1/automation/audit-dispatch/`: `{ "site_id": 1, "event_id": "a durable event identifier" }`; 202 with job_id/state. Body IDs must equal the token's site; extra fields are rejected. Stable event IDs map to durable job keys.
- POST `/api/v1/automation/dispatch-due/`: empty body; token selects the site. Django locks the schedule, accepts one due job and advances next_due. Disabled/not-due returns state=not_due without fetching WordPress. Daily interval is separate from n8n's one-minute internal due checks.
- GET `/api/v1/automation/jobs/{uuid}/`: current same-site state/error and observed title/description/status/issues when available. Inaccessible jobs are 404. No connection secrets are exposed.

Service-token activity/expiry, actor permissions and archived-site status are checked again by the worker before network work and persistence. These tokens cannot approve or publish changes. See automation/n8n for the two actual read-only audit workflows; other operations are not exposed as placeholder success.

## WordPress connection UI (implemented)

`/sites/{id}/connection/` requires current manage_integrations permission and CSRF on browser POSTs. It saves/rotates encrypted credentials, tests read-only capabilities, syncs at most 75 public records and revokes local access. Authenticated HTTPS requests pin public DNS, reject all redirects and bounded-invalid responses. Only the fixed, explicit DEBUG WordPress fixture can use local HTTP. Secrets are never normal API fields. `/sites/{id}/automation/` requires manage_automation for schedule/revoke controls.

Browser dashboard routes and API routes have distinct names (`site-detail` versus `api-site-detail`, `job-detail` versus `api-job-detail`). Browser Open website/edit-save redirects resolve to HTML under `/sites/{id}/`; `/api/v1/sites/{id}/` deliberately remains JSON. Archived websites and their jobs disappear from normal UI/API querysets; owner-only archive/restore pages retain history and never touch the remote website.

Session-authenticated endpoints require an active user; browser writes require CSRF. Schema is available to authenticated users at `/api/v1/schema/`. Lists are paginated (`count`, `next`, `previous`, `results`), default 25. Every response gets a server-generated `X-Request-ID`. Credentials are never serialized.

| Endpoint | Behavior |
|---|---|
| GET /api/v1/sites/ | Only sites with current view_site access |
| GET /api/v1/sites/{id}/ | 404 for inaccessible objects |
| POST /api/v1/sites/{id}/public-audit/ | Current run_audit required; body only `{ "idempotency_key": "a client-generated UUID" }`; 202 with job_id/state/scope/created |
| GET /api/v1/jobs/ | Jobs for currently visible sites |
| GET /api/v1/jobs/{uuid}/ | Poll queued/running/succeeded/failed/cancelled; error_code is redacted |

Unknown body IDs on submission are rejected. A site's URL is selected server-side. An idempotency key reused for another target hash fails; same payload returns the existing job. Three active jobs per site maximum, coordinated under a PostgreSQL row lock. `succeeded` means limited checks executed, not that SEO passed or WordPress is connected. The job view shows critical HTTP findings even if execution completed.

The worker rechecks actor authorization before network access and before saving evidence, claims a six-minute lease transactionally, and ignores duplicate delivery with an active/completed claim. A lost Redis message can be redispatched using `docker compose exec web python manage.py recover_jobs`. This is manual internal recovery, not a duplicate business schedule. Publication jobs are not implemented.

Poll at 2 seconds initially, then 5–15 seconds, stop at a terminal state or 5 minutes. Polling cannot authorize a write. Browser job screen currently provides an explicit refresh button. Worker task hard limit is 300 seconds. Unexpected errors produce a safe generic code rather than a stack trace in the UI.

## WordPress company-seo/v1 (0.1.0)

HTTPS + dedicated WordPress Application Password, or standard authenticated REST cookie/nonce for WP UI. An explicit isolated-local flag permits HTTP only in the disposable fixture. Every route has a permission callback. `company_seo_reader` has read access without content/plugin/user/theme administration.

- GET /capabilities: protocol/plugin/WP versions, mode, detected theme/Elementor, conflicts, supported operations and explicit unsupported list. remote_write=false, restore=false.
- GET /health: authenticated ready/writes_enabled=false.
- GET /pages?page=1&per_page=25: published, password-free public post types, bounded to 100 per page.
- GET /pages/{id}/seo: stored local fields, SHA-256 revision, provenance, schema version. Effective frontend values require HTTP verification.
- GET /pages/{id}/content-map: detected readonly builder and empty editable_fields. No body save path claimed.

Preview/apply/change status/restore routes do not exist yet. The durable remote publication ledger belongs to M4. Unknown private/draft objects return 404 unless an authenticated reader also has the relevant object-edit capability. No arbitrary meta, SQL, filesystem or shell endpoint is exposed.
