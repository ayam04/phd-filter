# PhD Shortlist Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build a single-command system that ingests a student profile JSON and emits a ranked, contamination-controlled shortlist of 50–200 PhD supervisors with verifiable evidence and personalised `why_match`.

**Architecture:** OpenAlex-centric candidate generation → cheap filter cascade (country/career-stage/domain/embedding) → Gemini LLM verification gate → ranking+tiering → `why_match` generation → schema-validated JSON. Everything cached to disk. Plus a feedback-loop module that learns from an outcomes CSV.

**Tech Stack:** Python 3.12, `httpx` (async API calls), `pydantic` v2 (schema), `google-genai` (Gemini 2.0 Flash + text-embedding-004), `numpy` (cosine), `tenacity` (retry), `pytest`. Data sources: OpenAlex, NIH RePORTER, UKRI Gateway to Research, OpenAIRE, ORCID.

---

## Phase 0 — Ground the API contracts (research, parallel)

Before coding, confirm the *current* request/response shapes for OpenAlex (works/authors/institutions filters + `select` fields, grants field, `summary_stats`), NIH RePORTER v2 POST, UKRI GtR, OpenAIRE, ORCID public API, and the `google-genai` SDK call shape for `gemini-2.0-flash` + `text-embedding-004`. Output: a `docs/api-notes.md` cheat-sheet. (No code; de-risks every later task.)

## File structure (locked)

```
src/config.py        # env + constants (thresholds, model names, target field maps)
src/llm.py           # Gemini wrapper: complete_json(), embed(); retry; cached
src/cache.py         # content-hash disk cache decorator + raw get/set
src/schema.py        # pydantic: StudentProfile, Area, PaperEvidence, GrantEvidence,
                     #          LinkedProgram, Supervisor, Shortlist
src/profile.py       # load_profile(path) -> StudentProfile ; normalize_areas() (LLM)
src/sources/openalex.py    # search_works(area, countries) , get_author(id) , get_institution(id)
src/sources/grants.py      # nih_reporter(area), ukri_gtr(area), openaire(area, country)
src/sources/email_finder.py# find_email(author) -> str|null  (ORCID + domain heuristic)
src/candidates.py    # generate_candidates(profile) -> list[Candidate]
src/filters/country.py     # passes_country(cand, countries) -> bool
src/filters/career_stage.py# pi_score(author) -> float ; is_pi(author) ; fellowship_awardee(grant)
src/filters/domain.py      # discipline_ok(cand, profile) ; region_ok(cand, profile)
src/filters/eligibility.py # extract_eligibility(ad_text) -> Eligibility ; eligible(elig, nationality)
src/verify.py        # verify_candidate(cand, profile) -> Verdict  (Gemini gate)
src/rank.py          # score(cand) ; assign_tier(cand, profile) ; balance_coverage(cands)
src/why_match.py     # generate_why_match(cand, profile) -> str
src/pipeline.py      # run(profile_path, out_path, adjustments_path=None) -> Shortlist
run.py               # argparse entrypoint -> pipeline.run()
feedback/ingest.py   # read_outcomes(csv_path) -> list[Outcome]
feedback/learn.py    # learn(outcomes) -> writes adjustments.json
data/sample_student.json
sample_output/<id>.json
tests/test_*.py
README.md DECISIONS.md schema.md requirements.txt .env.example
```

---

## Phase 1 — Foundations

### Task 1: Project scaffold + deps
**Files:** Create `requirements.txt`, `.env.example`, `src/__init__.py`, `src/config.py`, `tests/__init__.py`.
- [ ] requirements: `httpx pydantic google-genai numpy tenacity python-dotenv pytest pytest-asyncio rapidfuzz`
- [ ] `.env.example`: `GOOGLE_API_KEY=`, `GEMINI_MODEL=gemini-2.0-flash`, `EMBED_MODEL=text-embedding-004`, `OPENALEX_MAILTO=`
- [ ] `config.py`: load dotenv; constants — `PI_MIN_CAREER_YEARS=6`, `SIM_THRESHOLD=0.62`, `MIN_PAPERS=1`, per-area `CANDIDATES_PER_AREA=120`, `TARGET_TOTAL=80`, field-domain maps, current year.
- [ ] Commit.

### Task 2: Disk cache (`src/cache.py`)
**Test:** `tests/test_cache.py` — calling a wrapped fn twice hits the function once; cache key changes with args.
- [ ] `cached(namespace)` decorator hashing `(args, kwargs)` → JSON file under `.cache/<namespace>/<hash>.json`; `get/set` raw helpers. Handles async + sync.
- [ ] Test fails → implement → passes → commit.

### Task 3: Pydantic schema (`src/schema.py`)
**Test:** `tests/test_schema.py` — a minimal valid Supervisor + Shortlist construct; missing evidence raises.
- [ ] Models exactly as `schema.md` (see design §6). `Shortlist.summary` computed. Validator: supervisor must have ≥1 paper OR ≥1 grant else `ValueError`.
- [ ] Test → implement → commit. Then write `schema.md` from the models.

