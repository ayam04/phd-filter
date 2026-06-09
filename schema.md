# Output Schema — `sample_output/<student_id>.json`

The system emits one JSON object per student. It is produced and validated by the pydantic models
in `src/schema.py`; this document is the human-readable contract.

## Top level

| Field | Type | Notes |
|---|---|---|
| `student_id` | string | Echoes the input profile's id. |
| `generated_at` | string (ISO-8601) | UTC timestamp of generation. |
| `target_countries` | string[] | The student's hard country constraint, as given. |
| `summary` | object | Counts + the contamination self-check (below). |
| `supervisors` | Supervisor[] | The ranked shortlist, best first. |

## `summary`

| Field | Type | Notes |
|---|---|---|
| `total` | int | Number of supervisors emitted. |
| `by_tier` | object | Count per tier (`reach`/`target`/`safety`). |
| `by_area` | object | Count per matched area (a supervisor may count under more than one). |
| `contamination_self_check` | object | Per-stage funnel: `generated`, `dropped_out_of_country`, `dropped_career_stage`, `dropped_low_similarity`, `verified_pool`, `rejected_domain`, `rejected_non_pi`, `rejected_region`, `rejected_collision`, `final`. This is the system auditing its own filtering. |

## `Supervisor`

| Field | Type | Notes |
|---|---|---|
| `supervisor_id` | string | **OpenAlex Author ID** (e.g. `A5031856973`) — same ID space as the bonus outcomes CSV. |
| `name` | string | Display name. |
| `institution` | string | Primary affiliation in a target country. |
| `country` | string | Full country name (mapped from ISO code). |
| `contact_email` | string \| null | From ORCID public record if available, else `null`. **Never fabricated.** |
| `research_focus` | string | Short topic descriptor from OpenAlex topics. |
| `matched_areas` | string[] | Which of the student's areas this PI matched; the best-fit area is first. |
| `tier` | enum | `reach` \| `target` \| `safety` (by institution-strength percentile within the shortlist). |
| `evidence` | object | `{ papers: PaperEvidence[], grants: GrantEvidence[] }`. At least one entry is **guaranteed** (evidence-or-drop invariant). |
| `why_match` | string | Personalised rationale referencing the PI's specific work. |
| `linked_programs` | LinkedProgram[] | Best-effort program/department links with optional eligibility notes. |
| `scores` | object | `{ similarity, evidence, final }` floats — transparency into ranking. |
| `verification` | object | The LLM gate verdict (below). |

### `PaperEvidence`
`{ "title": string, "year": int|null, "doi": string|null, "url": string, "citations": int }` — `url` is always a resolvable link (DOI or OpenAlex work URL).

### `GrantEvidence`
`{ "title": string, "funder": string|null, "award_id": string|null, "url": string, "is_personal_fellowship": bool }` — sourced from OpenAlex awards on the PI's own papers (and, where enriched, national grant APIs). `is_personal_fellowship` flags the career-stage trap.

### `LinkedProgram`
`{ "name": string, "url": string, "eligibility_note": string|null }` — `eligibility_note` carries any extracted citizenship/residency restriction relevant to the applicant.

### `verification`
`{ "domain_match": bool, "region_match": bool, "is_pi": bool, "collision_checked": bool, "reason": string }` — the gate's decision and a one-line justification (includes the candidate's classified discipline). Every emitted supervisor has `domain_match=true`, `region_match=true`, `is_pi=true`.

## Example (one supervisor, trimmed)

```json
{
  "supervisor_id": "A5031856973",
  "name": "Jane Doe",
  "institution": "University of New South Wales",
  "country": "Australia",
  "contact_email": null,
  "research_focus": "Post-traumatic stress disorder, computational psychiatry",
  "matched_areas": ["Computational Psychiatry & PTSD Prediction"],
  "tier": "target",
  "evidence": {
    "papers": [{"title": "Predicting PTSD treatment response ...", "year": 2024, "doi": "https://doi.org/...", "url": "https://doi.org/...", "citations": 42}],
    "grants": [{"title": "NHMRC award ...", "funder": "NHMRC", "award_id": "GNT...", "url": "https://...", "is_personal_fellowship": false}]
  },
  "why_match": "Your interest in PTSD treatment-outcome prediction maps directly onto Doe's 2024 work on ...",
  "linked_programs": [{"name": "PhD programs at University of New South Wales", "url": "https://openalex.org/I...", "eligibility_note": null}],
  "scores": {"similarity": 0.78, "evidence": 0.66, "final": 0.71},
  "verification": {"domain_match": true, "region_match": true, "is_pi": true, "collision_checked": true, "reason": "discipline=Clinical psychology; abstracts confirm PTSD treatment research"}
}
```
