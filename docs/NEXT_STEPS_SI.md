# දැන් පරීක්ෂා කරන පියවර

1. http://localhost:8000 වෙත ඔබේ දැනට ඇති owner account එකෙන් login වෙන්න.
2. Denim Yard report එක සඳහා http://localhost:8000/sites/1/research/ විවෘත කරන්න. සැබෑ public pages 5ක් කියවූ report එක සහ source links සහිත heading keyword candidates 8ක් තිබෙනවා. මේවා search volume/ranking data නොවේ.
3. Preview සඳහා http://localhost:8000/sites/1/preview/ විවෘත කරන්න. Title, description සහ image URL වෙනස් කර Google/Facebook/X/LinkedIn පෙන්වන ආකාරය බලන්න. මෙයින් website එක publish/change වෙන්නේ නැහැ.
4. අලුත් managed site එකක් URL එකෙන් ආරම්භ කිරීමට http://localhost:8000/sites/discover/ භාවිත කරන්න. මුලින් publishing paused තත්ත්වයේ profile එකක් සහ public research job එකක් සෑදෙනවා.
5. Gemini සඳහා project root එකේ `.env` file එක තුළ පහත fields පුරවන්න. `.env.example` තුළ සැබෑ key එක දාන්න එපා. Key එක chat එකටත් එවන්න එපා.

```dotenv
GEMINI_API_KEY=ඔබේ_සැබෑ_key_එක
GEMINI_MODEL=gemini-3.8-flash
RESEARCH_AI_ENABLED=true
```

ඉන්පසු project folder එකේ PowerShell තුළ:

```powershell
docker compose up -d web worker
```

Research page එකේ **Include Gemini profile hypotheses** තෝරා run කරන්න. එක් run එකකට outbound provider request එකක් පමණයි; output tokens උපරිම 2,048යි; organization එකකට දිනකට reserved calls උපරිම 5යි. Failed call එක නැවත ස්වයංක්‍රීයව charge වන ලෙස retry කරන්නේ නැහැ. මේවා මුදල් වියදම් ceiling එකක් නොවන නිසා provider account billing limits වෙනම සකස් කළ යුතුයි. AI suggestions ඔබේ verified facts වෙනස් කරන්නේ නැහැ.

## Approval සහ WordPress

Gemini config follow-up: key/model access check එක HTTP 200 වුණා. ඒත් text generation test එකේ timeout සහ අවසන් වරට `provider_http_503` ලැබුණා. ඒ නිසා AI test එක pass ලෙස සලකන්නේ නැහැ. Research report එකේ Gemini status බලන්න; service unavailable වෙලාවක නැවත නැවත Analyze ඔබලා daily allowance වැය කරන්න එපා. Key එක නැවත chat එකට එවන්න අවශ්‍ය නැහැ.

ඔබ තෝරාගත් ක්‍රමය Draft → ඔබේ approval → staging test. Draft එක හැදූ හෝ අවසන් වරට edit කළ account එකෙන් ඒ draft එක approve කරන්න බැහැ. වෙනම authorized reviewer අවශ්‍යයි. දැනට ඔබ හැදූ draft එකක් ඔබම approve කිරීමට මේ නීතිය මඟහැරීමට ක්‍රමයක් එකතු කරලා නැහැ.

Local plugin 0.2.0 තුළ private SEO history CPT එක තිබෙනවා. WordPress admin එකේ Settings → SEO Metadata Records යටතේ local apply/restore history බලන්න පුළුවන්. Actual frontend tags post metadata වලින් render වෙනවා. Live Denim Yard plugin 0.1.0 තවම read-only; එයට මේ ZIP එක upload කරලා නැහැ.

Denim Yard homepage එකට validated WordPress ID mapping එකක් නැති නිසා product metadata වෙනස් කිරීමෙන් homepage SEO වෙනස් කරන්නේ නැහැ. Homepage adapter එක ඉදිරියට සකස් කළ යුතු වෙනම කොටසක්.

## තවම සම්පූර්ණ නොවූ දේ

Automatic competitors/search-demand research, keyword map, page-specific AI drafts, homepage/category/content adapters, සම්පූර්ණ technical audit, Google Search Console/GA4 සහ ඉතිරි n8n workflows තවම අවසන් නැහැ. දැනට තිබෙන n8n daily public audit එක ක්‍රියාත්මකයි; එය full SEO automation එකක් ලෙස සලකන්න එපා.

සම්පූර්ණ විස්තර සහ ඉතිරි වැඩ: [URL_RESEARCH_AND_PREVIEW.md](URL_RESEARCH_AND_PREVIEW.md), [STATUS.md](STATUS.md), [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
