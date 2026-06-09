# PhD Shortlist Builder — Design Spec

**Date:** 2026-06-09
**Assignment:** Ambitio AI Engineer take-home — PhD Shortlist Builder (72h)
**Status:** Approved design, pre-implementation

---

## 1. Problem & grading-aligned objective

Ingest one **student profile JSON** and emit one **ranked shortlist JSON** of 50–200 PhD
**supervisors (PIs)** + linked programs, each carrying verifiable paper/grant evidence and a
personalised `why_match` referencing specific PI work.

The grader weights, in priority order:
1. **Contamination** (wrong-domain / wrong-person / non-PI) — *weighted heaviest*. Past systems 5–20%.
2. **Country adherence** — hard fail if any pick is outside target countries.
3. **Mentor-eye audit** — (bullseye+solid)/30 on the top 30. Past systems 60–85%.
4. **Coverage** — ≥50, spread across stated areas.
5. **Latency** — < 15 min wall-clock on one laptop / VM.
6. **Process quality** (`DECISIONS.md`) — *weighted heavily*.

> Design principle that follows directly from the weighting: **precision over recall.** An
> 80%-approved list of 60 PIs beats a 60%-approved list of 150. Every stage is a *filter that
> prefers dropping a borderline-correct PI over admitting a wrong one.*

## 2. Approach (selected: A)

**OpenAlex-centric cheap-cascade + LLM verification gate.** Rationale and rejected
alternatives (B multi-source entity-resolution; C web-search-first) are recorded in
`DECISIONS.md`. Key evidence for the choice: the bonus CSV's `supervisor_id` values
(`A5031856973`) are **OpenAlex Author IDs**, so OpenAlex is the natural backbone — it gives
disambiguated author identities, paper evidence with DOIs, institution + country, a topic/field/
domain taxonomy, and career-signal metadata, all from one free API.

## 3. Data flow

```
student_profile.json
  │
  ▼ [profile]   LLM-normalize → {areas[] with query terms + discipline tags,
  │             nationality, target_countries[], intake, student_seniority}
  ▼ [candidates] per area: OpenAlex works search (country + recency + topic filters)
  │             → aggregate authorships → candidate Author IDs (dedupe across areas)
  │             → attach grant evidence (OpenAlex work.grants + national grant APIs)
  ▼ [filter cascade]  (cheap → expensive, each prefers dropping over admitting)
  │   1 country      hard: institution country_code ∈ target_countries
  │   2 career_stage PI test (multi-signal) — reject grad students / postdocs / fellowship awardees
  │   3 domain       discipline gate (OpenAlex field/domain) — reject discipline mismatch
  │   4 embedding    cosine(profile, PI recent abstracts) ≥ threshold
  ▼ [verify gate]   Gemini reads PI top abstracts → {domain_match, region_match,
  │             is_collision, is_PI, discipline} — the decisive contamination kill
  ▼ [rank]      score = w1·sim + w2·evidence + w3·coverage ; tier (reach/target/safety) ;
  │             per-area quota balancing for spread
  ▼ [why_match] Gemini blurb citing SPECIFIC PI papers/grants (no generic praise)
  ▼ [emit]      schema-validated JSON → sample_output/<student_id>.json
```

Every stage is **cached to disk** (content-hash keys) so re-runs are deterministic and fast.

## 4. Failure-mode defenses (≥6 of the 15; concrete output examples go in DECISIONS.md)

| # | Failure mode | Defense |
|---|---|---|
| 6.1 | Same-name collision | Resolve **OpenAlex Author IDs**, never name strings; require the author's *aggregate* works to match the area; LLM coherence check on top abstracts. |
| 6.2 | Career-stage (non-PI) | Multi-signal PI test: years-since-first-pub ≥ θ, last/corresponding-author count, sustained recent output, affiliation-string reject ("PhD student", "doctoral candidate"), and the **personal-fellowship awardee trap** (NIH F31/F32, MSCA-IF, UKRI studentship → awardee is junior → drop or redirect to host PI). |
| 6.3 | Wrong-domain leakage | Discipline gate (OpenAlex field/domain) + embedding similarity on **abstracts not keywords** + LLM domain+region classifier. The four PDF cases (biodegradable cartridges, high-elevation, trauma-informed, DNA barcoding) become **regression tests** that must be rejected. |
| 6.4 | Eligibility in ad text | LLM extractor pulls citizenship/residency restrictions from vacancy text; filter against student nationality (international Indian → drop "UK/home-only"). |
| R2 | Country adherence (hard) | Filter on institution `country_code`; 100% guaranteed by construction. |
| R3 | Evidence-or-drop | No PI emitted without ≥1 verifiable paper (DOI/OpenAlex URL) or grant (funder URL). |
| — | Fabricated contact | Email only from ORCID / institution-domain heuristic, else `null`. **Never invent an address.** |

## 5. Module layout (standalone repo `phd-proj/`)

