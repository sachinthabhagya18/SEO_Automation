> **2026-11-17 current update:** Gemini 3.5 Flash-Lite passed a real generation/research run. Google OAuth/property/metrics code and its n8n flow are implemented; real Google account setup is required. Read [today's results and next steps](NOV17_PROGRESS_SI.md) and [Google setup guide](GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md). Older dated statements below are historical.

> Current Denim Yard approval, verified homepage/category results and operating steps: [current guide](DENIM_YARD_CURRENT_WORKFLOW_SI.md). This supersedes older staging/publisher statuses below.

# වත්මන් system එක පරීක්ෂා කිරීම — 2026-11-16

**සම්පූර්ණ SEO automation platform එක තවම අවසන් නැහැ.** Local research, preview, manual/rule-based drafts, review සහ local WordPress apply/restore කොටස් පරීක්ෂා කර තිබෙනවා. Live Denim Yard වෙත SEO publishing තවම enable කරලා නැහැ. Gemini config access check එක pass වුණත් actual generation test එක timeout/HTTP503 නිසා pass නැහැ.

## 1. දැනට ඇති තත්ත්වය

| කොටස | තත්ත්වය | ඔබ බලාපොරොත්තු විය යුතු දේ |
|---|---|---|
| Login, website profiles, site permissions | Implemented/tested | Existing owner account එකෙන් login |
| Denim Yard WordPress connection | Connected, read-only | Plugin 0.1.0; public inventory කියවීම |
| URL-only onboarding | Implemented | Paused profile සහ research job |
| Public research | Implemented, සීමිත | උපරිම same-origin HTML pages 5ක්; source excerpts සහ heading candidates |
| Full SEO audit/score | Unfinished | Partial evidence වලින් complete score නැහැ |
| Search/social preview | Implemented | Approximate Google/Facebook/X/LinkedIn preview; browser visual acceptance තවම ඔබ පරීක්ෂා කළ යුතුයි |
| Gemini profile suggestions | Configured; generation unverified | Latest `provider_http_503`; valid suggestions තවම ලැබී නැහැ |
| Manual/rule-based metadata drafts/review | Implemented/tested | Save draft, submit, වෙනම reviewer approval |
| Local plugin apply/status/restore/CPT | Fixture tested | Plugin 0.2.0 සහ private history; live site update එකක් නොවේ |
| n8n | Audit workflows 2ක් verified | Initial public audit සහ daily scheduled public audit; interval 1440 minutes |
| Competitors, search demand, keyword maps | Unfinished | Competitor/ranking/volume data ලෙස heading candidates සලකන්න එපා |
| Page-specific AI drafts, homepage/category/content adapters | Unfinished | Research එකෙන් approved publish-ready SEO සියල්ල සෑදෙන්නේ නැහැ |
| GSC/GA4/PSI/CrUX, reports, remaining 8 workflows | Unfinished | Search traffic/sales/rank improvements තහවුරු කර නැහැ |
| MFA/recovery/production hardening | Unfinished | Production release එකක් ලෙස සලකන්න බැහැ |

මීට පෙර full PostgreSQL suite එකේ tests 97ක් pass වුණා. ඊට පසු Gemini diagnostics වෙනස්කම් සඳහා focused tests 16ක් සහ අවසන් model-parameter වෙනසට අදාළ tests 6ක් pass වුණා. මේවා එකතු කර unique tests 119ක් යැයි කියන්නේ නැහැ. WordPress metadata/CPT checks 25ක් සහ සැබෑ local HTTP/Celery apply/restore checks pass වුණා.

## 2. Services start කිරීම

Docker Desktop → Linux containers running තත්ත්වයට ගන්න. VS Code PowerShell terminal එකේ:

```powershell
Set-Location "G:\MY Project\DJANGO Project\SEO_Automation"
docker compose up -d --wait
docker compose ps
```

Expected: web, worker, db, redis, n8n සහ n8n-db running/healthy. `migrate` සාර්ථකව අවසන් වීම සාමාන්‍යයි; ඒක දිගටම running service එකක් නොවේ. දැනට latest build තිබෙන නිසා නැවත build අවශ්‍ය නැහැ.

Code updates පසු rebuild අවශ්‍ය නම්:

```powershell
docker compose up -d --build --wait
docker compose exec web python manage.py migrate --noinput
```

URLs:

- Application: http://localhost:8000
- Readiness: http://localhost:8000/health/ready/ — expected `{"status":"ready"}`
- අපේ n8n: http://localhost:5679 — 5678 වෙනම instance එකයි.
- Optional disposable WordPress: http://localhost:8081

Existing `.env`, encryption keys සහ volumes තබාගන්න. Database reset, `down -v`, නැවත owner bootstrap කිරීම මෙම test සඳහා අවශ්‍ය නැහැ.

## 3. Login සහ business profile

1. http://localhost:8000/accounts/login/ විවෘත කරන්න.
2. දැනට ඇති `you@example.com` owner account එකේ ඔබ සකස් කළ password එක භාවිත කරන්න. Password එක මෙහි සටහන් කරලා නැහැ.
3. Denim Yard open කරන්න: http://localhost:8000/sites/1/ .
4. Publishing paused බව සාමාන්‍යයි. ඒක දැනට වෙනස් කරන්න අවශ්‍ය නැහැ.
5. Business profile එකේ Sri Lanka, English, Wide Leg/Women's Denim සහ COD facts බලන්න. Shipping තවම තහවුරු නොකළ දෙයක්; PayHere planned. Public banners වලින් ඒ facts ස්වයංක්‍රීයව overwrite වෙන්නේ නැහැ.

## 4. WordPress read connection

1. http://localhost:8000/sites/1/connection/ යන්න.
2. **Test read connection** ඔබන්න.
3. Expected: `connected`, live plugin 0.1.0, remote write false.
4. **Read public inventory** ඔබන්න. Published public pages/products list එක ලැබිය යුතුයි. කලින් records 22ක් ලැබුණා; site content වෙනස් වුවහොත් count වෙනස් විය හැකියි.
5. Credentials නැවත පුරවන්න/rotate කරන්න/revoke කරන්න අවශ්‍ය නැහැ.

## 5. Public audit එකෙන් අඩුපාඩු බලන්න

1. http://localhost:8000/sites/1/ හි **Run public page audit** ඔබන්න.
2. Job එක open කර **Refresh status** ඔබන්න: queued → running → succeeded.
3. HTTP status, title, description සහ issue code/remediation බලන්න.
4. කලින් homepage එකේ `description_missing` ලැබුණා. නැවත run එකේ actual result එක භාවිත කරන්න; site එක වෙනස් විය හැකියි.

`succeeded` කියන්නේ audit එක run වූ බවයි; SEO errors සියල්ල fix වූ බව නොවේ. මේ path එක single-page head checks සඳහායි. Missing/duplicate title/description, HTTP errors වගේ සීමිත issues පමණයි.

## 6. URL research සහ නව site එකක්

1. http://localhost:8000/sites/1/research/ යන්න.
2. Gemini checkbox එක **තෝරා නොගෙන** Analyze URL ඔබන්න.
3. Refresh කර completed report එක බලන්න. Expected: උපරිම pages 5ක්, page observations, source excerpts, keyword candidates සහ skipped-page reasons තිබේ නම් ඒවා.
4. කලින් Denim Yard homepage, Wide Leg, Women's Denim, About සහ Contact pages 5ක් සහ heading candidates 8ක් ලැබුණා.
5. Competitors/search volume/difficulty unknown බව පෙන්වීම expected. ඒවා හදා දමා නැහැ.

URL-only onboarding බලන්න http://localhost:8000/sites/discover/ වෙත ගොස් ඔබට කළමනාකරණය කිරීමට අවශ්‍ය site URL එක දෙන්න. එක organization එකක් තිබේ නම් URL එක පමණක් අවශ්‍යයි. Matching existing URL එකක් තිබේ නම් ඒ site එක reuse වෙනවා; නැත්නම් paused production profile එකක් සෑදෙනවා. WordPress credentials/owner facts මේකෙන් සොයාගන්නේ නැහැ.

## 7. Gemini test — වෙන්ව පරීක්ෂා කරන්න

Key/model දැනට configure කරලා AI enable කර තිබෙනවා. Key එක නැවත පුරවන්න හෝ chat එකට එවන්න අවශ්‍ය නැහැ.

1. Research page එකේ latest **Gemini status** බලන්න: කලින් `provider_timeout`, අවසන් test එකේ `provider_http_503` ලැබුණා.
2. Provider නැවත ක්‍රියාත්මක වූ පසු අවශ්‍ය නම් **Include Gemini profile hypotheses** තෝරා එක් run එකක් කරන්න.
3. Pass result: Gemini status `succeeded` සහ schema/evidence validation pass වූ profile suggestions. Model එකට ප්‍රමාණවත් evidence නැත්නම් suggestions හිස්ව uncertainties පෙන්විය හැකියි.
4. 503/timeouts නැවත ලැබුණොත් AI generation test fail. Public research report එක තිබුණා කියලා AI pass යැයි සලකන්න එපා.

Calls උපරිම 1/run සහ 5/organization/Colombo calendar day; token cap 2,048; low thinking; bounded provider timeout 90 seconds. Failed attempts ද reservation භාවිත කරනවා. මේ දිනේ agent tests වල reservations 4ක් භාවිත වුණා; තවත් ඔබ කළ runs අනුව allowance වෙනස් විය හැකියි. Repeated clicks මඟින් limit bypass කරන්න හෝ budget reset කරන්න අවශ්‍ය නැහැ. මේ සීමාව මුදල් billing ceiling එකක් නොවේ.

## 8. Preview test

1. http://localhost:8000/sites/1/preview/ විවෘත කරන්න.
2. URL එක Denim Yard homepage ලෙස තබා public page fetch action එක භාවිත කරන්න.
3. Title/description පුරවන්න හෝ test text වෙනස් කරන්න.
4. Google, Facebook, X සහ LinkedIn tabs මාරු කරන්න. Preview text වෙනස් විය යුතුයි.
5. Public raster image URL එකක් දුන් විට allowed image එකක් නම් preview එක පෙන්වයි. Missing image/blocked URL එකකට placeholder පෙන්වීම expected.
6. **Inspect proposed HTML** සහ **Copy HTML** පරීක්ෂා කරන්න.

මෙය approximate visual preview එකක්. Actual Google snippet/ranking හෝ social platform cache result එක guarantee කරන්නේ නැහැ. මෙහි typed values live site එකට publish වෙන්නේ නැහැ.

## 9. Draft සහ review test

1. http://localhost:8000/sites/1/changes/ යන්න.
2. තිබෙන draft එක බලන්න: http://localhost:8000/sites/1/changes/51dde149-c177-42d2-915e-f7c0ca688083/ . මේක product 89 සඳහායි; homepage එකට නොවේ.
3. New draft/editor එකේ inventory එකෙන් published product/page එකක් තෝරා, අවශ්‍ය title/description fields සහ අදාළ source evidence තෝරන්න. Factual wording සහ reason එකක් දී **Save draft only** ඔබන්න.
4. Expected: draft එක app එකේ save වෙනවා, current WordPress revision කියවනවා, preview සහ field diff පෙනෙනවා. Live metadata වෙනස් වෙන්නේ නැහැ.
5. **Submit for review** කළ විට `pending_review` විය යුතුයි.
6. Draft එක හැදූ/අවසන් edit කළ account එකෙන් approve කිරීම block විය යුතුයි. ඒක expected protection එකක්.
7. Review test සඳහා http://localhost:8000/staff/ හි වෙනත් ඔබ පාලනය කරන email account එකක් invite කර Denim Yard වෙත **Reviewer** bundle එක assign කරන්න. Private invite link එකෙන් password සකස් කර වෙනත් browser profile/private window එකක login වෙන්න.
8. Reviewer account එකෙන් same diff බලලා **Approve exact diff** ඔබන්න. Expected: approved. ඉන්පසු original editor account එකෙන් edit/save කළොත් කලින් approval invalidate විය යුතුයි.

Owner ලෙස ඔබට final approval දෙන්න ඕන නම්, වෙනම Content Editor account එකෙන් draft එක create/edit/submit කර owner account එකෙන් approve කරන්න. Owner තමන් හැදූ draft එක approve කිරීමට නීතිය bypass කරන්නේ නැහැ.

**Live site එකට publish button test කරන්න එපා.** Outbound writes දැනට fixed disposable WordPress fixture එකට පමණක් සීමා කරලා තිබෙනවා. Owner approval පමණින් live publishing enable වෙන්නේ නැහැ. Homepage mapping/category adapters සහ සැබෑ staging setup තවම අවශ්‍යයි.

## 10. Local WordPress apply/restore/CPT end-to-end test

PowerShell තුළ පහත එකින් එක run කරන්න:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wordpress-fixture.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-publication.ps1
```

මේවා synthetic local WordPress එකට පමණක් writes කරනවා. Expected output:

- 25 WordPress metadata change checks passed.
- Separate-author review / approved apply / actual public HTML verification passed.
- Concurrent duplicate replay සහ later-edit restore conflict passed.
- Queued apply සහ restore සැබෑ Celery worker එකෙන් execute වීම.
- Original HTML/revision නැවත ලැබීම.
- Temporary writer password revoked; remote writes disabled.

Private `cseo_record` CPT snapshot storage/privacy මේ checks වල ඇතුළත්. Local WordPress admin එකේ Settings → SEO Metadata Records යටතේ history බලන්න පුළුවන්. සාමාන්‍ය public page හෝ REST endpoint එකකින් private records පෙනෙන්නේ නැහැ. Live Denim Yard තවම 0.1.0 read-only plugin එකයි.

## 11. n8n test

1. http://localhost:5679 වෙත දැනට ඇති n8n owner account එකෙන් login වෙන්න. Django account එකෙන් n8n login වෙන්නේ නැහැ.
2. Initial audit සහ scheduled audit workflows දෙක පමණක් දැනට implemented/verified බව සලකන්න.
3. Executions හි latest status බලන්න. http://localhost:8000/sites/1/automation/ හි schedule enabled, interval 1440 minutes සහ jobs බලන්න.
4. Real timer → Django → Celery → public audit test එක නැවත run කරන්න අවශ්‍ය නම්:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/test-n8n-schedule.ps1 -SiteId 1
```

මේ helper එක scheduled workflow re-import/publish කර n8n restart කර daily audit එක due කර actual timer tick එකක් බලාගන්නවා (maximum wait 90 seconds). මේක read-only audit එකක්; SEO changes publish කරන්නේ නැහැ. View කිරීම සඳහා setup-n8n-audit helper එකෙන් credentials නැවත rotate කිරීමට අවශ්‍ය නැහැ.

## 12. Automated checks සහ issue එකක් හමු වුණොත්

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

Expected: Django check pass, no migration drift, PostgreSQL tests pass, OpenAPI validation pass. Full suite එකට මිනිත්තු කිහිපයක් යා හැකියි. Current source එකේ අලුත් test එක නිසා full test count එක පෙර 97ට වඩා වෙනස් විය හැකියි; actual result එක භාවිත කරන්න.

Service/queue issue එකක් නම්:

```powershell
docker compose ps
docker compose logs --tail 60 web worker
docker compose exec web python manage.py recover_jobs
docker compose exec web python manage.py recover_research
```

Recovery commands අතුරුදහන් queued messages නැවත dispatch කරනවා; abandoned research paid calls ස්වයංක්‍රීයව නැවත run කරන්නේ නැහැ. Gemini 503 සඳහා මේවා provider fix එකක් නොවේ.

Report කරන්න: ඔබ විවෘත කළ URL, ඔබපු button එක, expected/actual result, job/change/run ID, සහ error code එක. Password, API key, Application Password, invitation token හෝ `.env` contents එවන්න එපා.

Final acceptance: login/read connection/public audit/research/preview/draft/review/local apply-restore/n8n එකින් එක pass වුවත් full SEO automation අවසන් යැයි කියන්න බැහැ. Search-backed competitors, keyword map, automated page-specific AI drafts, homepage/category/content adapters, Google integrations, reports, ඉතිරි workflows සහ production release requirements තවම ඉතිරියි.
