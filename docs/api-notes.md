# API Notes (live-verified 2026-06-09)

Condensed, implementation-ready contracts for every data source. Verified by hitting live endpoints.

## OpenAlex — backbone (no key; pass `mailto` for the polite pool)
- **Works search:**
  `GET https://api.openalex.org/works?filter=authorships.institutions.country_code:us|gb|au,from_publication_date:2018-01-01&search=<terms>&sort=cited_by_count:desc&per_page=100&select=<fields>&mailto=<email>`
- **select fields:** `id,title,publication_year,doi,cited_by_count,authorships,primary_topic,grants,abstract_inverted_index`
- **authorship:** `author_position` (first/middle/last), `is_corresponding`, `author.{id,display_name,orcid}`, `institutions[].{id,display_name,country_code,type}`, `raw_affiliation_strings`.
- **primary_topic:** `{id, display_name, score, subfield{}, field{display_name}, domain{display_name}}` → discipline gate.
- **grants on a work:** `grants: [{funder, funder_display_name, award_id}]` → paper-attached grant evidence, **no cross-source linking risk**.
- **author object** `GET /authors/{id}?select=id,display_name,orcid,summary_stats,works_count,counts_by_year,affiliations,topics,x_concepts`:
  `summary_stats.{h_index,i10_index,2yr_mean_citedness}`, `works_count`, `counts_by_year[].{year,works_count}` (first-pub year = min year; recent output = sum recent years), `affiliations[].institution.{display_name,country_code,type}`.
- **institution** `GET /institutions/{id}?select=display_name,country_code,type,works_count,cited_by_count,h_index` → prestige for tiering.
- **abstract decode:** invert `abstract_inverted_index` (word→positions) back to text.
- Country codes are UPPERCASE in responses (`US`), filter values lowercase (`us`).

## NIH RePORTER — US grants + career-stage (POST)
- `POST https://api.reporter.nih.gov/v2/projects/search` (`Content-Type: application/json`), ≤1 req/s.
- payload: `{"criteria":{"advanced_text_search":{"operator":"and","search_field":"projecttitle,abstracttext,terms","search_text":"<q>"},"fiscal_years":[2023,2024,2025,2026]},"offset":0,"limit":50,"include_fields":["ProjectNum","ProjectTitle","Organization","PrincipalInvestigators","ActivityCode","FiscalYear","ProjectDetailUrl"]}`
- result fields: `project_num, project_title, principal_investigators[].{full_name,title}, organization.org_name, activity_code, fiscal_year, project_detail_url`.
- **Fellowship/junior activity codes (awardee is NOT a PI):** F30,F31,F32,F33,F99,K00,K01,K08,K23,K24,K25,K43,K99,R00,T32,T15,T90. PI `title` like `RESEARCH FELLOW` is a junior signal.

## UKRI Gateway to Research — UK grants (GET)
- `GET https://gtr.ukri.org/api/projects?q=<terms>&fetchSize=50&page=1` with header `Accept: application/json` (vendor types → 406).
- `projectsBean.projects[].{id,title,grantCategory,status,abstractText,fund.valuePounds,fund.funder.name,resourceUrl}`.
- `grantCategory ∈ {Research Grant, Studentship, Fellowship, Training Grant}` → career-stage flag. **List endpoint has NO PI/person** → PI-linking requires the org endpoint (heavy). Used as best-effort UK evidence, not for fuzzy PI linking.

## OpenAIRE — EU/AU grants fallback (GET, no key)
- `GET https://api.openaire.eu/search/projects?keywords=<q>&participantCountries=AU&funder=ARC&format=json&size=20`
- nested `response.results.result[].metadata.oaf:entity.oaf:project.{title,code,fundingtree.funder.name,websiteurl,fundedamount}`. Project-level (no clean PI).

## ORCID — email + seniority (GET public, no token)
- `GET https://pub.orcid.org/v3.0/{id}/record` header `Accept: application/json`.
- email **almost always empty** (~5-10% public) → use if present, else `null`. **Never fabricate.**
- `activities-summary.employments.affiliation-group[].summaries[].employment-summary.role-title` → seniority booster ("Professor" vs "PhD Student"); freeform text → keyword match.

## google-genai SDK (`from google import genai`, v1.33+)
- `client = genai.Client(api_key=...)`
- JSON: `client.models.generate_content(model="gemini-2.0-flash", contents=..., config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=PydanticModel))` → `response.parsed` (or `response.text`).
- embed: `client.models.embed_content(model="text-embedding-004", contents=[...])` → `response.embeddings[i].values` (list[float]). Async: `client.aio.models.*` + `asyncio.gather`.

> **Cost note:** OpenAlex is used via the free polite pool (mailto). We cache every call to disk, so a full run hits each unique endpoint once; re-runs are free and deterministic.
