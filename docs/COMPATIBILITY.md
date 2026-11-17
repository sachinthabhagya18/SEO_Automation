# Compatibility and official references

Selected versions are pinned in requirements.lock, package-lock.json and Compose. Installed does not mean container-tested; see STATUS for exact checks. Docker images are pinned tags; digest attestation and production security review remain release work.

| Component | Selection | Evidence |
|---|---|---|
| Host | PowerShell 5.1, Python 3.14.0, Node 22.14.0 | Detected locally |
| Docker | Desktop 4.39.0 / Engine 28.0.1 / Compose 2.33.1 | Engine reachable after Desktop launch |
| Django | 5.2.19 LTS | Installed; [official supported releases](https://www.djangoproject.com/download/) lists 5.2 LTS through April 2028 |
| DRF | 3.16.1 | Installed; [official 3.16 announcement](https://www.django-rest-framework.org/community/3.16-announcement/) documents Django 5.2 support |
| Python container | 3.14.0 slim-bookworm | Clean build and container tests passed |
| PostgreSQL | 17.6-bookworm | 49 integration/unit checks passed; no SQLite substitute; disposable restore passed |
| Redis / Celery | 7.4.6-alpine / 5.6.3 | Worker broker ping/health passed; job execution tested with fixture HTTP; [official broker setup](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) |
| Tailwind / Alpine | 4.2.1 / 3.15.8 | npm install/build passed; [official Tailwind CLI](https://tailwindcss.com/docs/installation/tailwind-cli) |
| n8n | 2.47.7 | Two audit imports, authenticated live execution and real Schedule Trigger verified; installed HTTP Request default 4.5 supports tested 4.2 export nodes. [Official Docker page](https://docs.n8n.io/hosting/installation/docker/). |
| WordPress / MariaDB / PHP | 7.1.4 / 11.4.8 / 8.3 | Isolated fixture: 13 plugin checks and rendered custom-theme output passed; [official image tags](https://hub.docker.com/_/wordpress) |
| Elementor | Not installed/tested | No supported body widget or Canvas versions claimed |
| Gemini / LangGraph / Google | Pending M4/M6 | No live-tested adapter claims |
| Cryptography | 49.0.0 | Fernet/MultiFernet encrypted connection tests, Linux container build and actual WordPress auth passed |

n8n license: historical documentation URL redirected to a missing page. The [official source license](https://github.com/n8n-io/n8n/blob/master/LICENSE.md) was subsequently inspected; it limits use to internal business/noncommercial/personal purposes and separately restricts Enterprise code. This instance is internal only; client-facing/embedding use must be checked against concrete deployment terms. No SaaS embedding rights or free paid features are assumed.
