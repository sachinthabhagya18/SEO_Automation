# URL research and metadata preview

## Try the local application

1. Open http://localhost:8000 and sign in with your existing company owner account. No account or password was reset.
2. For Denim Yard, open http://localhost:8000/sites/1/research/ and select **Analyze URL**. Refresh for the completed report. This reads public pages even while publishing is paused.
3. To onboard another managed website, use **Analyze a URL** on the overview, or http://localhost:8000/sites/discover/. Only the URL is required for an owner with one organization. The initial label comes from the hostname; the profile starts paused in production mode. Existing matching websites are reused.
4. Review collected titles, descriptions, missing/duplicate head tags, heading-based keyword candidates and source excerpts. The crawl samples up to five same-origin HTML pages, prioritizing category/about/contact links from the root. It respects robots and public-network restrictions. It is not a full website audit.
5. Open http://localhost:8000/sites/1/preview/. Enter values or fetch a managed public page. Google/Facebook/X/LinkedIn previews update in the browser. The same panel appears in the metadata draft editor. Previewing does not publish anything. Display, rewriting, cropping and caching differ on actual platforms.
6. Metadata drafts and separate review are at http://localhost:8000/sites/1/changes/. Existing unapproved product draft: http://localhost:8000/sites/1/changes/51dde149-c177-42d2-915e-f7c0ca688083/ . This targets WordPress product 89, not the homepage.

Owner-verified COD, Sri Lanka and English facts remain intact. Public shipping/payment banners are observations, not replacements for owner facts. PayHere remains planned. The homepage has no validated post-ID mapping; `homepage_mapping_missing` tracks the required homepage/site-default adapter. Product metadata does not update the homepage.

## Gemini configuration

The `gemini-api-dev` skill was applied. The integration uses the official `google-genai` SDK, Interactions API, typed structured output and `store=False`. No CrewAI/LangGraph runtime is used in this milestone: PostgreSQL research states and Celery already own execution. These libraries are not required just to call Gemini. A future multi-agent graph needs a separate durable-checkpoint design rather than a second independent publisher.

Privately edit the local `.env` file; do not paste API keys into chat:

```dotenv
GEMINI_API_KEY=your-private-key
GEMINI_MODEL=gemini-3.8-flash
RESEARCH_AI_ENABLED=true
```

Then recreate local services with `docker compose up -d web worker`. Select **Include Gemini profile hypotheses** for a research run. The configured model must support Interactions structured output; model availability is account dependent. No paid call is made by default. The live provider has not been accepted until a configured test succeeds.

Suggested starting model: [Gemini 3.8 Flash](https://aistudio.google.com/docs/models/gemini-3.8-flash), verified against current official documentation. It supports structured output; the model ID remains configurable.

Latest live check: key/model access returned HTTP 200, but generation did not produce accepted suggestions. The final bounded run returned `provider_http_503` after earlier timeouts. Reports now show the safe Gemini status explicitly. Configuration access is verified; generation acceptance remains pending. Do not repeatedly press Analyze to consume the remaining daily allowance during an unavailable-provider period. A later explicit run can retry after the service recovers; failed requests keep their reservations.

Limits: one call per run, 2,048 maximum output tokens, 90-second provider timeout with low thinking, five reserved calls per organization per Colombo calendar day, no automatic paid retry, no tools, no browsing or code execution by the model. A failed call consumes its reservation. Input consists of at most five bounded public-page excerpts plus selected owner facts, never connector credentials. These are call/token limits, not a monetary billing ceiling. Provider billing controls are still needed for a financial limit.

Only industry, products/services, audience and voice hypotheses are accepted. Every suggestion must cite one of the collected URLs; duplicate fields, unknown URLs and unsupported fields are rejected. Citing a URL does not prove entailment: human review is required. AI output does not update the profile or publish SEO. Search volumes, difficulty and ranking remain unknown. Automatic competitor discovery requires a search-data integration and is still unfinished; empty competitor results are not reported as a successful competitor analysis.

## WordPress custom post type

Local plugin 0.2.0 includes private **Settings → SEO Metadata Records** (`cseo_record`). Applied/restored title and description snapshots are mirrored into private CPT metadata with change UUID, target ID, state and revision hashes. Records are excluded from public search, frontend queries and REST. Only administrators can inspect them; the connector writer cannot edit them. CPT records do not contain credentials.

Native post metadata remains the actual tag renderer; the transactional SQL change ledger remains the idempotency/restore authority. The CPT is a post-commit history mirror. A mirror failure does not undo a committed metadata operation, and an automatic mirror-reconciliation job remains future work. Deactivation retains history. Live Denim Yard still has read-only plugin 0.1.0; this local source change was not uploaded there.

## Recovery and remaining work

`docker compose exec web python manage.py recover_research` re-dispatches queued research and expires old running executions for review, without retrying paid calls. Research uses a per-site active-run constraint and worker authorization rechecks. Other existing recovery commands cover audit/publication jobs.

Still required for complete SEO automation: search-backed competitors, demand data and keyword mapping; approved profile adoption; research-to-page-specific AI drafts; homepage/category adapters; complete crawl/sitemap/schema/performance/link checks; Search Console/GA4; policy and financial budgets UI; staging approval and production rollout; remaining n8n workflows; durable graph checkpoints if orchestration expands; reporting, monitoring and production hardening. None of these are implied complete by URL research or the preview UI.

Official references: [Gemini structured output](https://aistudio.google.com/docs/structured-output), [Interactions](https://aistudio.google.com/docs/interactions), [WordPress register_post_type](https://developer.wordpress.org/reference/functions/register_post_type/). Visual inspiration: [Meta Tags](https://metatags.io/).
