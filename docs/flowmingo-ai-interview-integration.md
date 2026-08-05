# Flowmingo async AI interviews

Status: proposed, not implemented. Prioritized 2026-08-03 ahead of
`docs/interview-scheduling-google-meet.md` to cover an urgent real
interviewing need. Shares one data model with that doc — read its "Data
model" section first, this doc only covers what's different for Flowmingo.

## What Flowmingo actually is (confirmed, not assumed)

Flowmingo is an **async** AI interviewer — the candidate completes the
interview on their own time via a link, not a live booked call. That's a
materially different shape from the Google Meet mechanism, not just a
different vendor for the same thing:

- No time-proposal/picker needed — `proposed_times`/`selected_time` on
  `InterviewScheduleRequest` are Meet-specific and stay unused on
  `FLOWMINGO` rows.
- Flowmingo's own candidate-facing invite (their email, their link) is
  itself the moment a candidate can simply not participate — there's no
  live event to accept or decline ahead of time the way there is for a
  Meet call. So **the Elevare-side accept/decline consent-link step from
  the Google Meet design does not apply here** — don't build it for this
  mechanism, it'd be a redundant gate in front of a gate.

## The consent question that's still real for this mechanism, and different from Meet's

Google Meet's consent gate existed because you're booking a live call with
someone who may not have agreed to be contacted that way. Flowmingo's
concern is different: **triggering a Flowmingo invite means sending that
candidate's personal data (name, email, and however much of their parsed
CV Flowmingo's invite API requires) to a third-party vendor**, before
they've done anything to indicate they want to be considered further by
this employer beyond having their CV sit in your talent pool.

That's a real question to decide deliberately, not skip because it's
inconvenient right now. The line that matters is **not** "self-registered
on Elevare vs. sourced" — channel doesn't establish intent; someone who
emailed their CV for a specific posting, or applied via Indeed and was
brought into the pool by the employer, has exactly the same intent-to-be-
considered as someone who clicked "Apply" on the platform. The line that
actually matters is **whether this CV was brought in against a specific
role at all**:

- **Tied to a specific job** — `TalentPoolProfiles.sourced_for_job_id IS
  NOT NULL` (covers CVs entered against a posting regardless of
  channel — email, Indeed, the platform's own apply flow), or a
  self-registered candidate with a real `Application` row. Sending this
  person's data onward to run an interview for the role they expressed
  interest in is a reasonable, expected extension of "you applied, we're
  evaluating you" — normal hiring-process tooling, not a surprise use of
  their data. (Worth being precise with yourself about one thing: the data
  reaches Flowmingo *before* Flowmingo's own invite email gives the
  candidate any notice a third party is involved — for an actual applicant
  to a named role that's within normal expectations, but it's not
  *advance* consent, it's normal-process handling. Know the difference if
  it's ever asked about.)
- **Not tied to any role** — `sourced_for_job_id IS NULL`, pure speculative
  sourcing with no applicant intent behind it at all. Defer this
  population until there's a real consent step for this specific action,
  same spirit as `IntroductionRequest`'s ask-first pattern, just not built
  yet for this mechanism.

This scoping is a query filter on existing data, not a new field or a new
flow — implement it as the eligibility check in Phase 1/2, not as
something requiring more design work.

## Flow

1. Employer, from an `InterviewListEntry` (or directly from the applicant
   pipeline — worth deciding which entry points you need for the urgent
   cases first), chooses `mechanism = FLOWMINGO`.
2. Backend creates an `InterviewScheduleRequest` row, `status = PENDING`,
   and queues a Celery task (same pattern as `score_talent_pool_profile_task`
   — outbound third-party API calls don't belong in the request/response
   cycle).
3. Task calls Flowmingo's invite endpoint with candidate email + job
   context + a reference id (your `InterviewScheduleRequest.id`) so their
   webhook can tell you which row it's about. Row moves to `INVITED`.
4. Flowmingo emails the candidate; they complete the interview whenever.
5. Flowmingo posts webhook events to `POST /webhooks/flowmingo` — progress
   updates and, eventually, the evaluation result. Verify the HMAC
   signature on every call (mandatory, not optional — this endpoint has no
   other auth). Update `status` (`IN_PROGRESS` → `COMPLETED`) and store the
   evaluation.
6. Frontend shows status + evaluation on the Interview List row, same
   visual treatment `ai_fit_summary` already gets elsewhere in this app.

## What's genuinely unknown until you have API access

Everything found on Flowmingo's public site is marketing-level — API key
auth, HMAC-signed webhooks, "trigger invites from your ATS" — not actual
endpoint paths, request/response field names, or the webhook payload
shape. **The real first step is getting a Flowmingo account and API
credentials and reading their actual developer docs** — nothing past that
point can be built correctly on guesses about field names.

## Phases

**Phase 0 — unblock on real docs.** Get Flowmingo API access. Read their
actual invite-endpoint and webhook docs. Confirm: does their invite payload
accept a client reference id (needed for step 3 above)? What does their
webhook payload actually contain? How exactly is the HMAC signature
computed (which header, which secret, which body encoding)? Don't guess
any of this from the marketing page.

**Phase 1 — data model.** Add `InterviewScheduleRequest` (shared with the
Meet doc) via migration. For this phase, only `mechanism = FLOWMINGO` needs
to actually work — Meet-specific fields can exist in the schema and stay
unused.

**Phase 2 — outbound invite.** The Celery task that calls Flowmingo's
invite API. Model it on `score_talent_pool_profile_task` for the
fresh-engine/`NullPool` pattern already fixed this session — don't
reintroduce the connection-exhaustion problem in a new task.

**Phase 3 — webhook receiver.** New endpoint, HMAC verification, status +
evaluation updates. This is the first webhook handler in this codebase —
no existing pattern to copy, budget real time for getting signature
verification right and for handling out-of-order/duplicate webhook
deliveries (idempotency — a webhook you've already processed shouldn't
double-apply).

**Phase 4 — frontend.** "Send AI Interview" action + status/evaluation
display on the Interview List row.

## Resources worth reading before you start

- Flowmingo's actual developer docs, once you have account access — not
  the public marketing page, which is what's linked below and is not
  sufficient to build against.
- `backend/app/modules/ai/tasks.py::score_talent_pool_profile_task` — your
  template for an outbound-API Celery task with the connection-handling
  fix already applied.
- `backend/app/modules/introductions/` — for the ask-first consent pattern,
  relevant if you decide to extend this to admin-sourced profiles later.
- General reference on verifying HMAC webhook signatures correctly (timing-
  safe comparison, raw body vs parsed body) — this is a common source of
  subtle security bugs; worth reading a solid guide before Phase 3, not
  improvising it.