```
src/
  profile.py            # load + LLM-normalize student profile
  llm.py                # Gemini client (model + embeddings), retry, JSON-mode
  cache.py              # content-hash disk cache (API + LLM)
  schema.py             # pydantic models: StudentProfile, Supervisor, Shortlist
  sources/
    openalex.py         # works/authors/institutions; polite pool; rate-limited
    grants.py           # NIH RePORTER (US), UKRI GtR (UK), OpenAIRE (EU/AU fallback)
    email_finder.py     # ORCID + institution-domain heuristic (never fabricate)
  filters/
    country.py          # hard country filter
    career_stage.py     # PI seniority scoring + fellowship-awardee trap
    domain.py           # discipline + region classification (OpenAlex + embeddings)
    eligibility.py      # LLM eligibility extraction from ad text
  candidates.py         # per-area fan-out → candidate PIs
  verify.py             # LLM verification gate (collision + domain + career)
  rank.py               # scoring, tiering, per-area coverage balancing
  why_match.py          # personalised blurb referencing specific PI work
  pipeline.py           # orchestrates end-to-end
feedback/
  ingest.py             # parse outcomes CSV
  learn.py              # produce adjustments.json (suppression + priors)
run.py                  # single-command entrypoint
data/sample_student.json
sample_output/<id>.json
tests/                  # regression + schema + eligibility tests
README.md  DECISIONS.md  schema.md  requirements.txt  .env.example
```

## 6. Output schema (summary; full doc in `schema.md`)

```jsonc
{
  "student_id": "string",
  "generated_at": "ISO-8601",
  "target_countries": ["..."],
  "summary": { "total": 0, "by_tier": {...}, "by_area": {...}, "contamination_self_check": {...} },
  "supervisors": [{
    "supervisor_id": "OpenAlex Author ID (A...)",
    "name": "string",
    "institution": "string",
    "country": "ISO country",
    "contact_email": "string | null",
    "research_focus": "string",
    "matched_areas": ["..."],
    "tier": "reach | target | safety",
    "evidence": {
      "papers": [{ "title": "...", "year": 0, "doi": "...", "url": "...", "citations": 0 }],
      "grants": [{ "title": "...", "funder": "...", "award_id": "...", "url": "..." }]
    },
    "why_match": "string referencing specific PI work",
    "linked_programs": [{ "name": "...", "url": "...", "eligibility_note": "...|null" }],
    "scores": { "similarity": 0.0, "evidence": 0.0, "final": 0.0 },
    "verification": { "domain_match": true, "region_match": true, "is_pi": true, "collision_checked": true }
  }]
}
```

## 7. Bonus — feedback loop

`feedback/ingest.py` parses the outcomes CSV; `feedback/learn.py` emits a persisted
`adjustments.json`:
- **Suppression:** `BOUNCE` / `WRONG_PERSON` / `NOT_RECRUITING` → blocklist or hard demote that supervisor_id.
- **Priors:** smoothed success rate per `(area, institution)` and per `tier` from
  `ADMIT`/`INTERVIEW`/`POSITIVE_REPLY` (uplift) vs `REJECT`/`NO_REPLY` (weak signal).
- **Recruiting decay:** `NOT_RECRUITING` decays an institution/PI's recency weight.

Next run loads `adjustments.json` and re-weights ranking (learning-to-rank-lite). Documented
trade-offs: sparse data → heavy smoothing; survivorship bias (only emailed PIs get signal);
cold-start (unseen PIs keep base score); `WRONG_PERSON` feeds back into the disambiguation gate.

## 8. Reproducibility / latency / cost

- **Single command:** `python run.py --profile data/sample_student.json`.
- **Cache:** every OpenAlex/grant/LLM/embedding call cached by content hash → re-runs in seconds, deterministic.
- **Latency budget:** cheap cascade cuts thousands of authors → ~150–250 survivors before any LLM call; Gemini Flash batched/concurrent for the gate; `why_match` only for final picks. Target < 15 min cold, seconds warm.
- **Config:** `.env` → `GOOGLE_API_KEY`, `GEMINI_MODEL` (default `gemini-2.0-flash`), `OPENALEX_MAILTO` (polite pool).

## 9. Synthesized sample profile

A realistic profile chosen to exercise the failure modes:
- **Areas:** computational/clinical psychology (PTSD, trauma) + computational biology
  (single-cell genomics) — hits NIH + UKRI grants and the "trauma-informed" + "DNA barcoding"
  domain traps.
- **Target countries:** US, UK, Australia (multi-grant-DB; tests eligibility for an international Indian student).
- **Nationality:** Indian (international) → eligibility module must drop "UK/home-only" ads.

## 10. Testing

`pytest`: (a) the four 6.3 adversarial abstracts must be rejected by the domain gate; (b) a known
grad-student author must fail the PI gate; (c) a non-target-country PI must be filtered; (d) emitted
JSON validates against the schema; (e) eligibility extractor flags a "UK-only" ad for an Indian student.

## 11. Known limitations (to be expanded in README)

OpenAlex humanities/regional-venue coverage gaps; live PhD-vacancy sourcing reduced to a
documented eligibility module (supervisors first, positions as enrichment); grant-API
heterogeneity (US/UK first-class, EU/AU via OpenAIRE fallback); email obtainability is
best-effort and frequently `null` by design.
