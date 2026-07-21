# AI Talent Match — Relevance Fix (Skill-Overlap Blending)

## Problem

Employer posts a "Machine Learning Engineer" job, opens AI Talent Match, and
sees clearly unrelated profiles (e.g. HR) at ~30% similarity. Low, but still
visible — feels wrong, and there was no floor hiding it either way.

## First attempt: fix the embedding text (didn't fully work)

Diagnosis: job embeddings only used narrative description fields
(`about_the_role`, `requirements`, etc.) — `title` and `required_skills` were
never included. Candidate/talent-pool embeddings used `current_title` +
`profession` + work-history text + `summary` — never `skills`. Fix: added
`title`/`required_skills` to the job embedding text, `skills` to the
candidate/talent-pool embedding text (`app/modules/ai/tasks.py`, hash
functions in `app/modules/ai/scoring_service.py`).

**Result after backfilling locally: scores went up, not down** (HR profile
moved from ~30% to ~40%).

**Why**: `text-embedding-3-small` cosine similarity between any two pieces of
well-formed professional English text sits in a narrow, high-ish band
regardless of topic — unrelated text isn't near 0%, often 30-50%. Adding
short "Job title: X / Skills: Y" lines inside much longer narrative text
adds shared boilerplate vocabulary across *every* profile without reliably
shifting the vector toward the specific skill/title content. Conclusion:
**pure embedding cosine similarity, however the input text is tuned, is not
a reliable relevance signal on its own.** The text change is still correct
to keep (title/skills should influence the vector), but it isn't sufficient.

## Actual fix: blend in a structured skill-overlap signal + a floor

Embeddings alone can't reliably separate professions. Added an explicit,
deterministic modulator based on `Job.required_skills` vs. candidate skills
(same source already used for the embedding text and display).

### `compute_skill_overlap_modulator` (`app/modules/ai/scoring_service.py`)

Reuses the existing `_skills_coverage` helper (already used for application
scoring) rather than reimplementing overlap matching.

```
if job.required_skills is empty:     modulator = 1.0   (unaffected — nothing to check)
elif candidate has no skills at all: modulator = 1.0   (unknown ≠ mismatch — don't penalize)
elif overlap == 0:                   modulator = 0.5   (confirmed mismatch — halved, not zeroed)
else:                                modulator = 0.5 + 0.5 * overlap_ratio
```

**Bug found immediately after shipping**: the "candidate has no skills at
all" branch was missing initially. A candidate with an empty skills list
(common — sparse CV parsing, self-registered candidates who never filled it
in) got the same 0.5 penalty as a *confirmed* mismatch, silently halving
almost every candidate whenever the job had `required_skills` filled in.
Symptom: a previously-visible 50% match disappeared entirely
(50 × 0.5 = 25, below the 40 floor). Fixed by treating "no data to judge"
and "confirmed zero overlap" as different cases — only the latter is
penalized.

Pure penalty, never a boost — full overlap preserves the embedding score
unchanged; it never inflates a score above what the embedding said.

`final_score = round(embedding_score * modulator)`

### Re-ranking, not just re-scoring (`get_job_matches`, `talent_pool/service.py`)

The SQL query orders by raw embedding distance and used to `LIMIT` there
directly. If the blend only adjusted the *displayed* number after fetching,
a candidate who ranks #25 by raw embedding distance but has full skill
overlap would never even get fetched. Fixed by:

1. Over-fetching — `min(limit × 4, 100)` by raw embedding distance instead of `limit`.
2. Scoring all of them with the blended formula.
3. Filtering below `_MIN_SIMILARITY_SCORE = 40` (the floor we'd discussed
   separately — implemented here since it's the natural backstop for the
   blend).
4. Re-sorting by `final_score` and slicing to the real `limit`.
5. Only *then* resolving the CV download URL (presigned URL + an extra
   query for admin-sourced profiles) — moved to run on the final sliced set
   instead of all ~100 over-fetched candidates, since most never survive the
   floor.

`TalentMatchResponse.from_match` now takes the final blended
`similarity_score` directly instead of deriving it from raw distance
internally — scoring needs `job.required_skills`, which the schema has no
access to, so that logic moved to the service layer.

## Round 3: the actual root cause (found via debug output)

The floor + modulator combo kept failing in both directions (over-hides,
then over-shows) because neither was the real problem. Added temporary
`debug_*` fields to `TalentMatchResponse` (since removed — diagnosis
confirmed, no longer needed) and inspected a live response — both "wrong"
matches turned out to be **non-CV documents**: one had
`candidate_name: "Mega D Building\nConstruction"` (a company, not a
person), the other's source file was `AuctionMarketplace_Presentation_v2.pdf`
— a presentation deck. Every structured field (title/profession/skills) was
null because there was nothing CV-shaped to extract. No amount of
scoring-formula tuning fixes garbage input — a bad document still gets a
"successful-looking" ~42% embedding score from whatever text was extracted,
for the same anisotropy reason as before.

**Real fix**: there's already an existing signal for this —
`ParsedCVSubmission.parse_status`, set to `FLAGGED` when
`overall_confidence < 0.6`, non-English, or scanned/OCR (`app/modules/ai/tasks.py`,
around the `run_extraction_pipeline` call). The match query never checked
it. Now it does:

- `find_matches_for_job` (`talent_pool/repository.py`) — added an outerjoin
  to `ParsedCVSubmission` and requires `parse_status == COMPLETED` for
  sourced-only profiles. Retroactive — fixes currently-visible bad matches
  immediately, no backfill needed.
- `_generate_talent_pool_embedding_async` (`ai/tasks.py`) — skips embedding
  generation entirely for non-`COMPLETED` parses going forward, so future
  garbage documents don't burn an OpenAI call at all.

**Known tradeoff**: this excludes *all* `FLAGGED` reasons, including
"Scanned PDF — OCR used" — a legitimately scanned CV with decent OCR gets
excluded too, not just genuinely-not-a-CV documents. If that turns out to
matter in practice, narrow the filter to specifically
`"Low confidence extraction" in flag_reasons` instead of the blanket
`parse_status != COMPLETED`.

## Tunable knobs (revisit after real usage)

- `_MIN_SIMILARITY_SCORE = 40` — initial guess, not measured.
- Modulator floor of `0.5` for zero overlap, and the `0.5 + 0.5·ratio` shape —
  arbitrary but reasoned (penalty, never boost).
- `_MATCH_OVERFETCH_MULTIPLIER = 4`, capped at `100` — balances re-ranking
  correctness against query cost.
- Skill matching is case-insensitive exact/substring, not semantic — "ML"
  won't match "Machine Learning". Acceptable for now; a real gap if it
  becomes noticeable.

## Verification

Run `scripts/regenerate_embeddings.py` locally (see script header for usage),
then re-check the AI Talent Match tab for the same ML-job/HR-profile case
before doing the same against production.
