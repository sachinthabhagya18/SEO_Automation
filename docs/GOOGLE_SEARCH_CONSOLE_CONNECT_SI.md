# Google Search Console — ඔබේ account එකෙන් අවශ්‍ය සැකසුම්

මෙය Gemini API key එකට වෙනස් integration එකක්. Gemini සඳහා අලුත් app/key එකක් අවශ්‍ය වුණේ නැහැ: 2026-11-17 දින `gemini-3.5-flash-lite` tiny generation සහ සැබෑ Denim Yard research validation සාර්ථක වුණා. Google traffic metrics සඳහා පහත account setup එක වෙනම අවශ්‍යයි.

## 1. Denim Yard property එක verify කරන්න

1. ඔබේ browser එකෙන් https://search.google.com/search-console/welcome විවෘත කර Google account එකෙන් login වෙන්න.
2. **Domain property** තෝරා `denimyard.com` දාන්න. මෙහි `https://` හෝ path එකක් දාන්න එපා.
3. Google දෙන `google-site-verification=...` TXT value එක copy කරන්න. මෙය API key එකක් නොවේ; public DNS verification record එකක්.
4. Cloudflare → denimyard.com → DNS → Records → Add record: Type **TXT**, Name **@**, Content **Google දුන් exact value**, TTL **Auto**. Existing mail/verification records මකන්න හෝ overwrite කරන්න එපා.
5. http://localhost:8000/sites/1/google/ තුළ value එක save කර **Check public TXT record** බලන්න.
6. Google Search Console වෙත නැවත ගොස් **Verify** ඔබන්න. App එකේ DNS match එක පමණක් Google ownership verification නොවේ.

