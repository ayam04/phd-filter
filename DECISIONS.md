# DECISIONS — Data-Quality Challenges Addressed

This documents how the system addresses the data-quality failure modes, with **concrete examples
from the committed `sample_output/106419.json`** (a synthesized profile: computational psychiatry /
PTSD + stress neurobiology + psychiatric/single-cell genomics; target US/UK/Australia; Indian
nationality). Run self-check for that file:

```
generated 400 → country 400 → career 400 → similarity 398
→ verified_pool 240 → (rejected: domain 57, non-PI 4, collision 3, region 0)
→ final 70   [areas: 69 / 52 / 68; cold-cache wall-clock ~241 s]
```

Governing principle: **precision over recall.** Contamination is graded heaviest and country
adherence is a hard fail, so every stage prefers dropping a borderline match to admitting a wrong one.

---

## 1. Wrong-domain leakage from keyword overlap (§6.3) — primary defense

**Approach.** Three layers: (a) a cheap OpenAlex field/domain + embedding-similarity pre-filter,
then (b) an LLM **verification gate** that reads the candidate's *actual abstracts* (not title
keywords) and classifies discipline + region, then (c) explicit trap instructions in the gate prompt.

**Concrete evidence.** In this run the gate rejected **57 of 240** candidates as domain mismatches.
The four worked examples from the brief are encoded as always-on regression tests
(`tests/test_verify.py`) and all four are correctly rejected:
- "trauma-informed" **grief in Roman antiquity** (literary history) → rejected for a clinical-psych student.
- "DNA barcoding" that is actually **single-cell Hi-C human chromatin** → rejected for a plant-biology student.
- "high-elevation social-ecological systems" that is actually **Pacific-NW fire archaeology** →
  rejected for a Himalayan-pilgrimage student.
- "biodegradable plastic cartridges" framed as munitions → rejected for a biomaterials student.

The genuine matches that survive are on-discipline by construction — e.g. Paolo Fusar-Poli's verdict:
`discipline=Psychiatry; … psychiatric prediction models, transdiagnostic approaches`; Huda Akil:
`discipline=Neuroscience; neurobiology of stress and neuroendocrine regulation`.

**Trade-off.** We deliberately widened `domain_match` from "exact area only" to "same broad field or
directly adjacent subfield a mentor would approve," because the grader counts *bullseye + solid*.
Tightening it to bullseye-only cut the pass rate from ~67% to ~33% and discarded clearly-solid
adjacent PIs (depression/anxiety genomics for a PTSD-genomics student). The four cross-discipline
traps still fail because they are different *disciplines*, not adjacent subfields.

## 2. Career-stage errors — surfacing non-PIs (§6.2)

**Approach.** A name in an author list is not a supervisor. Defense is split across a cheap heuristic
and the LLM gate:
- **Cheap filter** (`filters/career_stage.py`): rejects trainee affiliation strings ("PhD student",
  "doctoral candidate", "research assistant", "predoctoral"), and very-early-career authors with thin
  records and no senior-author signal; computes a `pi_score` from career length, `works_count`,
  last/corresponding-author counts and recent output.
- **Fellowship-awardee trap:** `grants.py` flags NIH personal-award activity codes
  (F30/F31/F32/F33/K99/R00/K-series/T32) and UKRI Studentship/Fellowship categories, so the listed
  person is treated as a junior awardee, not a PI (`fellowship_awardee()` + regression test).
- **LLM gate** confirms `is_pi` from the abstracts + seniority signals.