### Task 4: LLM wrapper (`src/llm.py`)
**Test:** `tests/test_llm.py` (mark `live`) — `embed("hello")` returns vector; `complete_json(prompt, schema)` returns dict. Mock-based unit test for retry/parse.
- [ ] `complete_json(system, user, response_schema)` using `google-genai` JSON mode; `embed(texts)->np.ndarray`; `tenacity` retry; both `@cached`.
- [ ] Unit test with monkeypatched client → implement → commit.

---

## Phase 2 — Sources

### Task 5: OpenAlex adapter (`src/sources/openalex.py`)
**Test:** `tests/test_openalex.py` (live, network) — `search_works("post-traumatic stress disorder treatment", ["US"])` returns works with author + institution + country; `get_author(id)` returns `summary_stats`, `works_count`, first-pub year.
- [ ] `search_works(query, countries, per_page, recency_years)` — `/works?search=...&filter=authorships.institutions.country_code:us|gb|au,from_publication_date:...&select=...`; polite pool mailto.
- [ ] `get_author(id)`, `get_institution(id)` with `select` to minimize payload; all `@cached`.
- [ ] Live test → implement → commit.

### Task 6: Grants adapters (`src/sources/grants.py`)
**Test:** `tests/test_grants.py` (live) — NIH RePORTER POST for "PTSD" returns awards with PI names + project URLs; UKRI GtR search returns projects; OpenAIRE returns projects. Each returns normalized `GrantEvidence` + a `grant_type` hint (fellowship vs project).
- [ ] `nih_reporter(query)`, `ukri_gtr(query)`, `openaire(query, country)` → normalized dicts with `funder`, `award_id`, `title`, `url`, `pi_names`, `is_personal_fellowship` (regex on activity/scheme codes: F31/F32/K99/F-series, MSCA-IF/PF, studentship).
- [ ] Live test → implement → commit.

### Task 7: Email finder (`src/sources/email_finder.py`)
**Test:** `tests/test_email_finder.py` — given an author with ORCID returns ORCID-listed email or `None`; never fabricates; domain-heuristic only proposes when institution domain known AND flagged `is_guess=True`.
- [ ] `find_email(author)` → ORCID public API email; else `None`. (Domain-guess kept conservative + clearly flagged; default `None`.)
- [ ] Test → implement → commit.

---

## Phase 3 — Profile + candidate generation

### Task 8: Profile normalization (`src/profile.py`)
**Test:** `tests/test_profile.py` — `load_profile(sample)` returns `StudentProfile`; `normalize_areas` (LLM, mocked) returns areas with `query_terms[]` + `discipline` + `region_hint`.
- [ ] `load_profile(path)`; `normalize_areas(profile)` LLM-expands each stated interest into search queries + discipline tag + expected region; extracts nationality from resume/profile.
- [ ] Test → implement → commit.

### Task 9: Candidate generation (`src/candidates.py`)
**Test:** `tests/test_candidates.py` (live, small) — for one area returns deduped candidates each with author meta + ≥1 paper; same author across two areas merges `matched_areas`.
- [ ] `generate_candidates(profile)` — fan out `search_works` per area; aggregate authorships→authors; fetch `get_author`; dedupe by Author ID; attach top papers (by citations, recent); attach matching grants by PI-name fuzzy match (rapidfuzz) within country.
- [ ] Live test → implement → commit.

---

## Phase 4 — Filter cascade (the contamination control)

### Task 10: Country filter (`src/filters/country.py`)
**Test:** `tests/test_country.py` — PI at a US institution passes for `["US"]`; PI at a German institution fails. 100% adherence is structural.
- [ ] `passes_country(cand, countries)`; commit.

### Task 11: Career-stage filter (`src/filters/career_stage.py`)
**Test:** `tests/test_career_stage.py` — synthetic grad-student (first-pub 2 yrs ago, only first-author, low works_count) → `is_pi=False`; senior PI → `True`; a candidate whose only evidence is an F31 fellowship → flagged awardee.
- [ ] `pi_score(author)` blends years-since-first-pub, last-author ratio, works_count, recent output; `is_pi` threshold; affiliation-string reject list; `fellowship_awardee(grant)` via `is_personal_fellowship`.
- [ ] Tests (the 6.2 cases) → implement → commit.

### Task 12: Domain filter (`src/filters/domain.py`)
**Test:** `tests/test_domain.py` — the four 6.3 adversarial abstracts vs their tempting student area → `discipline_ok=False`. A genuine match → `True`. `region_ok` rejects wrong continent/ecosystem.
- [ ] `discipline_ok` via OpenAlex field/domain set membership + embedding similarity floor; `region_ok` via embedding + LLM region tag.
- [ ] Tests (the 6.3 cases) → implement → commit.

