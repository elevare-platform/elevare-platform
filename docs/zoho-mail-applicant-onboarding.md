# Zoho Mail → Elevare applicant onboarding

Status: **interim stopgap in effect as of 2026-08-05** — using Zoho Mail's
native Out of Office / auto-reply feature to nudge applicants to register,
instead of the webhook-driven reply below, for now. Reason: the ingestion
poll's OOM fix (see `fix/ingestion-oom-page-buffering`) hasn't been proven
against a real full historical import yet — `MailIntegration.sync_cursor`
isn't populated because that import hasn't completed. Building the
webhook reply on top of an unverified pipeline isn't worth it right now,
and available credit/budget is tight. **Known tradeoff accepted for the
interim**: the native auto-reply can't branch on whether the sender
already has an Elevare account, so it'll nudge existing users to
"register" too — acceptable short-term, not the end state.

**Revert condition — switch back to the plan below once**: (a) a real
historical import has completed against `careershub@elevare.com.ng`
without an OOM kill, confirming the fix actually holds under full load,
and (b) there's budget/credit to build Phases 0-2 properly.

Everything below this point describes the target design once those two
conditions are met — it's fully speculed out and ready to resume, not
abandoned.

---

Webhook config (Phase 0 of the original plan) was itself confirmed
working end-to-end 2026-08-05 — webhook created under the
`careershub@elevare.com.ng` account (not `hr@`), conditions are `To
contains careershub@elevare.com.ng` AND `Has attachment` AND `Attachment
Name ends with .pdf` (not "Attachment Type" — that field didn't match
plain `.pdf`). Real applicant email confirmed with valid
`x-hook-signature`. Design below revised 2026-08-05 after discovering the
existing `app/modules/ingestion/` module already does full CV
parsing/dedup/talent-pool creation via OAuth polling — the webhook's scope
shrank significantly as a result. Nothing past webhook config
implemented yet.

## Problem

Candidates email CVs directly to the company's Zoho Mail inbox instead of
applying through Elevare. HR wants those people automatically nudged to
register on the platform, upload formally, and apply to the job there —
without losing the CV they already sent, and without creating duplicate
work if the same person emails more than once.

## Revised architecture: webhook only handles the reply, not CV parsing

Original design (see git history) had the webhook fetch the CV attachment
and run it through the parsing pipeline itself. That's now known to be
redundant: `app/modules/ingestion/` already does this end-to-end for any
OAuth-connected mailbox — poll every 15 minutes, fetch, hash, dedupe,
`submit_cv_for_parsing`, create `TalentPoolProfiles`, queue the AI
pipeline. Building a second path that duplicates that would risk two
pipelines racing to process the same CV.

**So the webhook's only job is the reply** — branch on the sender's email
and send the right message, immediately, without waiting on parsing:

1. `create_invite` raises `AlreadyExistsException` → user already has an
   account → send a "log in" reply.
