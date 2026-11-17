# Owner setup / හිමිකරුගේ සැකසුම්

**Denim Yard සඳහා fields, Open/Edit/Delete, WordPress plugin සහ n8n පැහැදිලි පියවර:** [DENIM_YARD_WALKTHROUGH.md](DENIM_YARD_WALKTHROUGH.md).

වත්මන් login සහ test පියවර සඳහා [LOCAL_TEST_GUIDE.md](LOCAL_TEST_GUIDE.md) බලන්න. Pending owner invitation link නැති නම් `reissue_invitation --email ACCOUNT_EMAIL` command එකෙන් අලුත් single-use link එකක් ලබාගත හැක; active account passwords එයින් reset නොවේ.

## දැනට ක්‍රියාත්මක කරන පියවර

1. VS Code තුළ මෙම project folder එක විවෘත කරන්න. Terminal එක PowerShell විය යුතුය. Docker Desktop විවෘත කර Linux engine එක ready වනතුරු රැඳී සිටින්න.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/preflight.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose ps
```

`setup.ps1` මගින් `.env` සඳහා random secrets සාදයි; තිබෙන `.env` එක වෙනස් නොකරයි. සාර්ථක නම් web/worker/db/redis/n8n services healthy වන අතර migrate service එක exit code 0 පෙන්වයි. Docker pipe/connection error නම් Docker Desktop running ද බලන්න. Database password error නම් පැරණි volume එකේ credentials `.env` වෙනස් කළ පමණින් මාරු නොවන බව මතක තබාගන්න; volumes delete නොකරන්න.

2. පළමු company Super Admin account එක සාදන්න. පහත email/company ඔබගේ තොරතුරුවලට වෙනස් කරන්න.

```powershell
docker compose exec web python manage.py bootstrap_owner --email you@example.com --company "Your company"
```

Terminal එකේ ලැබෙන private URL එක browser එකෙන් විවෘත කර අවම අක්ෂර 12 සහිත strong password එකක් යොදන්න. Link එක පැය 24 කින් expire වේ; එක වරක් පමණක් භාවිත කළ හැක. Link එක chat/log/repository එකකට දාන්න එපා. මෙය product owner account එකයි; Django admin superuser එකක් නොවේ.

3. http://localhost:8000/accounts/login/ වෙත ගොස් email එක username ලෙස යොදා sign in කරන්න. Websites → Add website වෙතින් name, managed URL, staging/production, timezone, industry, services, audience, countries/languages, brand voice, verified facts, prohibited claims සහ conversion goals ඇතුළත් කරන්න. Profile save කළ විට **Not connected**, **No audit data** පෙන්වීම සාමාන්‍යයි. ඒවා සාර්ථක audit ප්‍රතිඵල නොවේ.

4. Staff & permissions පිටුවෙන් staff email එකට invitation සාදන්න. Private link එක එම පුද්ගලයාට පමණක් ලබාදෙන්න. Staff account, website, Researcher/Content Editor/Reviewer/Viewer bundle තෝරා assignment save කරන්න. Staff login කළ විට assigned websites පමණක් පෙනිය යුතුය. Reviewer permission එක publish permission එකක් නොවේ. Email ස්වයංක්‍රීයව යවන්නේ නැත.

5. Checks ධාවනය කරන්න:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
```

## පසුව අවශ්‍ය owner තොරතුරු — මෙම integrations තවම සම්පූර්ණ නැත

| පියවර | ඔබ ලබාදිය යුතු දේ | බලාපොරොත්තු වන අවසාන ප්‍රතිඵලය |
|---|---|---|
| Managed / reference URLs | ඔබගේ staging/managed URLs සහ sample/competitor URLs වෙන වෙනම; ව්‍යාපාරයේ සත්‍ය තොරතුරු | References කිසිවිටෙක publishing targets නොවිය යුතුය; Site overview → Reference websites මගින් manual URL/CSV input දැනට ඇත; research job තවම නැත. |
| WordPress plugin | Staging WP admin, selected SEO owner, dedicated connector user/Application Password over HTTPS | dist/company-seo-connector-0.1.0.zip දැනට ඇත; local custom-theme output පරීක්ෂා කර ඇත. Remote writes නැත. Django connection UI සහ Elementor පරීක්ෂණ තවම අවසන් නැත. |
| AI | Gemini API key සහ configured model ID; `.env` හි fields වෙන්කර ඇත, M1 ඒවා භාවිත නොකරයි | M4 live smoke test. Editor assistant subscription එකට වඩා API usage සඳහා වෙනම ගාස්තු ඇතිවිය හැක. |
| Google | Google Cloud project, OAuth consent/client/redirect, required API access, authorized GSC/GA4 properties | M6 OAuth UI මගින් account authorization කළ යුතුය. Code එකට consent bypass කළ නොහැක. |
| Keyword metrics (optional) | Licensed provider key/country/language/device හෝ CSV estimates | Provider නොමැතිවත් basic keyword extraction කළ හැකි වනු ඇත; volume unknown/null ලෙස පෙන්විය යුතුය. |
| n8n | http://localhost:5679 හි වෙනම owner account; පසුව workflow imports/credential bindings | M7 exports තවම නැත. Credentials JSON එකේ නොලැබේ. Container API URL `http://web:8000`; browser URL `http://localhost:8000`. Test webhook manual listener එකක් අවශ්‍යයි; production webhook activation පසුව පමණි. |
| Notifications (optional) | SMTP/internal recipients හෝ dev mail sink | දැනට email යැවීම අක්‍රියයි. Customer messages යවන්නේ නැත. |
| Staging approval | පළමු audit/diff සහ test title/description change | M4 apply/public verify/restore checks සමත් වූ පසුව staging පමණක්. |
| Production (later) | HTTPS/domain, secret rotation, MFA, backups/restore proof, policies | M8 release gates සහ explicit deployment authorization පසුව. |

Plugin/API/Google/n8n හි version-dependent exact integration commands ක්‍රියාත්මක කළ milestone එකේදී එකතු කෙරේ. දැනට සකසා නැති integrations සකසා ඇතැයි මෙම guide එකෙන් අදහස් නොවේ.

## දැනට ඇති local fixture සහ public audit

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wordpress-fixture.ps1
python scripts/smoke.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/package-plugin.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-restore.ps1
```

WordPress fixture එක http://localhost:8081 හි පමණක් DEMO label සහ noindex privacy සමඟ ධාවනය වේ. මෙය customer site එකක් නොවේ. `smoke.py` සඳහා host Python අවශ්‍යයි; සාමාන්‍ය setup සඳහා host Python/Node/PHP අවශ්‍ය නැත. Packaging script එකට host PHP නැති නම් Docker භාවිත වේ. PowerShell execution policy block වූ නිසා මෙහි process එකට පමණක් Bypass දී ඇත; computer-wide policy වෙනස් නොකරයි.

Site overview හි **Run public page audit** button එකෙන් තෝරාගත් managed URL එකේ එක page එක පමණක් read-only ලෙස බලයි. Robots policy, public DNS, HTTPS/HTTP accessibility අවශ්‍යයි. WordPress connection එකක් නැති බව එයින් වෙනස් නොවේ. Job status Refresh කර findings බලන්න. Queued job එකක් Redis interruption එකකින් අහිමි නම් operator විසින් `docker compose exec web python manage.py recover_jobs` ධාවනය කළ හැක. Full website crawl/keyword research/Google analytics/publishing දැනට සම්පූර්ණ නැත.
