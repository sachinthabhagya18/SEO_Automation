# Denim Yard — verified connection and audit automation

Updated 2026-11-16. This supersedes earlier instructions saying the WordPress connection screen and all n8n exports were unavailable. The full platform specification is still in progress; only the capabilities below are claimed.

## Owner-confirmed profile

The owner confirmed WordPress/WooCommerce, Sri Lanka, English, Wide Leg and Women’s Denim categories, Cash on Delivery, unfinished shipping setup, and PayHere planned rather than active. These facts are saved in the existing Denim Yard profile (site 1). Its environment is Production because the supplied URL is the live store; publishing remains paused.

Public robots policy and six allowed pages were fetched through the DNS-pinned bounded HTTP client: homepage, Our Story, delivery/exchange policy, Contact Us and both category pages. Limited excerpts, titles, source URLs, hashes and timestamps are stored as public observations, separate from owner-provided facts. Public banners mention delivery thresholds/installments/exchanges; these are not treated as verified payment/shipping facts when owner setup is unfinished. Review those live statements manually before relying on them in drafts.

## Current screens

- Overview: http://localhost:8000/sites/1/
- Business profile: http://localhost:8000/sites/1/edit/
- Encrypted WordPress connection, reported capabilities, inventory and evidence: http://localhost:8000/sites/1/connection/
- Schedule/service revocation/automation jobs: http://localhost:8000/sites/1/automation/
- n8n: http://localhost:5679

## Verified WordPress connection

The owner entered the dedicated account/Application Password through the new connection form. The server verified WordPress 7.1.4 and Company SEO Connector 0.1.0, standalone rendering, protocol v1 and remote_write=false. Credentials are encrypted using a separately generated Fernet key and never included in normal APIs, prompts or HTML. The live public inventory read returned 22 records; 23 URLs were stored including prior public-audit history. These are page/product records, not 22 confirmed products. Prices, stock, orders, checkout and SEO tags were not changed.

Credentials are bound to the saved base URL; editing the site URL blocks the old credential until explicitly re-saved. Connection commands follow no redirects with Authorization and require public HTTPS. A fixed `http://wordpress` exception is available only for explicitly enabled DEBUG/local fixture checks; it does not weaken the public crawler. Authentication failures and revoke states remain distinct from successful connection.

Use Save encrypted credentials to rotate credentials, Test read connection to verify, Read public inventory to sync at most 75 records, and Revoke local connection to stop local access. Also revoke the Application Password in WordPress when retiring it. Do not send the password through chat.

## n8n audit workflows

Two parameterized exports exist, with no secrets or user-specific credential IDs:

- `automation/n8n/onboarding_initial_audit.json`: authenticated/manual request → site parameters → enqueue idempotent audit → bounded wait/poll → actual job result.
- `automation/n8n/scheduled_audit.json`: Schedule Trigger (every minute) or authenticated request → Django due-dispatch API.

Exports remain inactive by default. The local Denim Yard instance has runtime credential bindings and published workflows after authenticated live testing. Runtime IDs are stored only in ignored `.local-bindings.json`. This initial one-site setup binds the credential to Denim Yard; generalized multi-site dispatch remains future work. No workflow is cloned per website in the tracked exports.

Django owns `next_due`; n8n only checks due work every minute. Denim Yard's page audit interval is 1440 minutes (daily). A future tick before next_due performs no WordPress fetch. Overlaps use a database-locked due schedule and durable job idempotency. Missed times create one bounded audit rather than a backlog storm. No Celery Beat business schedule exists.

The real clock-triggered job 43bebc6b-c94a-4a48-a2bd-c7ed49771c55 succeeded; all three latest automation jobs are successful. Next due is 2026-11-17 13:32:01 Asia/Colombo (the next minute dispatcher tick processes it).

The service user has only view_site/run_audit on the assigned site, an unusable login password and a 30-day revocable token. Service tokens cannot approve/publish, administer users or call the browser session API. Worker claim and persistence both recheck user/site access and service-token activity/expiry. Revoke audit service access on the Automation screen to block new dispatch and queued service execution.

## Verified live result

The authenticated initial n8n workflow executed against Denim Yard and returned:

```json
{
  "job_id": "29e9d983-90f4-48b8-b8ea-a37b40f18d10",
  "state": "succeeded",
  "scope": "single_public_page_head_checks",
  "observed": {
    "title": "Denim Yard",
    "description": "",
    "status_code": 200,
    "issues": [{"code": "description_missing", "severity": "medium"}]
  }
}
```

Open http://localhost:8000/jobs/29e9d983-90f4-48b8-b8ea-a37b40f18d10/ after login. This proves a limited public-page audit, not full-store coverage, Google indexing/rank, sales attribution, or successful publication. No missing data is replaced with invented scores/traffic.

## Reproducible checks and setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-wp-connection.ps1
```

The latter creates a temporary local fixture Application Password, verifies real HTTP authentication/capabilities/inventory in rolled-back app records, and revokes the temporary password. It does not use the live site's password.

Reimport/rebind the local audit workflows only when needed (this rotates the prior service token):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-n8n-audit.ps1 -SiteId 1
```

To explicitly publish and live-test the read-only flows and configure a daily audit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-n8n-audit.ps1 -SiteId 1 -TestAndEnable
```

Do not run this just to view results; it has already been configured for this example. The UI can pause the audit schedule or revoke access. Changing the publishing pause does not alter the explicitly separate read-only audit schedule.

## Key management

`.env` contains `CONNECTION_ENCRYPTION_KEYS`, separate from Django and n8n secrets. Keep it backed up securely. MultiFernet accepts a new first key plus old decrypt keys; re-save each connection under the new key before removing old keys. Losing all applicable keys makes stored credentials unreadable. No secret is committed to workflow JSON or this guide.

## Remaining work

Full crawls and keyword research/maps, Gemini/AI budgets and checkpoints, immutable review/approval, safe plugin apply/restore ledger, public verification/rollback, Elementor content adapters, GSC/GA4/performance, eight other dependent workflows, reporting, MFA and release hardening remain unfinished. WordPress connection success and a daily public audit do not mean these features are implemented. No staging copy exists yet; use the local WordPress fixture for upcoming write-path development and establish staging before live publishing.
