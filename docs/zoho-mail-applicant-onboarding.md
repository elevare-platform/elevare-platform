# Zoho Mail → Elevare applicant onboarding

Status: proposed, not implemented. Design agreed 2026-08-03.

## Problem

Candidates email CVs directly to the company's Zoho Mail inbox instead of
applying through Elevare. HR wants those people automatically nudged to
register on the platform, upload formally, and apply to the job there —
without losing the CV they already sent, and without creating duplicate
work if the same person emails more than once.

## Decisions

- **Ingestion trigger**: a Zoho Mail outgoing webhook (`Settings →
  Integrations → Developer Space → Outgoing Webhooks`), condition-matched
  on the target inbox, POSTs to a new Elevare endpoint on each matching
  incoming email. The webhook payload is metadata only (`fromAddress`,
  `subject`, message summary/HTML, message ID) — **no attachment** — so
  fetching the actual CV requires a follow-up call to the Zoho Mail REST
  API using that message ID. Needs its own Zoho Mail API credential/OAuth,
  separate from the webhook itself.
- **CV ingestion reuses the existing pipeline exactly** —
  `CVParsingService.submit_cv_for_parsing` (HMAC-hash + Redis cache, skips
  re-running the LLM parse on content it's already seen) followed by
  `TalentPoolRepository.get_by_cv_hash(hash, sourced_for_job_id)` (skips
  creating a duplicate `TalentPoolProfiles` row for the same content+job
  combo — confirmed this also works correctly with `sourced_for_job_id =
  None`). **Do not write a parallel ingestion path** — call the same entry
  points `talent_pool.submit()` already uses, or this dedup is lost.
- **Reply is generic** (not tied to a specific job) — "register and browse
  our openings," not "apply to job X." Simpler, and confirmed the dedup
  above works correctly either way, so nothing is lost by not parsing the
  subject line for a job reference.
- **The invite link doesn't just point at /register — it carries which
  `TalentPoolProfiles` row to link.** Needs a new `talent_pool_profile_id`
  field on the invite record (nullable — ordinary employer/candidate
  invites don't set it). Reasoning: `TalentPoolProfiles.candidate_profile_id`
  is `unique=True` — one candidate can only ever be linked to *one* sourced
  profile, ever — so if the same person was sourced more than once (two
  different emails, two different jobs), an "auto-link by matching email at
  registration time" approach would have no correct way to choose between
  them. Carrying the specific row on the invite token avoids that ambiguity
  entirely.
- **Three-way branch on incoming email**, not a simple exists/doesn't:
  1. `create_invite` raises `AlreadyExistsException` (already checks this)
     → user already has an account → send a "log in" reply, plain link to
     the existing login page. No new passwordless-login mechanism needed —
     they already have a password.
  2. A pending, unused invite already exists for this email → call
     `resend_invite` (already exists) instead of minting a second live
     token. Needs one new lookup: pending invite by email (today's lookup
     is by token only).
  3. Neither → `create_invite`, extended to accept `talent_pool_profile_id`.
- **Onboarding pre-fills from parsed data, editable before submit**: bio ←
  parsed `summary`, skills ← parsed `skills`. This is safe in a way the
  earlier "show raw scraped CV data" discussion wasn't — it's the
  candidate reviewing their *own* data before it goes live, not exposed to
  a third party, so none of that discussion's visibility/consent concerns
  apply here.
- **Linking happens once `CandidateProfile` is created** during invite
  acceptance: if the invite has `talent_pool_profile_id` set, that
  `TalentPoolProfiles` row's `candidate_profile_id` gets set to the new
  profile's id.

## What's still genuinely unresolved

- **Exactly where `CandidateProfile` gets created for a newly-registered
  candidate.** Traced `accept_invite` in `auth/service.py` — it creates a
  `User` row only, nothing candidate-profile-specific. The actual
  `CandidateProfile` creation happens somewhere else in the onboarding
  path. **Finding this exact call site is the first concrete step of
  Phase 3** — don't guess at it, trace it for real before writing the
  linking logic.
- **Zoho Mail API credentials for attachment fetching** — separate from
  whatever's used for the webhook itself. Needs its own setup step,
  similar in spirit to the Flowmingo API key work.

## Flow, end to end

1. Candidate emails a CV to the monitored inbox.
2. Zoho outgoing webhook → new Elevare endpoint, with email metadata.
3. Endpoint fetches the attachment via Zoho Mail API (message ID from the
   webhook payload) and runs it through `submit_cv_for_parsing` →
   `get_by_cv_hash` — creates or reuses a `TalentPoolProfiles` row,
   `source="email"`, `candidate_profile_id=None`.
4. Three-way branch on the sender's email (exists / pending invite /
   neither) as above, resulting in either a "log in" reply, a resent
   invite, or a fresh invite carrying `talent_pool_profile_id`.
5. Candidate clicks the link, lands on registration, sees bio/skills
   pre-filled from their parsed CV (editable), sets a password, submits.
6. `CandidateProfile` is created (existing path — see open item above);
   the linking step sets `TalentPoolProfiles.candidate_profile_id` for the
   row referenced by the invite.
