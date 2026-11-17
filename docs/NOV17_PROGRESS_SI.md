# 2026-11-17 — අද කළ වැඩ සහ ඊළඟ account setup එක

## Gemini සඳහා අලුත් app/key එකක් අවශ්‍ය නැහැ

Existing key එකම භාවිත කර තිබෙනවා. `gemini-3.8-flash` generation test එකට HTTP 503 ලැබුණත්, `gemini-3.5-flash-lite` සමඟ tiny JSON generation සාර්ථක වුණා. ඒ model එකෙන් සැබෑ Denim Yard URL research එකත් schema/source validation pass වුණා. Runtime සහ `.env.example` දැන් `gemini-3.5-flash-lite` භාවිත කරනවා.

Actual accepted research run: `77db53b9-32c7-4aa7-864d-7a883b9db328`.

Report: http://localhost:8000/sites/1/research/?run=77db53b9-32c7-4aa7-864d-7a883b9db328

Validated AI homepage proposal එක fresh staging evidence/revision සමඟ වෙනම draft එකකට සකස් කර තිබෙනවා:

http://localhost:8000/sites/12/changes/a98c7d2f-24e8-42ed-96be-695f56520b82/

එය **pending_review**. Approvals හෝ publication copy කර නැහැ. Diff එක කියවා අනුමත නම් Approve & run on test copy භාවිත කරන්න. Live site එක තවම paused/unchanged.

වෙනත් staging AI research request එකකට 503 ලැබුණා. ඒ නිසා provider availability සෑම request එකකටම ස්ථාවරයි කියලා කියන්න බැහැ. Valid AI output ලැබුණු බවට සැබෑ acceptance එක දැන් තිබෙනවා; failure එකකදී evidence-only drafts සහ safe status දිගටම පෙන්වනවා. දිනකට organization calls පහේ සීමාව සහ එක් run එකකට එක් outbound generation request එකේ සීමාව වෙනස් කර නැහැ.

## Google account setup එකයි actual metrics test එකේ බාධාව

ඔබ Search Console property එකවත් OAuth client එකවත් තවම සකස් කර නැති බව තහවුරු කළා. ඒවා ඔබේ Google account එකෙන් අවශ්‍යයි. දැන් backend code, token encryption, OAuth state/PKCE, property selection, bounded metrics sync, analytics UI සහ CSV export සකස් කර තිබෙනවා.

ඔබ පුරවන්න ඕන local fields `.env` තුළ සකස් කර තිබෙනවා. [Google setup Sinhala guide](GOOGLE_SEARCH_CONSOLE_CONNECT_SI.md) හි පියවර අනුගමනය කරන්න. Secret එක chat එකට එවන්න එපා.

Connection screen: http://localhost:8000/sites/1/google/connection/

Metrics screen: http://localhost:8000/sites/1/analytics/

Daily Search Console n8n workflow එක import/publish කර සැබෑ webhook එක පරීක්ෂා කළා. දැනට response එක `blocked: google_property_connection_required`; කිසිම Google traffic value එකක් invent කර නැහැ. Account setup ඉවර වුණාම එම pipeline එක actual data fetch කිරීම සඳහා සූදානම්.

Workflow: http://localhost:5679/workflow/som67c9baa118704c49a9183257fdba7029

Google properties සහ token refresh/sync tests mocked Google responses භාවිත කරනවා. Real Google OAuth consent සහ live metrics තවම verified නැහැ. Daily metrics summary සහ query/page/country/device samples වෙන් කර තිබෙනවා; detail rows 3,000 cap එක සහ missing-data limitations UI තුළ පෙන්වනවා.

## Services නැවත ආරම්භ කිරීම

අද මුලින් web/worker/database services නවතා තිබුණා. ඒවා නැවත ආරම්භ කර, long-lived services සඳහා restart policies සහ non-destructive helper එක සකස්/test කළා:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-platform.ps1
```

Code rebuild අවශ්‍ය නැත්නම් `-SkipBuild` එක් කරන්න. Existing accounts, volumes සහ approvals reset වෙන්නේ නැහැ.

## Verification සහ ඉතිරි scope

Full PostgreSQL suite: **170 passed in 345.78s**. Google/bridge focused set: **19 passed in 59.55s** (එයට පසුව එක් කළ refresh/pagination cases ද full suite එකේ ඇතුළත්). Startup helper සහ live UI routes pass වුණා. Actual successful Gemini result සහ unapproved prepared test draft පරීක්ෂා කළා.

Google account setup, real OAuth/metrics acceptance, remaining six specification workflows, search-backed competitor discovery, content/Elementor editing, reporting සහ production hardening තව අවශ්‍යයි. n8n තුළ දැනට audit workflows දෙක, URL research/drafts සහ Google daily metrics flow එක තියෙනවා; අවසන් එක account setup නිසා blocked. මුළු platform specification එක 100% complete කියලා මෙයින් අදහස් කරන්නේ නැහැ.