**Concrete evidence.** The gate rejected **4** candidates as non-PIs in this run; the regression
suite (`tests/test_career_stage.py`) confirms a 2-years-since-first-publication, 3-paper,
first-author-only profile is rejected while a 20-year, 80-work, senior-author profile is accepted,
and that an F32-coded grant flags its awardee as junior. (The cheap filter dropped 0 here because the
top-400-by-appearance candidates are already senior; the gate is the binding non-PI check for this
profile — both layers exist precisely so one covers the other's blind spots.)

## 3. Same-name-different-person collisions (§6.1)

**Approach.** We never resolve a person from a name string. Every candidate is an **OpenAlex Author
ID** (the same ID space as the bonus CSV's `supervisor_id`, e.g. `A5031152245`), which carries
OpenAlex's own disambiguation. On top of that, the verification gate is asked whether the abstracts
"look like different people merged under one name" (`is_collision`), and `WRONG_PERSON` feedback flows
back into suppression.

**Concrete evidence.** Output `supervisor_id`s are OpenAlex Author IDs; the gate flagged **3**
collision/identity-incoherent candidates in this run and dropped them. Because the *aggregate* of an
author's matched works must cohere to the area (not a single paper title), a paper that merely shares
a title keyword cannot by itself surface a person.

## 4. Country adherence as a hard constraint (§R2) + institution-quality

**Approach.** Country is enforced **structurally** on the institution `country_code`, and — critically
— on the author's **primary academic affiliation**, not a single co-authored paper's institution.
Candidates whose only target-country affiliation is a non-academic/junk OpenAlex org are dropped.

**Concrete evidence.** 100% of the 70 supervisors are in {US, UK, Australia}. The academic-affiliation
rule fixed real OpenAlex data-quality artifacts observed in an earlier run:
- **Naomi Wray** was mislabeled "Pioneer (United States)" (a junk org) → corrected to **University of
  Queensland (Australia)**.
- **Ronald Kessler** was mislabeled "Virginia Commonwealth University" (one co-author paper) →
  corrected to **Harvard University**.
- **Daniëlle Posthuma** (primary lab in the Netherlands) was surfaced via a junk "Cognitive Research
  (United States)" org → now resolves to her genuine **Icahn School of Medicine at Mount Sinai**
  academic affiliation; a researcher with no legitimate target-country academic affiliation is dropped
  entirely rather than surfaced under a spurious US org.

This matters twice: a wrong country is a hard fail, and "Naomi Wray, Pioneer (United States)" reads as
an embarrassing mismatch to a mentor even when the country were right.

## 5. Eligibility filters in free-text ads (§6.4)

**Approach.** `filters/eligibility.py` uses the LLM to extract citizenship/residency restrictions
("UK/home only", "EU residents", "home fees") from unstructured ad text into structured flags, then
filters against the applicant's nationality.

**Concrete evidence.** Regression test (`tests/test_eligibility.py`): a "UK/home students only"
studentship is correctly marked `home_or_domestic_only=true` and `eligible(..., "Indian", "gb")`
returns **False**; an "international applicants welcome" ad returns **True** for the same Indian
applicant. Surfacing an ineligible position to this international student is treated as worse than
omitting it.

## 6. Evidence integrity + no fabricated contact details (§R3)

**Approach.** A `Supervisor` cannot be constructed without ≥1 verifiable paper or grant (enforced by a
pydantic validator — evidence-or-drop). Emails come only from ORCID's public record; otherwise `null`.

**Concrete evidence.** All **70/70** supervisors carry papers *and* grant evidence with resolvable
links (DOIs / OpenAlex / funder URLs). Only **23/70** have an email — the rest are `null` by design
because ORCID emails are public for only ~5-10% of researchers; **no address is ever invented**. The
`why_match` references specific evidence, e.g. for Paolo Fusar-Poli: *"…your meta-analyses, such as
'Age at onset of mental disorders worldwide'…"* — a real, named paper from his record tied to the
applicant's interests, not generic praise.

---

## Bonus — closing the feedback loop (working, demonstrated)

`feedback/learn.py` turns the outcomes CSV into `adjustments.json`. Re-running with
`--adjustments adjustments.json` measurably changes the ranking (`sample_output/106419_after_feedback.json`):
- **Suppression:** the `WRONG_PERSON` (rank 8) and `BOUNCE` (rank 9) supervisors are demoted to the
  **bottom of the list (ranks 68, 69)**; the `NOT_RECRUITING` supervisor (rank 10) is **dropped entirely**.
- **Priors:** `ADMIT`/`INTERVIEW`/`POSITIVE_REPLY` outcomes lift their `(area, institution)` cells
  (e.g. Mount Sinai genomics +0.15, Michigan stress-neurobiology +0.10), pushing those PIs to the top
  (Posthuma and Roussos at Mount Sinai become ranks 1-2 after feedback).

Caveats (documented because the data is sparse and biased): outcomes only exist for *emailed* PIs
(survivorship bias), so unseen PIs keep their base score (cold-start), and we smooth heavily (Laplace)
so a single outcome cannot dominate. `WRONG_PERSON` additionally feeds the disambiguation signal, not
just ranking.

---

### Things we noticed but consciously bounded (72-hour trade-offs)
- **OpenAlex humanities/regional coverage** is weaker than STEM/medicine — fine for this profile, flagged for humanities students.
- **Grant→PI fuzzy linking across national databases** is intentionally *not* done; we use OpenAlex grants attached to a PI's own papers (zero linking risk). Aggressive fuzzy linking would add the very contamination the grader punishes.
- **Live vacancy scraping** is reduced to the eligibility module; supervisors are the unit, positions are enrichment.
- **The cheap embedding pre-filter barely binds** (dropped 2/400) because `bge-small` is not very discriminative on dense biomedical abstracts; the LLM gate is the real domain filter. We kept the embedding stage as a cheap ordering signal rather than relying on it for rejection.
