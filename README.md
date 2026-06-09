# PhD Shortlist Builder

Ingests a student profile JSON and produces a ranked, contamination-controlled shortlist of PhD
**supervisors** (principal investigators) in the student's target countries — each with verifiable
paper/grant evidence and a personalised `why_match` the student can use when emailing the professor.

Built for the Ambitio AI-Engineer take-home. The design rationale (every technical and
business-logic decision, with trade-offs) lives in **[`docs/UNDERSTANDING.md`](docs/UNDERSTANDING.md)**;
the failure-mode write-up with concrete examples is in **[`DECISIONS.md`](DECISIONS.md)**; the output
contract is in **[`schema.md`](schema.md)**.

## Approach in one line

OpenAlex-centric candidate generation → a cheap filter cascade (country → career-stage → discipline
→ embedding similarity) → an LLM verification gate that reads real abstracts and kills wrong-domain /
wrong-person / non-PI matches → ranking, tiering and per-area coverage balancing → an evidence-grounded
`why_match`. Everything is cached to disk for reproducibility and speed.

Guiding principle: **precision over recall.** Contamination is graded most heavily and country
adherence is a hard fail, so every stage prefers dropping a borderline match to admitting a wrong one.

## Data sources (all cited, all free)

| Source | Role | Link |
|---|---|---|
| **OpenAlex** | Backbone: candidate PIs, paper evidence (DOIs), institution + country, career signals, topic taxonomy. Author IDs match the bonus CSV's `supervisor_id` space. | https://openalex.org |
| **NIH RePORTER** | US grant evidence + fellowship-awardee (career-stage) detection via activity codes. | https://api.reporter.nih.gov |
| **UKRI Gateway to Research** | UK grant context + studentship/fellowship flags. | https://gtr.ukri.org |
| **OpenAIRE** | EU/Australia grant/project fallback. | https://www.openaire.eu |
| **ORCID** | Best-effort public email + employment role (seniority booster). | https://orcid.org |
| **Gemini 2.5 Flash** (via OpenRouter) | Profile normalization, the verification gate, eligibility extraction, `why_match`. | https://openrouter.ai |
| **fastembed** (`bge-small-en-v1.5`, local) | Semantic-similarity pre-filter. | https://github.com/qdrant/fastembed |

## Quick start

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows  (use: source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
cp .env.example .env            # then fill OPENROUTER_API_KEY (and OPENALEX_MAILTO)

python run.py --profile data/sample_student.json --out sample_output/106419.json
```

That one command runs the whole pipeline end-to-end and writes the shortlist JSON. Re-runs hit the
disk cache and finish in seconds.

### CLI options

| Flag | Meaning |
|---|---|
| `--profile` | path to the student profile JSON (required) |
| `--out` | output shortlist path |
| `--target` | desired shortlist size (default 70/80) |
| `--adjustments` | path to a feedback `adjustments.json` (see below) |

Scope/latency knobs are environment variables (`CANDIDATES_PER_AREA`, `ENRICH_LIMIT`,
`VERIFY_LIMIT`, `TARGET_TOTAL`) — see `src/config.py`.

## Configuration (`.env`)

```
OPENROUTER_API_KEY=...                 # required for the LLM stages
LLM_MODEL=google/gemini-2.5-flash      # any OpenRouter chat model
OPENROUTER_BASE=https://openrouter.ai/api/v1
EMBED_MODEL=BAAI/bge-small-en-v1.5     # local fastembed model
OPENALEX_MAILTO=you@example.com        # OpenAlex polite pool
```

> The pipeline standardises on **Gemini 2.5 Flash through OpenRouter** (the available direct Google
> key was expired; OpenRouter serves the same Gemini model). Embeddings run **locally** via fastembed,
> so the hottest path needs no embedding key or network. See `docs/UNDERSTANDING.md` §2.5.

## Output

A single JSON shortlist (full contract in `schema.md`). Each supervisor carries `name`, `institution`,
`country`, `contact_email|null`, `research_focus`, `matched_areas`, `tier`, `evidence` (papers/grants
with links), `why_match`, `linked_programs`, `scores`, and the `verification` verdict. The top-level
`summary.contamination_self_check` reports the per-stage funnel so the filtering is auditable.

## Bonus — closing the feedback loop

```bash
python -m feedback.learn --outcomes data/sample_outcomes.csv --out adjustments.json
python run.py --profile data/sample_student.json --out sample_output/106419.json --adjustments adjustments.json
```

`feedback/learn.py` turns the outcomes CSV into `adjustments.json`: it blocklists supervisors with
`WRONG_PERSON`/`BOUNCE`/`NOT_RECRUITING`, and builds smoothed per-`(area, institution)` success priors
from `ADMIT`/`INTERVIEW`/`POSITIVE_REPLY` vs `REJECT`/`NO_REPLY`. The next run loads these and
re-weights ranking. Rationale and caveats: `docs/UNDERSTANDING.md` §3.9.

## Tests

```bash
pytest -q            # all tests (unit + live)
pytest -q -m "not live"   # unit only (no network/LLM)
```

The suite includes the four PDF keyword-collision cases (must be rejected by the gate), the
career-stage regression (grad students rejected, senior PIs kept), the country gate, the eligibility
extractor, and schema validation.

## Design trade-offs & known limitations

- **Precision over recall by design** — a smaller, cleaner list is the explicit goal.
- **OpenAlex coverage** is strongest in STEM/medicine; some humanities/regional venues are
  under-indexed (flagged for humanities profiles).
- **Grant PI-linking is deliberately conservative** — we use OpenAlex grants attached to a PI's own
  papers (zero linking risk) rather than aggressively fuzzy-matching national-grant PIs, which would
  add contamination.
- **Live PhD vacancies** are reduced to a documented eligibility module; supervisors are the primary
  unit, positions are enrichment.
- **Contact email** is frequently `null` by design — correctness over completeness; never fabricated.
- The **feedback loop** is intentionally simple (sparse, noisy outcome data → heavy smoothing).

## Latency

Cold run (full network + LLM, single laptop): **~__FILL__ minutes** for the sample profile. Warm
re-runs (cache hit): seconds. Well within the < 15-minute target.

## Repository layout

```
run.py                  single-command entrypoint
src/                    profile, candidates, filters/, verify, rank, why_match, pipeline, sources/
feedback/               outcomes-CSV ingest + learn
data/sample_student.json
sample_output/          generated shortlist(s)
tests/                  unit + live regression tests
docs/UNDERSTANDING.md   master decision log
DECISIONS.md            failure-mode write-up with concrete examples
schema.md               output schema
```
