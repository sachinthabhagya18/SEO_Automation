> **2026-11-17 current update:** Gemini 3.5 Flash-Lite passed a real generation/research run. Google OAuth/property/metrics code and its n8n flow are implemented; real Google account setup is required. Read [today's results and next steps](NOV17_PROGRESS_SI.md) and [Google setup guide](GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md). Older dated statements below are historical.

# Current setup update ? 2026-11-16

The protected existing test copy has now been provisioned on the authorized VPS and linked beneath Denim Yard (Site 1 ? Site 12). SSH host key was verified from the owner's trusted console. Production files/database remain unchanged. Public staging DNS remains unresolved; app testing uses the explicit verified-certificate private origin route. Do not follow obsolete provisioning/pending-access statements below as a request to create another site. Google property ownership still needs the owner's Google account action. See [current workflow](DENIM_YARD_CURRENT_WORKFLOW_SI.md).

# Denim Yard: Hetzner / Virtualmin / Cloudflare / Search Console

Owner-confirmed hosting: Hetzner VPS, Virtualmin, Cloudflare DNS. Server address supplied: `178.105.120.198`; panel link supplied: `https://fortis.convesco.com:10000/net/list_dns.cgi`.

## Server access

Trusted console fingerprint confirmed by owner:

```text
SHA256:CHMTf8pRoDzSt753ZHRkR25en/MzGvyRbKkQbYkJ/Yg (ED25519)
```

The verified host entry is in ignored `.local/ssh/known_hosts`. The existing local SSH identities were refused (`Permission denied (publickey)`). A dedicated Ed25519 key was prepared in `.local/ssh/denim_staging_ed25519`, with private-key ACL restricted to the Windows user. Its public half ends in `.pub`; only that public half is to be added to the server. Never paste the private file into chat or upload it to WordPress. `.local/` is excluded from source tracking/build context.

The owner was given the exact append-only console command to authorize the public key with `restrict` (no forwarding/PTY; SSH command execution remains available). After that one server authorization, read-only access can be checked from this project folder:

```powershell
ssh -i .local/ssh/denim_staging_ed25519 -o IdentitiesOnly=yes -o UserKnownHostsFile=.local/ssh/known_hosts -o StrictHostKeyChecking=yes -o BatchMode=yes root@178.105.120.198 "id -un"
```

`scripts/vps-staging-preflight.sh` is prepared for read-only inventory. It checks server identity, confirms the exact managed source domain and whether staging already exists. It never reads wp-config, prints credentials, clones or edits a server. Remote execution remains pending until key authorization works.

## Concrete staging target

- Source: live `https://denimyard.com/`.
- Proposed target: `https://staging.denimyard.com/`, separate Virtualmin webroot and database; inspect any existing target before reuse.
- Inspect Virtualmin version/features and available disk before choosing clone tooling. [WP Workbench](https://www.virtualmin.com/docs/plugins/wp-workbench/) is Pro-only; do not assume it is installed/licensed. If absent, use a reviewed backup/restore or WP-CLI-based copy after resolving actual paths and separate database credentials. No blind clone command has been executed.
- Protect staging before copying store data: restrict access, prevent indexing, isolate mail/webhooks/payment integrations and background jobs. Copied production orders/customer data must not be exposed on a public staging hostname. For SEO testing, use sanitized data/public content where practical.
- In the staging WordPress config use `WP_ENVIRONMENT_TYPE=staging`; configure noindex and control staging cron/outbound integrations. Do not change the live environment flag or its checkout/mail settings.
- Add only the staging DNS record in the existing Cloudflare zone after the origin/vhost is ready; retain live apex/www/MX/TXT records. Set up valid origin HTTPS before routing public staging traffic.
- Install local connector 0.2.0 on staging and create a dedicated scoped Application Password. Keep initial connection read-only. The app currently permits outbound mutation only to the fixed local fixture; staging mutation support needs its own explicit tested policy change and is not enabled merely by setting a URL.
- Test drafts/apply/HTML verification/conflict/restore on staging before production rollout. Do not restore a whole staging database onto the live WooCommerce store after new live orders exist; deploy only reviewed supported SEO changes.

No VPS/domain/DNS mutation has been performed in this update. SSH access is the actual current dependency for completing the server-specific setup.

## Search Console — new assisted setup in the app

Open http://localhost:8000/sites/1/google/ with the company owner account:

1. Open [Google Search Console](https://search.google.com/search-console/welcome) and sign into the Google account that should own the store.
2. Add a **Domain** property: `denimyard.com` (no scheme/path).
3. Copy the Google-issued `google-site-verification=...` TXT value into the app's setup form. No invented token or API key is accepted there.
4. Cloudflare → denimyard.com → DNS → Records → Add record: type TXT, name `@` (zone apex), value exactly the Google-issued value, TTL Auto. Keep existing records. [Cloudflare DNS instructions](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/).
5. Select **Check public TXT record** in the app. It makes a bounded public DNS-over-HTTPS read and reports whether the exact record is observed. It does not write DNS.
6. Return to Google and click **Verify**. Google decides ownership; app DNS observation is not that approval. Keep the token after verification. [Official ownership instructions](https://support.google.com/webmasters/answer/9008080).

No Google/Cloudflare account session with property-creation/DNS-write access is connected here. Plugin discovery found reporting-oriented integrations but did not provide an already connected way to perform this ownership setup. This update has not created a property, changed DNS, authorized OAuth or imported search metrics. The application-side Google authorization/data connector remains future work after property setup.
