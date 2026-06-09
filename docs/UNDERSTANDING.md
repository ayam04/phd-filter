# PhD Shortlist Builder — Understanding & Decision Log

This is the master rationale document. It explains **what** the system does, **why** every
significant technical and product-logic choice was made, and the **trade-offs** accepted. Source code
carries no comments by design; all reasoning lives here.

---

## 0. The problem in one paragraph

The goal is a personalised list of 50-200 PhD **supervisors** (principal investigators) for a
student, each with verifiable evidence and a personalised reason-to-contact, restricted to the
student's target countries, with as few embarrassing mismatches as possible. The hard part is not
calling an LLM — it is the **data**: finding the right humans, in the right field, at the right
career stage, in the right country, and proving it.

## 1. The governing principle: precision over recall

A wrong pick (**contamination** — wrong-domain / wrong-person / non-PI) is far more damaging than a
missed borderline-correct one, and **country adherence** is a hard requirement. The guiding rule of
thumb: an 80%-correct list of 60 beats a 60%-correct list of 150.

**Decision:** Every stage of the system is a *filter that prefers dropping a borderline-correct
supervisor over admitting a wrong one.* We aim for the high end of mentor approval on a moderate
list (target ~60-90 supervisors) rather than maxing out at 200. This single principle explains most
of the choices below.

---

## 2. Technical decisions

### 2.1 Language & runtime — Python 3.12
Every data source here has clean HTTP/JSON access; the work is I/O-bound API orchestration plus
LLM calls. Python gives the fastest path with `httpx` (async), `pydantic` (schema), and the
official `google-genai` SDK. No heavyweight framework — the orchestration is explicit and auditable.

### 2.2 Architecture — OpenAlex-centric cheap-cascade + LLM verification gate (chosen over two alternatives)

**Chosen (A): one disambiguated primary source, cheap filters first, LLM gate last.**
Candidates come from OpenAlex; a cascade of *cheap* filters (country → career-stage → discipline →
embedding similarity) cuts thousands of authors down to ~150-250; only then does a Gemini
verification gate read real abstracts and make the expensive precision call; `why_match` text is
generated only for survivors.

**Rejected (B): multi-source aggregation with cross-source entity resolution.**
Pulling OpenAlex + Semantic Scholar + Crossref + national grant DBs and reconciling identities
across them would raise recall, but cross-source entity resolution is the single hardest
sub-problem here. Done imperfectly in a 72-hour window it *increases* contamination — the most
penalised axis — and hurts reproducibility and latency. Not worth it.

**Rejected (C): web-search / LLM-first sourcing.**
Letting an LLM browse and pick supervisors invites hallucinated people and papers — a contamination
catastrophe — and cannot guarantee country adherence or a minimum count, nor reproduce. We only
borrow web-style reasoning for the *eligibility text extractor*, never for sourcing.

### 2.3 Why OpenAlex is the backbone
- The feedback outcomes CSV uses `supervisor_id` values like `A5031856973` — **that is an OpenAlex
  Author ID.** Adopting that ID space means the shortlist's `supervisor_id` lines up directly with the
  outcome stream used by the feedback loop.
- Free (polite pool via `mailto`), no key, generous limits.
- **Author disambiguation is built in** — we resolve stable Author IDs, never name strings (directly
  attacks the same-name-collision failure mode).
