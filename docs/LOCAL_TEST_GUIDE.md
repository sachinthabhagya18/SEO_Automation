# Local login සහ test guide

මෙය දැනට ඇති build එක සඳහාය. App accounts, business profiles, staff/site permissions, reference inputs සහ සීමිත public-page audits ක්‍රියාත්මකය. n8n server එක running නමුත් SEO workflows තවම සාදා/connect කර නැත. AI, full keyword research, Google analytics සහ WordPress remote publishing තවම නැත.

1. Docker Desktop start කර VS Code PowerShell terminal එකේ project root එකට යන්න:

```powershell
Set-Location 'G:\MY Project\DJANGO Project\SEO_Automation'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose ps
```

Web, worker, db, redis, n8n සහ n8n-db healthy විය යුතුය. Migrate exited 0 සාමාන්‍යයි.

2. වත්මන් database එකේ `you@example.com` owner account එක තිබේ; පරීක්ෂා කළ අවස්ථාවේ inactive විය. මුල් private setup URL තිබේ නම් එය විවෘත කරන්න. Link එක නැති/expired නම්:

```powershell
docker compose exec web python manage.py reissue_invitation --email you@example.com
```

Terminal එකේ අලුත් private URL විවෘත කර password දෙවරක් යොදන්න (අවම අක්ෂර 12). පැරණි links expire වේ. මෙම command එක active account එකක password reset නොකරයි. Password එක දැනටමත් සකසා ඇත්නම් මෙම පියවර අවශ්‍ය නැත. Link/password chat එකට දාන්න එපා.

3. http://localhost:8000/accounts/login/ වෙත යන්න. Username `you@example.com`; password ඔබ දැන් තෝරාගත් එක. `/admin/` වෙනුවට මෙය භාවිත කරන්න. සම්පූර්ණයෙන් අලුත් database එකක් සඳහා පමණක් `bootstrap_owner --email YOUR_EMAIL --company "YOUR_COMPANY"` භාවිත කරන්න; වත්මන් database එකට නැවත bootstrap අවශ්‍ය නැත.

4. Websites → Add website: ඔබගේ actual managed website name/URL යොදා environment, timezone Asia/Colombo සහ business facts ඇතුළත් කර Save profile කරන්න. Not connected සහ unknown score සාමාන්‍යයි; තවම WordPress integration කර නැත.

5. Site overview → Run public page audit → Refresh status. Queued → Running → Succeeded හෝ Failed පෙන්වයි. Succeeded නම් HTTP/head evidence සහ missing/duplicate metadata findings බලන්න. මෙය එක URL එකක limited checks පමණි; website edit/publish නොකරයි. Public URL සහ robots අවසර අවශ්‍යයි. localhost/private URLs blocked වේ; local WP fixture URL audit input එකට යොදන්න එපා.

6. Site overview → Reference websites: actual competitor/sample URLs සහ relationship දාන්න. CSV columns `url,relationship`; values own_sample/competitor/inspiration/research. Save පසු Not researched පෙන්විය යුතුය; keyword extraction තවම ක්‍රියාත්මක නැත.

7. Staff & permissions → Invite staff → private invitation link ලබාදෙන්න → account/site/bundle තෝරා Save assignment කරන්න. Incognito browser එකක staff invite link විවෘත කර password set/login කරන්න. Assigned website පමණක් පෙනිය යුතුය. Researcher හෝ Viewer ට publishing permission නැත. Email ස්වයංක්‍රීයව නොයවයි.

8. n8n http://localhost:5679 විවෘත කරන්න (5678 හි වෙනත් existing instance එකකි). Setup screen නම් ඔබගේ email/name/password යොදා වෙනම n8n owner සාදන්න. Sign-in screen නම් එම instance එකේ කලින් සෑදූ credentials භාවිත කරන්න. App password එක n8n සමඟ sync නොවේ.

Optional connection smoke: n8n හි අලුත් manual workflow එකක් සාදා Manual Trigger → HTTP Request nodes connect කරන්න. HTTP Request method GET, URL `http://web:8000/health/ready/`, authentication None. Execute workflow කළ විට `{ "status": "ready" }` ලැබිය යුතුය. මෙය network/health test පමණි; SEO automation workflow නොවේ. n8n container එක තුළ localhost වෙනුවට web භාවිත කළ යුතුය. Google/AI/customer credentials අවශ්‍ය නැත.

9. WordPress fixture:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wordpress-fixture.ps1
```

http://localhost:8081 හි DEMO page එක බලන්න. Admin අවශ්‍ය නම් http://localhost:8081/wp-admin/; username `fixture-owner`, password project `.env` හි `WP_FIXTURE_ADMIN_PASSWORD` අගය ඔබගේ editor එකෙන් privately බලන්න. Pages → SYNTHETIC Service Page → Company SEO metadata මගින් local metadata බලන්න. Settings → Company SEO ownership බලන්න. මෙය synthetic local fixture එක පමණි; noindex privacy වෙනස් නොකරන්න. Fixture metadata manually වෙනස් කළොත් smoke assertions මුල් expected values සමඟ නොගැළපිය හැක.

10. Automated checks:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
python scripts/smoke.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-restore.ps1
```

Smoke සඳහා WordPress fixture සහ n8n running විය යුතු අතර host Python අවශ්‍යයි. සාමාන්‍ය app setup/check සඳහා host Python අවශ්‍ය නැත. Plugin ZIP: `dist/company-seo-connector-0.1.0.zip`.

Error diagnosis:

- Docker pipe/connection error: Docker Desktop engine ready ද බලන්න.
- Organization already initialized: bootstrap නැවත නොකර existing login හෝ pending invitation reissue භාවිත කරන්න.
- Login temporarily limited: failed attempts 5 කින් පසු විනාඩි 15 රැඳී සිටින්න.
- Password setup හි `Origin checking failed - null` නම්: අලුත් invitation link එක reissue කර URL එක copy කර Chrome/Edge/Firefox address bar එකේ සෘජුව paste කරන්න. VS Code/embedded preview වෙනුවට සාමාන්‍ය browser tab එක භාවිත කරන්න. පැරණි page tab එක close කර fresh page එක load කරන්න. CSRF අක්‍රිය කිරීම හෝ null origin trusted කිරීම අවශ්‍ය නැත. App referrer policy strict-origin සහ invitation page no-store ලෙස නිවැරදි කර ඇත.
- Queued job නොවෙනස් නම් `docker compose logs --tail 80 worker`; lost queue recovery සඳහා `docker compose exec web python manage.py recover_jobs`.
- Page error: `docker compose logs --tail 80 web`.
- n8n error: `docker compose logs --tail 80 n8n`.
- `docker compose down -v` ධාවනය නොකරන්න; එයින් local persistent data මැකේ.
