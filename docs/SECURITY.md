# Security model

An active membership is required for every product permission. Company owners administer only their organizations. Staff receive per-site bundle permissions and optional explicit grants. Django superuser/is_staff does not imply product membership. Assigned sites do not imply every action. Approval and publication remain separate permissions. Cross-organization assignments fail validation and query authorization checks both membership and bundle organization.

Browser authentication uses Django sessions and CSRF, password validators, POST logout, password-change session rotation and django-axes login throttling. Invitations store token digests, expire after 24 hours and are consumed transactionally. Bootstrap takes a PostgreSQL advisory transaction lock and only runs on an uninitialized organization database. Private invitation URLs are intentional one-time owner output, never application audit fields. Do not put them in shared logs. No SMTP sends occur.

New sites start paused. There is no publisher in M1. Every future worker write must recheck current actor activity, membership, site/action permissions, pause, policy version and connection capabilities immediately before remote operations. Export/file/provider/job paths need independent boundary tests before release. Profile facts are currently owner-entered text, not approved source evidence.

Production release is blocked on tested TOTP MFA, recovery, hardened deployment, application-only database roles, encrypted integration storage with key rotation, SSRF-safe crawl transport, durable job recovery and the publication tests in the specification. Development DB uses the initialized PostgreSQL role (which can create the disposable pytest database); it must be replaced by a restricted runtime role for production. Never expose runserver or DEBUG to customers. Production cookies/HTTPS are enabled when DEBUG=false, but production proxy/static configuration is not delivered yet.

`.env`, uploads, backups and caches are ignored. Keep backup dumps encrypted and access restricted. No secrets belong in AI prompts, API serializers, workflow exports or audit events. No real customer accounts or URLs have been configured.


Connection/automation update: connection credentials now use separate-key Fernet/MultiFernet encryption and never render back to HTML/API. HTTPS connector GETs pin DNS, do not redirect Authorization and bound response sizes/time. The fixed wordpress local-host exception is DEBUG-only and separate from public transport. Key rotation requires retaining old decrypt keys until connections are re-saved; no secrets are printed by setup/import helpers.

n8n audit credentials are scoped to one site and view_site/run_audit, expire in 30 days and have no publishing/approval/admin scopes. Dedicated service actors have unusable passwords. Revocation/expiry is rechecked at queued task execution and result persistence. The same scoped read-only audit credential authenticates local n8n audit webhooks; it does not authorize ordinary browser API access. Other workflows, outbox/inbox and generalized multi-site service grants are pending.

Credentials are additionally bound to the saved site URL. Profile URL edits produce url_changed and block outbound Authorization until an integration manager explicitly re-saves credentials. The regression test asserts no network call occurs after a URL change.
