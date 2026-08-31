# Candidate Search — Chunked Retrieval (idea, not implemented)

## Origin

Raised after watching a tutorial on RAG/chunking: candidate search currently
embeds each CV as a single whole-document vector
(`CandidateProfile.profile_embedding` / `TalentPoolProfiles.profile_embedding`,
one 1536-dim vector per candidate) and compares it against the query/job
embedding via cosine similarity. The question raised: would chunking each CV
(e.g. one vector per job entry or section) and retrieving the best-matching
chunk per candidate produce better search results than one vector per CV?

## The real problem this would address: embedding dilution

A single whole-document embedding averages together everything in the CV.
If a candidate's CV covers 8 jobs across 3 pages, and "Kubernetes" appears
once, in job #6, that mention gets blended into one vector along with
everything else — it can score lower on a "Kubernetes experience" query than
it should, simply because it's diluted by unrelated content elsewhere in the
document. This is exactly the failure mode chunking exists to solve in RAG
systems generally: retrieval over long documents loses precision when
compressed into one vector.

## What chunking would look like here

- Split each CV into natural sections (per job entry, or by
  Experience/Education/Skills) rather than fixed-size token windows —
  fixed windows would cut mid-sentence through a CV and produce garbage.
- Generate one embedding per chunk (multiple vectors per candidate, not one).
- On search, retrieve the best-matching chunk(s) across all candidates, then
  map back to which candidate each chunk belongs to.

## Why this is not a clear-cut upgrade

1. **Trades holistic fit for granular recall — not a strict improvement.**
   A query like "senior backend engineer" often needs judging against the
   whole profile (seniority, breadth, trajectory), not one isolated bullet.
   A junior candidate whose one internship happens to mention "backend"
   could out-rank a genuinely senior candidate whose fit is holistic (no
   single chunk screams "senior"). Chunking swaps one failure mode
   (dilution) for another (loss of whole-profile context) — it does not
   simply return more correct results.

2. **Needs an aggregation step that doesn't exist today.** One row per
   candidate, one score, is the entire model right now. With N chunks per
   candidate, ranking requires a policy: best single chunk? Average of
   top-k? How to dedupe so one candidate doesn't appear to match multiple
   times? None of this is built, and getting it right is real design work,
   not just a schema change.

3. **Cost and storage multiply.** More embedding calls at ingestion time
   (one per chunk instead of one per CV) and a pgvector index sized by
   total chunk count rather than candidate count. Not prohibitive at current
   scale, but not free either.

4. **Chunk boundaries require real design work.** Naive fixed-token-window
   chunking (the default in most RAG tutorials) would frequently cut CV text
   mid-sentence. Chunking by natural CV structure (per job entry, per
   section) is the right approach but needs its own extraction logic on top
   of whatever CV-parsing output already exists.

## The strongest argument in favor: explainability, not recall

The more compelling reason to eventually do this isn't score accuracy — it's
that chunking would let the UI show *why* a candidate matched: "matched:
'led backend team of 5 engineers using Kubernetes'" instead of just a bare
score. That directly addresses the trust problem raised earlier this project
(employers not understanding why a score is low, or trusting a score with no
visible reasoning) — arguably a stronger case for building this than the
recall improvement itself.

## Recommendation if this is picked up later

Don't build the full chunked-retrieval pipeline speculatively. First:

1. Pick a handful of known long CVs where a clearly-relevant skill is buried
   deep in the document, and confirm dilution is actually costing real
   matches today (i.e. that candidate scores unexpectedly low on a query
   that should hit).
2. If confirmed, prototype chunking by natural CV section (not fixed token
   windows) on a small sample before committing to a schema change.
3. Design the ranking/aggregation policy (best-chunk vs top-k average vs
   something else) explicitly, rather than defaulting to whichever is
   easiest to implement.
4. Consider building this primarily for the explainability payoff (showing
   the matched excerpt), with improved recall as a secondary benefit, not
   the other way around.

## Status

Documented only — not scoped, not started. This is a separate feature-sized
project from [`application-match-score-unification.md`](application-match-score-unification.md)
(which fixed a bug in an already-working embedding pipeline); this is a
proposed architecture change on top of a pipeline that already works
correctly. Revisit when ready to prioritize.
