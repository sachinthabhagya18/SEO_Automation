> **2026-11-17 current update:** Gemini 3.5 Flash-Lite passed a real generation/research run. Google OAuth/property/metrics code and its n8n flow are implemented; real Google account setup is required. Read [today's results and next steps](NOV17_PROGRESS_SI.md) and [Google setup guide](GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md). Older dated statements below are historical.

# Gemini connection සහ අලුත් research workflow

## දැනට ලැබුණු ප්‍රතිඵල

2026-11-16 දින key එක නොපෙන්වා කළ model metadata check එක HTTP 200 වුණා. කලින් generation attempts වල timeout/HTTP503 ලැබුණා. අලුත් tiny generation probe එකත් තත්පර 25 ඇතුළත response එකක් නොලැබී `provider_timeout` වුණා. ඒ නිසා generation acceptance තවම pass නැහැ. අලුත් key එකක් සෑදීමෙන් මේ timeout/503 විසඳෙන බවට සාක්ෂියක් නැහැ.

Latest runtime configuration එකේ AI enable flag එක false තිබුණා. ඔබේ `.env` setting එක overwrite නොකර, diagnostic process එකට පමණක් `RESEARCH_AI_ENABLED=true` දී test කළා. දිනක normal allowance එකම භාවිත වෙනවා; එය bypass/clear කරලා නැහැ. අද organization allowance 5ම reserve වී තිබෙන නිසා තවත් generation test එකක් යවලා නැහැ. Colombo calendar day එක වෙනස් වූ විට allowance query එක අලුත් දවසට ගණනය වෙනවා.

## නැවත test කරන command

මේ command එක metadata access පමණක් පරීක්ෂා කරනවා; text generation නැහැ:

```powershell
docker compose exec web python manage.py check_gemini --site 1
```

Daily allowance තිබෙන විට explicit tiny generation test එකක් සඳහා:

```powershell
docker compose exec -e RESEARCH_AI_ENABLED=true web python manage.py check_gemini --site 1 --generate
```

Expected pass: `Model metadata HTTP: 200`, `Generation probe: succeeded`. Probe එකට outbound generation request උපරිම එකක්, output-token cap 128ක්, timeout තත්පර 25ක්. එයින් business analysis/drafts සෑදෙන්නේ නැහැ. Probe එක pass වීම සම්පූර්ණ research prompt එක pass වීමක් නොවේ; ඒක පසුව research page එකෙන් පරීක්ෂා කළ යුතුයි.

Safe status codes:

- `ai_disabled`: current process එකේ AI enable කරලා නැහැ.
- `ai_not_configured`: key/model configuration අඩුයි.
- `ai_budget_exhausted`: අද organization allowance ඉවරයි; database counters මකා bypass කරන්න එපා.
- `provider_http_400`: request/model parameters පරීක්ෂා කළ යුතුයි.
- `provider_http_401` / `provider_http_403`: key/project permissions/restrictions බලන්න.
- `provider_http_404`: configured model/API availability බලන්න.
- `provider_http_429`: provider quota/rate limits බලන්න.
- `provider_http_503` / `provider_timeout`: service/network/latency failure; key වැරදියි කියලා ඒකෙන් පමණක් තීරණය කරන්න බැහැ.
- `provider_incomplete_response` / schema rejection: structured output acceptance fail; incomplete text publish කරන්නේ නැහැ.

## අවශ්‍ය නම් අලුත් key එකක් සකස් කිරීම

1. [Google AI Studio API Keys](https://aistudio.google.com/apikey) විවෘත කරන්න.
2. අවශ්‍ය Google Cloud project එක තෝරන්න/import කරන්න; Create API key භාවිත කරන්න. Existing project එකේ quota/billing/permissions ගැටලුවක් නම් ඒ project එකේම තවත් key එකක් සෑදීමෙන් ඒවා වෙනස් වෙන්නේ නැහැ.
3. Google AI Studio හි දැනට new keys authorization keys ලෙස සෑදෙනවා. Gemini API access සහ project permissions පරීක්ෂා කරන්න. [Official key instructions](https://aistudio.google.com/docs/api-key).
4. Project root `.env` තුළ `GEMINI_API_KEY` value එක පමණක් privately replace කරන්න. `.env.example`, chat, screenshots හෝ workflow JSON තුළ key එක දාන්න එපා.
5. Model එක දැනට `GEMINI_MODEL=gemini-3.8-flash`. UI AI runs අවශ්‍ය නම් `RESEARCH_AI_ENABLED=true` සකස් කරන්න.
6. `docker compose up -d --wait web worker` run කර metadata check එක කරන්න.
7. Allowance තිබෙන විට generation probe එක කරන්න. අලුත් key එක තහවුරු වූ පසුව පරණ key එක revoke කිරීමට Google AI Studio භාවිත කරන්න. Key එක හෙළි වී තිබේ නම් එය ඉක්මනින් revoke කරන්න.

දැනට key/model access HTTP200 නිසා මුලින් key rotation අවශ්‍ය බව තහවුරු වී නැහැ. Provider failure සහ permission failure වෙනම සලකන්න. [Official troubleshooting](https://aistudio.google.com/docs/troubleshooting).

## මේ update එකෙන් සකස් කළ ඉදිරි කොටස්

### Research → metadata proposal → revision-bound draft

http://localhost:8000/sites/1/research/ විවෘත කරන්න. අලුත් public-only run එකේ root සහ categories සමඟ product links prioritize කරනවා (උපරිම pages 5යි). Page-specific metadata proposals ස්වයංක්‍රීයව සෑදෙනවා.

- Gemini validated output තිබේ නම් `gemini-page-v1` ලෙස ලේබල් වෙනවා.
- නැත්නම් observed page title/H1 වලින් සෑදූ starting wording `deterministic-page-v1` ලෙස පැහැදිලිව පෙන්වනවා. ඒක AI output ලෙස සලකන්නේ නැහැ.
- WordPress mapping ඇති proposal එකේ **Save as reviewable draft** ඔබන්න. Current WordPress revision එක read කර app එකේ draft එක save වෙනවා; website write එකක් නැහැ.
- Same proposal නැවත submit කළත් existing draft එකම ලැබෙනවා.
- Homepage/category mapping නැත්නම් **mapping required** පෙන්වනවා. වෙනත් product ID එකකට ඒ proposal එක යවන්නේ නැහැ.
- Draft → edit/review → separate approval → local staging test යන නීති ඒ ආකාරයෙන්ම තිබෙනවා.

Actual Denim Yard run `7cbae0df-18b0-4033-ad26-4794e892312f` pages 5ක් සහ proposals 5ක් සෑදුවා; products දෙකකට validated mappings තිබුණා. Product 17 සඳහා සැබෑ read connection එකෙන් draft එකක් save කර duplicate-submit proof එකත් pass වුණා:

http://localhost:8000/sites/1/changes/bed1d726-83c7-4cea-a972-a2e5ea70d69f/

එය unapproved rule-based draft එකක්; published SEO වෙනසක් නොවේ. Owner facts/pause වෙනස් වී නැහැ.

### Source-backed keyword map

http://localhost:8000/sites/1/keywords/ හි observed heading candidates, original source excerpt/date, human-reviewed intent සහ target-page assignment වෙන වෙනම පෙන්වනවා. Owner/authorized editor කෙනෙකුට mapping review කර lock කළ හැකියි. නැවත crawl එකක් existing assignment/intent/lock overwrite කරන්නේ නැහැ.

CSV export සඳහා `export_report` permission අවශ්‍යයි. Formula-like source text CSV එකේ neutralize කරනවා. Search volume/difficulty `unknown` ලෙස තබනවා; Google ranks/metrics සපයන්නේ නැහැ. මෙය heading evidence mapping milestone එකක්; external keyword-demand research, clustering/cannibalization analysis සම්පූර්ණ කිරීමක් නොවේ.

## තවම අවශ්‍ය දේ

Search-backed competitor discovery, full keyword-demand/cluster analysis, homepage/category/content adapters, Google integrations, remaining n8n workflows, staging setup සහ production hardening තවම ඉතිරියි. Hosting/control-panel නම සහ Search Console verification තත්ත්වය ඉල්ලා තිබෙන්නේ එම external setup සඳහායි; credentials chat එකට අවශ්‍ය නැහැ.