### Task 13: Eligibility filter (`src/filters/eligibility.py`)
**Test:** `tests/test_eligibility.py` — "This studentship is open to UK/home students only" + Indian nationality → `eligible=False`; "International applicants welcome" → `True`.
- [ ] `extract_eligibility(ad_text)` (LLM JSON: `citizenship_restrictions[]`, `funding_for_home_only`); `eligible(elig, nationality)`.
- [ ] Tests → implement → commit.

---

## Phase 5 — Verify, rank, why_match

### Task 14: Verification gate (`src/verify.py`)
**Test:** `tests/test_verify.py` (live, small) — feeding a PI's real abstracts in the student's area returns `domain_match=True,is_pi=True`; feeding the trauma-informed-Roman-antiquity case returns `domain_match=False`.
- [ ] `verify_candidate(cand, profile)` → Gemini reads top abstracts+affiliation → `Verdict{domain_match, region_match, is_pi, is_collision, discipline, reason}`. Batched/concurrent. `@cached`.
- [ ] Test → implement → commit.

### Task 15: Ranking + tiers + coverage (`src/rank.py`)
**Test:** `tests/test_rank.py` — score monotonic in similarity & evidence; `balance_coverage` enforces per-area min; tiers assigned by institution strength.
- [ ] `score(cand, adjustments)`; `assign_tier`; `balance_coverage(cands, areas, target_total)` round-robin per area; apply feedback `adjustments` (suppression/priors) if present.
- [ ] Test → implement → commit.

### Task 16: why_match (`src/why_match.py`)
**Test:** `tests/test_why_match.py` (live) — output references at least one specific paper title/grant from the candidate's evidence; no banned generic phrases.
- [ ] `generate_why_match(cand, profile)` — Gemini, must cite specific evidence; post-check rejects/regenerates if it doesn't name evidence.
- [ ] Test → implement → commit.

---

## Phase 6 — Pipeline + entrypoint

### Task 17: Pipeline orchestration (`src/pipeline.py`)
**Test:** `tests/test_pipeline.py` (live, end-to-end small `TARGET_TOTAL=15`) — emits a Shortlist that validates, 100% in target countries, every PI has evidence, ≥1 per area.
- [ ] `run(profile_path, out_path, adjustments_path)` wires: profile→candidates→country→career→domain→embedding→verify→rank→why_match→emit. Logs per-stage drop counts (feeds contamination self-check + DECISIONS examples).
- [ ] Test → implement → commit.

### Task 18: Entrypoint (`run.py`)
**Test:** `tests/test_run_cli.py` — `python run.py --profile data/sample_student.json --out sample_output/x.json --target 15` exits 0 and writes file.
- [ ] argparse: `--profile --out --target --adjustments`. Commit.

---

## Phase 7 — Sample data, feedback loop, docs

### Task 19: Synthesized sample profile (`data/sample_student.json`)
- [ ] Realistic profile per design §9 (clinical-psych/PTSD + computational-bio; US/UK/AU; Indian nationality; education, projects, publications, interests, intake, intro-call summary, raw resume). Commit.

### Task 20: Feedback loop (`feedback/ingest.py`, `feedback/learn.py`)
**Test:** `tests/test_feedback.py` — sample outcomes CSV → `learn` writes `adjustments.json` with WRONG_PERSON/BOUNCE suppressed and ADMIT-area uplifted; re-run ranking reflects it.
- [ ] `read_outcomes(csv)`; `learn(outcomes)` → suppression set + smoothed `(area,institution)`/tier priors → `adjustments.json`. Wire `--adjustments` into pipeline.
- [ ] Test → implement → commit.

### Task 21: Full live run + sample_output
- [ ] Run end-to-end at `TARGET_TOTAL≈60` against live APIs+Gemini; save `sample_output/<student_id>.json`; capture wall-clock; verify 100% country + 0 obvious contamination on a manual top-10 skim.

### Task 22: Docs — README.md, DECISIONS.md, schema.md
- [ ] `README.md`: approach, data sources + citations, how-to-run (one command), trade-offs, limitations, latency numbers.
- [ ] `DECISIONS.md`: ≥5 failure modes with **concrete examples from our own output** (e.g., "candidate X dropped by domain gate: trauma abstract was Roman-antiquity history").
- [ ] `schema.md`: documented output schema.
- [ ] Commit.

### Task 23: Adversarial review + GitHub
- [ ] Self-audit pass over top-30 picks for contamination; fix gate thresholds if needed.
- [ ] Final `pytest` green; commit; (push to new GitHub repo when user authorizes).

---

## Test strategy notes
- **Live tests** marked `@pytest.mark.live` (need network + `GOOGLE_API_KEY`); unit tests mock LLM/network and always run.
- **Regression anchors:** the four 6.3 abstracts (Task 12) and the 6.2 grad-student/fellowship cases (Task 11) are the contamination guardrails — they must stay green.
- Cache makes live tests cheap on re-run.