2. A pending, unused invite already exists for this email → `resend_invite`
   instead of minting a second live token. Needs one new lookup: pending
   invite by email (today's lookup is by token only).
3. Neither → `create_invite`, generic (not tied to a specific job) —
   "register and browse our openings."

This branch only needs `fromAddress` and two DB lookups — nothing about
the CV, nothing that waits on the 15-minute poll. That's why it's safe to
fire the reply instantly.

**Prerequisite this whole design depends on**: `careershub@elevare.com.ng`
must actually be connected as a `MailIntegration` (OAuth) so the existing
ingestion poll picks it up. Confirm this before anything else — the reply
can work perfectly and nothing downstream will happen if this isn't true.

## Why the invite no longer carries `talent_pool_profile_id`

Original design had the invite link carry the specific `TalentPoolProfiles`
row to link, generated at send time. That doesn't work now: the webhook
fires in seconds, but the poll that creates the profile row can take up to
15 minutes — the row often won't exist yet when the reply goes out.

Resolution: **link later, at registration/upload time, not at send time.**
By the time a candidate actually finishes registering, the poll has
virtually always already run. Two entry points need to do this linking,
found while reviewing where it could go wrong:

- **Invite acceptance** (candidate clicks our email link) — link by
  matching the sourced profile's email to the invite's email.
- **Self-upload, independent of our invite** (candidate registers on their
  own, unprompted, and separately uploads a CV that happens to match one
  already sourced via email) — this path currently does no linking at all
  (verified: `create_candidate_from_submission` in `cv_parsing_service.py`
  only touches `User`/`CandidateProfile`, never queries
  `TalentPoolProfiles`). Link here by **CV hash match** instead of email —
  more precise, since it's tied to actual content, not a string.

Both need a way to find the right `TalentPoolProfiles` row:
- Email match needs a real queryable column — verified `TalentPoolProfiles`
  has no such column today; the sourced email only exists buried in the
  free-text `source_note`. Needs a new `sender_email` column.
- Hash match needs `ParsedCVSubmission.cv_text_hash` (already exists,
  already indexed — `ix_parsed_cv_submissions_cv_text_hash`) compared
  against `TalentPoolProfiles.parsed_submission_id`'s target row.

On ambiguity (more than one unlinked profile matches): link the most
recently created one. Not perfectly rigorous, but a rare enough edge case
not to engineer around right now.

## Bug found while verifying the hash-match plan

`cv_parsing_service.py`'s `_compute_hash` (self-upload path) hashes
`text_result.text or ""` with no fallback — a failed text extraction
hashes an empty string, for every user, every time, meaning every
self-uploaded CV that fails extraction collides with every other one.
`ingestion/tasks.py`'s `_compute_cv_hash` (email path) falls back to
hashing the raw attachment bytes when extracted text is empty — different
behavior for the same kind of input. Confirmed via direct code read, not
assumed. Must be fixed for hash-matching to be trustworthy across both
entry points — otherwise the CVs most likely to have extraction trouble
are exactly the ones that won't match correctly.

## Other things decided along the way

- **Idempotency**: Zoho can redeliver the same webhook event. Must track
  processed `messageId`s and skip duplicates, or a retried delivery sends
  a second invite email to the same person.
- **Secret storage**: the one-time `x-hook-secret` (delivered only on the
  very first request, never again) needs to be captured and stored
  encrypted at rest — follow the existing `MailIntegration` pattern
  (Fernet-encrypted column, keyed by `settings.fernet_key`), not a generic
  new abstraction. Every subsequent event carries `x-hook-signature`
  instead — verify with `hmac.compare_digest` over the raw request body,
  reject (401/403) and log on mismatch, don't process the payload.
- Skipped: using Zoho's native out-of-office/auto-reply feature instead of
  building this. Rejected because it can't branch on account existence —
  it would send "please register" to someone who already has an account,
  which is the exact bad experience being avoided here.
- Onboarding pre-fills from parsed data, editable before submit: bio ←
  parsed `summary`, skills ← parsed `skills`. Safe in a way the earlier
  "show raw scraped CV data" discussion wasn't — the candidate is
  reviewing their *own* data before it goes live.

## What's still genuinely unresolved

- **Exactly where `CandidateProfile` gets created for a newly-registered
  candidate.** Traced `accept_invite` in `auth/service.py` — it creates a
  `User` row only, nothing candidate-profile-specific. **Finding this
  exact call site is the first concrete step of Phase 3** — don't guess,
  trace it for real before writing the linking logic.

## Phases

**v1 scope is Phases 0-2 only.** Phase 3+ (linking a later self-service
account back to the sourced profile) is deferred, not required to ship —
reasoning: even with zero linking, the CV is already in the talent pool
via the existing ingestion poll, searchable/scoreable by employers exactly
as it would be otherwise. Linking only helps if/when someone actually
clicks through and registers; it doesn't gate the core value. Revisit only
if real usage shows it's actually needed.

**Phase 0 — Confirm the dependency.** Verify (or set up)
`careershub@elevare.com.ng` as a connected `MailIntegration`. Nothing else
matters if this isn't true.

**Phase 1 — Schema.**
- Lookup method: pending invite by email.
- New table for the Zoho webhook secret, encrypted (Fernet), following
  `MailIntegration`'s pattern.
- New table/mechanism to track processed webhook `messageId`s for
  idempotency.

**Phase 2 — Webhook receiver.** New endpoint. Handles the one-time secret
handshake, verifies `x-hook-signature` on every real event, skips already-
processed `messageId`s, branches on sender email (login link / resend /
new invite) using Phase 1's lookups.

---

**Deferred — Phase 3+, only if usage justifies it later.**
- `sender_email` column on `TalentPoolProfiles`.
- Trace the real `CandidateProfile` creation call site (open item above).
- Link at invite acceptance, by email match.
- Link at self-upload, by CV hash match — new code, this path currently
  does no linking at all.
- Fix the hash-fallback inconsistency between `cv_parsing_service.py` and
  `ingestion/tasks.py` first, so hash matching is trustworthy.
- Onboarding pre-fill (bio/skills from parsed CV data).
- Email content + polish for the three reply variants.