- One call yields paper evidence (title, DOI, citations), institution + **country code**, author
  position (first/middle/**last**), and a **topic → subfield → field → domain** taxonomy used for
  discipline gating.
- Author objects give `summary_stats` (h-index), `works_count`, and `counts_by_year` — the raw
  material for career-stage detection.

### 2.4 Role of each secondary source (and why kept conservative)
- **NIH RePORTER (US grants):** clean PI names + **activity codes**. Used for (a) US grant evidence
  and (b) the **fellowship-awardee trap** — codes F31/F32/K99/T32 etc. mark the listed person as a
  junior awardee, not a supervising PI.
- **UKRI Gateway to Research (UK grants):** `grantCategory` flags Studentship/Fellowship for
  career-stage signal. Its list endpoint exposes **no PI**, so we do *not* fuzzy-link it to specific
  authors (that would add contamination); it is best-effort UK grant context.
- **OpenAIRE (EU/AU fallback):** project-level grants (ARC for Australia, EC for EU). Project-level,
  no clean PI — used conservatively for evidence breadth.
- **ORCID:** seniority booster (role-title "Professor" vs "PhD Student") and best-effort public
  email. Email is public for only ~5-10% of researchers, so it is usually `null` — and we never
  fabricate one.

**Trade-off:** OpenAlex `grants` data is attached *directly to the PI's own papers*, so it carries
**zero linking risk**. That is our primary grant-evidence path. The national grant APIs are
enrichment; we deliberately avoid aggressive fuzzy name-matching across them because a wrong link is
exactly the contamination the design is built to avoid.

### 2.5 LLM — Gemini 2.5 Flash via OpenRouter + local embeddings
- The verification gate runs on ~150-250 candidates per shortlist; `why_match` on the survivors.
  This needs a **cheap, fast, high-throughput** model with structured-JSON output. **Gemini 2.5
  Flash** (the current successor to 2.0 Flash) fills exactly that role.
- **Access path:** we reach Gemini through **OpenRouter** using the OpenAI-compatible client. This
  was a forced, pragmatic call — the direct Google AI Studio key available was expired, while the
  OpenRouter key was valid and can serve the same Gemini Flash model. It keeps the LLM choice intact
  and makes the model swappable via `LLM_MODEL` (e.g. `google/gemini-2.5-flash`,
  `google/gemini-2.5-flash-lite`) with no code change.
- **Embeddings run locally** via `fastembed` (`BAAI/bge-small-en-v1.5`, ONNX, ~130MB one-time, CPU).
  OpenRouter has no embeddings endpoint, and a local model removes a network/key dependency from the
  hottest path entirely — *more* reproducible and zero marginal cost, which suits the cheap semantic
  pre-filter well.
- **Forced JSON** via `response_format={"type":"json_object"}` + defensive parsing makes every gate
  verdict machine-readable without brittle text scraping.

### 2.6 Caching — content-hash disk cache on every external call
Each OpenAlex/grant/ORCID/LLM/embedding result is written to `.cache/<namespace>/<hash>.json`. This
buys two key properties at once:
- **Reproducibility:** same input → same cached responses → same output.
- **Latency:** a cold run hits each unique endpoint once; warm re-runs complete in seconds, keeping
  us well under the 15-minute budget. `null` results (e.g. "no public email") are cached via file
  existence so they are not re-fetched.

### 2.7 Schema & the evidence-or-drop invariant
Output is modelled in `pydantic`. A `Supervisor` **cannot be constructed without at least one paper
or grant** — the evidence requirement is enforced by the type system, not by convention, so a
no-evidence pick can never reach the output file.

### 2.8 Concurrency
API fan-out and LLM gate calls run concurrently with a bounded width (`CONCURRENCY`) via async
`httpx` / `asyncio.gather`, balancing throughput against polite rate limits.

### 2.9 No comments in code
Per the maintainer's preference, source files contain no comments or docstrings. All rationale is
captured in this document and in `DECISIONS.md` / `schema.md`.

---

## 3. Business-logic decisions

### 3.1 Unit of recommendation = supervisor (PI), positions as enrichment
The student emails *professors*. So the atomic recommendation is a verified PI with evidence and a
personalised reason. "Linked PhD programs / open positions" are attached when available, but we do
not gate the whole pipeline on scraping live vacancies (which is brittle in 72h). Instead, vacancy
**eligibility** is handled as a focused module (3.6).

### 3.2 Country adherence — structural, not scored
Target countries are a hard constraint, so they are enforced as a **structural filter** on the
institution's `country_code`. Crucially, country is decided from the author's **current primary
academic affiliation** (most-recent-active, most-tenured academic institution in OpenAlex), not a
single co-authored paper's institution — a candidate whose primary academic home is outside the
target countries is dropped even if a stray paper carries a target-country co-affiliation. This was
hardened after our own audit found researchers based in the Netherlands/Norway leaking in via spurious
US co-affiliations (see DECISIONS §7). It is impossible for an out-of-country supervisor to reach the
output. (Hard-fail axis → zero tolerance.)

### 3.3 Who counts as a PI (career-stage, failure mode 6.2)
A name in an author list is not a supervisor. We compute a **multi-signal PI score**:
- years since first publication ≥ threshold (a grad student has a short record),
- **last-author / corresponding-author** count (seniority signal; juniors are first/middle authors),
- sustained recent output and total `works_count`,
- affiliation-string rejection of "PhD student / doctoral candidate / graduate researcher",
- **fellowship-awardee trap:** if the supporting grant is a personal fellowship (NIH F/K/T codes,
  MSCA individual, UKRI studentship), the listed person is the awardee — a junior — and is dropped
  or not treated as the PI.
Borderline cases are dropped (precision over recall).

### 3.4 Wrong-domain leakage (failure mode 6.3)
Keyword overlap is the classic trap ("trauma-informed" history project leaking into clinical
psychology; "DNA barcoding" single-cell work leaking into plant biology). Three layers defend:
1. **Discipline gate** using OpenAlex field/domain — a candidate whose primary field is outside the
   student's discipline set is dropped before any LLM cost.
2. **Embedding similarity** between the student profile and the PI's *actual abstracts* (not
   keywords) must clear a floor.
3. **LLM verification gate** reads the PI's top abstracts and classifies discipline **and region**,
   explicitly rejecting keyword-collision matches.
Four canonical real-world collision cases are encoded as regression tests that must be rejected.

### 3.5 Same-name-different-person (failure mode 6.1)
We never resolve a person from a name string. We resolve an **OpenAlex Author ID** whose *aggregate*
body of work matches the area, and the LLM gate sanity-checks that the top abstracts describe one
coherent researcher in the student's field. `WRONG_PERSON` feedback (bonus loop) flows back here.

### 3.6 Eligibility in free-text ads (failure mode 6.4)
For any vacancy text we have, an LLM extractor pulls citizenship/residency restrictions
("UK/home only", "EU residents", "home fees") into structured flags, and we filter against the
student's nationality. Surfacing an ineligible position to an international Indian student is treated
as worse than omitting it.

### 3.7 Evidence & contact integrity
Every supervisor carries ≥1 verifiable paper (DOI/OpenAlex link) or grant (funder link). Contact
email is taken from ORCID's public record when present, otherwise left `null` — **we never invent an
address**, because a wrong email is an embarrassing mismatch.

### 3.8 Ranking, tiers, and coverage
- **Score** blends embedding similarity (fit), evidence strength (citations, recency, grants), and a
  small coverage term.
- **Tier** (reach / target / safety) is assigned from institution strength relative to the
  student's profile, so the student gets a realistic spread.
- **Coverage balancing** uses per-area quotas (round-robin) so the list spans all stated interests
  instead of collapsing onto the single easiest area.

### 3.9 Feedback loop (bonus)
The outcomes CSV is ingested into a persisted `adjustments.json`:
- **Suppression:** `BOUNCE` / `WRONG_PERSON` / `NOT_RECRUITING` blocklist or hard-demote that
  supervisor; `WRONG_PERSON` additionally signals the disambiguation gate.
- **Priors:** smoothed success rates per `(area, institution)` and per tier from
  `ADMIT`/`INTERVIEW`/`POSITIVE_REPLY` (uplift) vs `REJECT`/`NO_REPLY` (weak signal).
- **Recruiting decay:** `NOT_RECRUITING` decays a PI/institution's recency weight.
The next run loads these and re-weights ranking — a deliberately simple learning-to-rank-lite scheme
chosen because outcome data is sparse and noisy, with documented caveats (survivorship bias,
cold-start for unseen PIs, heavy smoothing).

### 3.10 The synthesized sample profile (why this shape)
We build against a deliberately adversarial profile: research areas spanning **clinical psychology
/ PTSD** *and* **computational biology / single-cell genomics**, target countries **US + UK +
Australia**, nationality **Indian (international)**. This composition forces the system to
demonstrate, in its own output: the trauma-informed and DNA-barcoding domain traps being caught
(3.4), the US/UK/AU multi-grant-source handling (2.4), and the UK-only eligibility filter firing for
an international student (3.6). It is swappable — drop the real profile at the same path and re-run.

---

## 4. How decisions map to quality goals

| Quality goal | The decisions that serve it |
|---|---|
| Low contamination (top priority) | 1, 2.2, 2.4, 3.3, 3.4, 3.5 — filter-first, conservative linking, multi-layer domain + career gates |
| Country adherence (hard requirement) | 3.2 — structural country filter on the primary academic affiliation |
| Expert-approval of picks | 3.4, 3.5, 3.8 — domain/person verification + sensible tiering and personalised `why_match` |
| Coverage across areas | 3.8 — per-area quota balancing |
| Latency | 2.6 — aggressive caching + cheap cascade before any LLM call |
| Transparency | This document + `DECISIONS.md` with concrete examples from real output |

---

## 5. Known limitations & accepted trade-offs

- **Humanities / regional-venue coverage:** OpenAlex is strongest in STEM/medicine; some humanities
  or local-language venues are under-indexed. Acceptable given the sample profile's disciplines, and
  flagged for any humanities student.
- **Grant PI-linking:** we intentionally do *not* aggressively fuzzy-match national-grant PIs to
  OpenAlex authors; we lean on paper-attached OpenAlex grants instead. This trades some grant
  coverage for much lower contamination.
- **Live vacancies:** reduced to an eligibility module rather than a full vacancy scraper; positions
  are enrichment, not the primary unit.
- **Email obtainability:** frequently `null` by design — correctness over completeness.
- **Feedback data sparsity:** the learning loop is intentionally simple and smoothed; it nudges
  ranking rather than making strong claims from thin data.