Google login සහ Google-issued token එක ඔබේ account එකෙන් ලැබිය යුතුයි; ඒවා agent විසින් invent කර නැහැ. Verification TXT record එක verify වුණාට පසුවත් තබන්න. [Google ownership verification guide](https://support.google.com/webmasters/answer/9008080)

## 2. Google Cloud OAuth client එක සකස් කරන්න

1. https://console.cloud.google.com/ විවෘත කරන්න. ඔබේ දැනට ඇති project එකක් හෝ මෙම integration එක සඳහා project එකක් තෝරන්න. Gemini project එකම භාවිත කළ හැකියි; OAuth client එක API key එකට වෙනස් credential එකක්.
2. APIs & Services → Library තුළ **Google Search Console API** enable කරන්න.
3. Google Auth Platform / OAuth consent screen තුළ app name සහ contact email සකස් කරන්න. Testing mode භාවිත කරනවා නම් **Audience / Test users** යටතේ ඔබේ Google account email එක එකතු කරන්න.
4. **Clients → Create client → Web application** තෝරන්න. Desktop app client එකක් තෝරන්න එපා.
5. **Authorized redirect URI** එකට පහත URL එක exact ලෙස දාන්න:

```text
http://localhost:8000/integrations/google/callback/
```

6. ලැබෙන **Client ID** සහ **Client Secret** local `.env` file එකේ දැනට සකස් කර ඇති fields දෙකට දාන්න:

```dotenv
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/integrations/google/callback/
```

මෙහි values examples පමණයි. සැබෑ secret එක chat, screenshot, Git හෝ docs තුළ දාන්න එපා. Client Secret Google Cloud/local `.env` තුළ පමණක් තබන්න. [Google web-server OAuth guide](https://developers.google.com/identity/protocols/oauth2/web-server)

## 3. Local services අලුත් configuration එකෙන් run කරන්න

Project folder terminal එකේ:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-platform.ps1 -SkipBuild
```

මේ helper එක existing accounts/volumes/data reset කරන්නේ නැහැ. Code වෙනස් කර තිබෙනවා නම් `-SkipBuild` ඉවත් කර run කරන්න. Docker Desktop ආරම්භ වී තිබිය යුතුයි.

## 4. App එක Google account එකට connect කරන්න

1. සාමාන්‍ය browser tab එකෙන් http://localhost:8000/sites/1/google/connection/ විවෘත කරන්න. Owner account එකෙන් app එකට login වී සිටින්න.
2. **OAuth client configured locally: Yes** ලැබිය යුතුයි. No නම් `.env` values සහ services recreate කිරීම පරීක්ෂා කරන්න.
3. **Connect with Google — read-only** ඔබන්න. නිවැරදි Google account එක තෝරා Search Console read-only consent දෙන්න.
4. App එකට නැවත ආ විට **Refresh matching Google properties** ඔබන්න.
5. `sc-domain:denimyard.com` හෝ exact URL-prefix property එක සඳහා **Use this property** ඔබන්න.
6. Status **connected** වුණාම **Open search performance** වෙත යන්න.

App එක exact website/property matching, single-use state, PKCE, encrypted token storage සහ local revoke/version checks භාවිත කරනවා. Refresh token එකක් ලබා නොදුන්නොත් `google_offline_token_required` පෙන්වනවා; Connect නැවත ආරම්භ කර consent දෙන්න. මේ consent එකෙන් WordPress content හෝ Google account settings ලියන්නේ නැහැ.

## 5. Actual metrics sync කරන්න

http://localhost:8000/sites/1/analytics/ තුළ **Sync last 28 final days** ඔබන්න. Status queued/running පසුව succeeded හෝ explicit failure එකක් ලැබෙනවා. Refresh කර result බලන්න.

Daily totals සහ query/page/country/device samples වෙන් කර තිබෙනවා. Details sample clicks daily totals එකට නැවත එකතු කරන්නේ නැහැ. Latest successful data period/fetched time පෙන්වනවා. Google date buckets Pacific timezone එකේ නිසා workspace job time එකෙන් day shift කරන්න එපා.

Sync එක finalized data සඳහා දින තුනකට පෙර අවසන් වන දින 28ක window එක භාවිත කරනවා. Google නොදුන් rows/days zero ලෙස invent කරන්නේ නැහැ. Detail rows 3,000කට සහ bounded API calls ගණනකට සීමා කර තිබෙනවා. API එකත් top/limited/anonymized data සීමා කරන නිසා මෙය complete query universe එකක් නොවේ. Average position fixed keyword rank එකක් නොවේ. [Search Analytics API reference](https://developers.google.com/webmaster-tools/v1/searchanalytics/query)

## 6. n8n daily flow

Daily Search Console workflow එක දිනපතා 06:30 Asia/Colombo සඳහා configure/publish කර තිබෙනවා. Google property connection එක නැති අද සැබෑ test එකේ `blocked: google_property_connection_required` ලැබුණා; traffic data සෑදුවේ නැහැ. Account setup අවසන් කළ විට එම flow එක actual sync එක queue කළ හැකියි.

n8n URL: http://localhost:5679

Workflow: http://localhost:5679/workflow/som67c9baa118704c49a9183257fdba7029

Credential නැවත bind/test කිරීමට:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-n8n-search.ps1 -SiteId 1 -TestAndEnable
```

n8n service token දින 30කින් expire වෙනවා. Google OAuth app එක External + Testing mode නම් Google refresh token දින 7කින් expire විය හැකි බැවින් නැවත Connect අවශ්‍ය විය හැකියි. මේ lifecycle දෙක වෙනස්. [Google refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)

## සාමාන්‍ය failure codes

| Code / screen | පරීක්ෂා කළ යුතු දේ |
|---|---|
| `redirect_uri_mismatch` | Google Cloud Web client redirect URI එක exact URL එකට ගැළපෙනවාද |
| OAuth access blocked / test-user error | Correct account එක test users ලැයිස්තුවේද; app consent settings සකස් කර තිබේද |
| `google_http_401` | Google account reconnect කරන්න |
| `google_http_403` | Search Console API enabled ද; selected property සඳහා account permission තිබේද |
| `google_http_429` | Quota recovery සඳහා ඉඩ දෙන්න; blind repeated sync කරන්න එපා |
| No matching property | Domain spelling, ownership verification සහ login කළ Google account එක බලන්න |
| No daily rows | New property/data delay/Google omissions විය හැකියි; zero traffic ලෙස නොසලකන්න |

මෙම code path local mocked-provider/PostgreSQL tests වලින් පරීක්ෂා කර තිබෙනවා. ඔබේ Google account/property තව නැති නිසා real OAuth consent සහ live Search Console data import තව සාර්ථකයි කියලා claim කරන්නේ නැහැ.
