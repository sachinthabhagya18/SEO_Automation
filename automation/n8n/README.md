# n8n audit integration

Pinned n8n 2.47.7 runs at http://localhost:5679. The unrelated instance on 5678 is untouched.

Two tracked parameterized workflows are implemented:

- onboarding_initial_audit.json: manual/authenticated webhook ? site parameters ? scoped Django audit API ? bounded wait/poll ? actual result. Poll interval grows from 2 to 10 seconds, maximum 12 continuation checks, 180-second workflow timeout.
- scheduled_audit.json: every-minute Schedule Trigger/authenticated webhook ? scoped due-dispatch API. Django owns next_due and the daily interval; no remote page fetch occurs when not due.

Exports contain no secrets or user-specific credential IDs and are inactive by default. scripts/setup-n8n-audit.ps1 binds runtime encrypted httpHeaderAuth credentials and local workflow IDs. Runtime bindings are ignored. Optional -TestAndEnable publishes only the read-only audit workflows after local configuration and tests the authenticated live flow. scripts/test-n8n-schedule.ps1 verifies a real timer-triggered audit, not just JSON import or manual execution.

The Denim Yard example is configured/published and verified through authenticated webhooks AND an actual Schedule Trigger ? Django ? Celery ? live public evidence. Its read-only audit is daily; dispatcher checks due work every minute. Site-scoped service tokens have 30-day expiry, revocation and no approval/publication powers. This first-site binding is not a completed generalized multi-site dispatcher.

Inside Docker use http://web:8000, not localhost. Inbound workflow requests use header authentication; service tokens cannot bypass Django authorization. The app Automation screen disables schedules/revokes service access. Publishing pause remains separate from explicitly enabled read-only audits.

Remaining eight workflows are not exported as fake runnable integrations: daily_search_metrics, reference_keyword_research, content_opportunities, approved_change_dispatch, post_publish_verification, regression_monitor, monthly_report and workflow_error_handler. Their business endpoints/outbox/inbox, providers and publishing flows must be implemented first.

An early CLI execute attempt did not produce a verified result; the final tests use the running n8n server's authenticated webhook and real clock trigger. Only those successful runs are claimed.

The official source license was inspected: https://github.com/n8n-io/n8n/blob/master/LICENSE.md . Keep this internal; client-facing access/embedding requires checking the concrete use and applicable terms. No Enterprise entitlement is assumed.
