# Talent Pool Data Isolation + Introduction Routing — Phased Plan

Status: design agreed, not yet implemented.
Supersedes/extends: `docs/ai-talent-match-monetization.md` (introduction request
flow) with a data-isolation fix and a routing refinement.

## Context

AI Talent Match currently leaks: `find_matches_for_job` has no ownership
check, so Employer B's job postings can match against CVs Employer A
privately imported. Full analysis in the design-review discussion; this doc
is the resulting implementation plan.

Two independent problems, one plan:
1. **Data isolation bug** — sourced CVs are matchable by any employer.
2. **Introduction consent** — sourced candidates never consented to anything;
   self-registered candidates already did (via `cv_sharing_consent`).

## Ownership model (confirmed from code, not assumed)

`TalentPoolProfiles.added_by`:
- Self-registered candidates: `added_by = candidate's own user_id`
  (`users/repository.py:86-93`, set at registration).
- Sourced/imported CVs: `added_by = whoever uploaded it` — an employer or an
  admin (`talent_pool/service.py: submit`/`submit_batch`).

This means "added by employer or admin" **cannot** be a blanket filter — it
must only apply to sourced profiles (`candidate_profile_id IS NULL`). Applied
universally, it silently deletes every self-registered candidate from every
employer's results, since their `added_by` is never an employer or admin.

## The three profile categories a match can fall into

| Category | Condition | Introduction flow |
|---|---|---|
| Self-registered | `candidate_profile_id IS NOT NULL` | Automated — unchanged |
| Sourced, owned by requester | `candidate_profile_id IS NULL AND added_by == requesting employer` | Free "Notify for this role" — no credit, no ops queue |
| Sourced, owned by admin | `candidate_profile_id IS NULL AND added_by is an admin` | Credit-gated "Request Introduction" — routed to that specific admin |

(A fourth category — sourced by a *different* employer — should never reach
the frontend once Phase 1 ships; the match query excludes it at the source.)

## Phase 1 — Data isolation fix (backend, do this first)

- `talent_pool/repository.py: find_matches_for_job` — add the ownership
  condition **only inside the sourced-profile branch** of the existing
  `sa.or_(candidate_profile_id.is_(None), cv_sharing_consent.is_(True))`
  clause. Needs the requesting `employer_id` threaded into the query (already
  a param on `get_job_matches`, just wasn't passed down to the repo call —
  add it).
- New condition, sourced branch only: `added_by IN (:employer_id) OR added_by
  has role ADMIN` (subquery against `users`, same pattern already used in
  `talent_pool/repository.py: list()` lines 112-119 — reuse it, don't
  reinvent).
- No schema/migration changes — this is a WHERE-clause fix.
- **Ship this alone first, independent of everything below.** It's the
  actual security fix; the introduction-routing work is a UX refinement on
  top of an already-safe base.

## Phase 2 — Schema: tell the frontend which category a match is

`TalentMatchResponse` currently has no way to distinguish the three
categories — the frontend needs this to pick the right CTA.

- Add `ownership: Literal["self_registered", "own_sourced", "admin_sourced"]`
  (or similar) to `TalentMatchResponse`, computed in `get_job_matches` from
  `candidate_profile_id` + `added_by` (already loaded on `profile`, no extra
  query).

## Phase 3 — CV data exposure

- Add `cv_download_url: str | None` to `TalentPoolProfileResponse`, generated
  from `ParsedCVSubmission.r2_key` via a presigned URL — same mechanism as
  the existing `GET /api/v1/candidates/cv/{cv_id}/download` for self-registered
  CVs, just pointed at `r2_key` instead.
- Gating: for `admin_sourced` profiles, only populate/return this field once
  the relevant `IntroductionRequest` is `ACCEPTED`. For `own_sourced`
  profiles, no new gating — the employer already has this via the existing
  Talent Pipeline view; this is just making the same data reachable from the
  AI Match card too.

## Phase 4 — `request_introduction` branching (backend)

Branch on the profile's category (self_registered unchanged, already built):

- **`own_sourced`**: new lightweight path, *not* `IntroductionRequest` at
  all — no credit deduction, no token, no accept/decline state machine. Just
  sends the candidate a notification (reuses `EmailService`, new
  `send_role_notification`-style method) letting them know about this
  specific job. One-way, instant, free.
- **`admin_sourced`**: existing `IntroductionRequest` flow, but instead of
  emailing the candidate directly, email goes to the specific admin
  identified by `talent_pool_profile.added_by`. That admin does the manual
  outreach off-platform, then marks the request `ACCEPTED`/`DECLINED`
  themselves (new admin-facing action — see Phase 5). Credit still deducted
  from the employer at request time, still refunded on decline, same as today.

## Phase 5 — Admin ops queue (new, backend + frontend)

- Backend: an authenticated equivalent of the public `accept`/`decline`
  magic-link endpoints, but for admins acting on a candidate's behalf —
  reuses `IntroductionService.accept`/`decline` logic (already handles
  status transition + credit refund), just triggered by an admin action
  instead of a public token click. Scope the list to `GET
  /api/v1/admin/introductions?assigned_to=me` (join `IntroductionRequest` →
  `talent_pool_profile.added_by == current_admin.id`, no new column needed —
  derivable at query time).
- Frontend: new admin page, same list/filter shape as the employer's
  `IntroductionsPage.jsx`, plus Accept/Decline buttons per row.

## Phase 6 — Frontend: three-way CTA on `TalentMatchCard`

Branch on `match.ownership` (from Phase 2):

- `self_registered` → today's "Request Introduction" button, unchanged.
- `own_sourced` → new "Notify for this role" button — free, single click,
  no credit badge, no paywall modal, immediate success state (no
  pending/accept/decline lifecycle to track).
- `admin_sourced` → today's "Request Introduction" button, unchanged
  behavior from the employer's point of view (credit, pending badge) — the
  routing-to-a-specific-admin difference is invisible to the employer, it's
  purely a backend/ops concern.

## Verification

- Phase 1 alone: as two different employers, confirm Employer B's AI Match
  never returns a profile with `added_by == Employer A` and
  `candidate_profile_id IS NULL`. Confirm self-registered candidates with
  `cv_sharing_consent=True` still appear for both employers unchanged.
- Phase 4/5: create an admin-sourced profile, request introduction as an
  employer, confirm the notification lands with the correct admin (not the
  candidate directly), confirm credit is held pending, confirm admin
  accept/decline correctly unlocks/refunds.
- Phase 6: three different profiles in one AI Match list (one of each
  category) render three different, correct CTAs.
