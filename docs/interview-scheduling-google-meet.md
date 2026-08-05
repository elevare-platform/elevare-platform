# Interview scheduling — consent-gated Google Meet

Status: designed, deferred. Design agreed 2026-08-02; build order changed
2026-08-03 — Flowmingo (async AI interviews) is being built first to cover
an urgent real interviewing need, this comes after. See
`docs/flowmingo-ai-interview-integration.md` for the mechanism this defers
to. The `InterviewScheduleRequest` model below is shared between both —
build it with the Meet-specific fields present but unused until this phase
starts.

## Problem

Employers can add candidates to a per-job `InterviewListEntry` (see
`backend/app/modules/interview_list/models.py`), but there's currently no way
to actually *conduct* that interview from inside the platform — an employer
has to coordinate a call entirely outside Elevare.

Two things make "just add a Schedule button" harder than it looks:

1. **`InterviewListEntry.job_id` is `NOT NULL`.** Candidate Search (the
   job-less "search my whole talent pool" flow) has no job in context, so
   there's no obvious `job_id` to attach a scheduling action to when a
   candidate is found that way.
2. **Consent.** A large share of talent pool profiles are sourced-only —
   an admin or employer uploaded a CV, there's no account, no login, and the
   only contact channel is an email address pulled out of the parsed CV by
   an LLM. Scheduling a live video call between an employer and that email
   address, with no confirmation the person even wants to be contacted this
   way, is not something to automate blindly.

## Decisions

- **Two-party call**: employer and candidate. Elevare is the plumbing
  (holds the Calendar API credentials, sends the consent link, creates the
  event once accepted) — **not** a permanent third participant. An Elevare
  staffer sitting in on every scheduled interview doesn't scale (it's a
  headcount cost that grows linearly with platform usage) and doesn't
  actually address the real concern, which is consent, not supervision.
- **No calendar event is ever created before the candidate explicitly
  accepts.** Reuses the exact pattern `IntroductionRequest` already uses for
  this same population: a one-time emailed link, accept or decline, no
  login required. Do not invent a new consent mechanism — this one already
  exists and is already trusted.
- **Candidate Search's missing `job_id` is solved by reusing
  `JobService.get_or_create_general_interest_job`** (already exists,
  `backend/app/modules/jobs/service.py`) — the same placeholder-job trick
  already used for `request_introduction` from Candidate Search. No schema
  change needed for this half of the problem.
- **Google Meet generation is automated**, via the Google Calendar API's
  `conferenceData` feature on event creation — not a manually pasted link.
- **This will eventually be subscription-gated.** Not built in this phase —
  no entitlement system exists yet — but the design should leave an obvious
  seam for a plan/entitlement check before "Schedule Interview" is callable,
  rather than needing rework later.
- **Interview mechanism (Meet vs. the future Flowmingo async AI interview)
  is a free choice per entry**, not locked to where the entry came from. An
  employer might want a quick AI screen on someone found via Candidate
  Search, or a live call with a standout AI Talent Match candidate — locking
  it by origin would block both for no real benefit.
- **The candidate is offered a few proposed times, not just one**, and
  picks one when accepting. Costs more than a single-time flow (a list to
  store, a picker in the accept UI instead of one button) but a materially
  better candidate experience.
- **Elevare keeps its own calendar record of every scheduled interview.**
  This settles the auth-model question below in the same move: the natural
  way to get "Elevare's own record of every interview" is for **every event
  to be created on one Elevare-owned Google account**, with the employer
  and candidate invited as guests — not each employer connecting their own
  Google Calendar. That single Elevare-owned calendar *is* the audit
  record; there's no separate bookkeeping needed to satisfy this
  requirement.

## Calendar auth — decided 2026-08-02

**Plain OAuth 2.0 against one dedicated Google account** (e.g.
`elevareinterviews@gmail.com`), not a service account.

Service accounts were ruled out entirely, not just deprioritized: a service
account can create Calendar events, but cannot invite attendees on them at
all without domain-wide delegation, and DWD can only be configured through a
Google Workspace Admin console — which Elevare doesn't have. Since inviting
the employer and candidate as attendees is the entire point of this
feature, a service account can't do it.

Setup:
1. Google Cloud project, Calendar API enabled.
2. OAuth consent screen configured with the calendar scope needed to create
   events with attendees, **test users added** (the dedicated account,
   plus whoever else needs to run the one-time auth during development).
3. Run the one-time OAuth authorization as the dedicated account, capture
   the refresh token, store it server-side the same way other API keys in
   this repo are stored.
4. Build and test against this — refresh tokens issued while the app is in
   **Testing** publishing status expire every 7 days, which is fine for
   development (re-authorize by hand as needed).
5. **Before this feature is relied on by real users**, flip the OAuth
   consent screen to **"In production"** status (requires Google's app
   verification process for this sensitive scope — start that review early,
   it can take real calendar time). Same account, same stored refresh
   token infrastructure — this is a status flip, not a migration. Skipping
   this step means the integration silently breaks ~7 days after whoever
   last authorized it did so, with no error, which is the specific trap to
   avoid.

## Data model (conceptual — no code yet)

New table, `interview_schedule_requests`, deliberately separate from
`InterviewListEntry` rather than bolted onto it — scheduling is its own
lifecycle (`PENDING → ACCEPTED/DECLINED/EXPIRED → COMPLETED`) layered on top
of "this candidate is queued for this job," the same relationship
`IntroductionRequest` has to `TalentPoolProfiles`.

```
InterviewScheduleRequest
  id
  interview_list_entry_id   FK -> interview_list_entries
  employer_id               FK -> users
  talent_pool_profile_id    FK -> talent_pool_profiles
  job_id                    FK -> jobs   (real job, or the General Interest
                                          placeholder for Candidate Search)
  mechanism                 enum: MEET | FLOWMINGO   (employer's free choice per entry)
  proposed_times            JSONB, list of datetimes the employer offered
  selected_time              nullable — the one the candidate picked, set on accept
  status                    enum: PENDING | ACCEPTED | DECLINED | EXPIRED | COMPLETED
  token                     unique, single-use — mirrors JobAccessTokens/
                             IntroductionRequest.token exactly
  meet_link                 nullable — set only once ACCEPTED
  calendar_event_id         nullable — id of the event on Elevare's own
                             calendar (see Decisions) — needed to update/
                             cancel later
  responded_at              nullable
  expires_at
  created_at
```

## Flow

1. Employer picks an `InterviewListEntry`, chooses a mechanism (Meet or
   Flowmingo, employer's free choice), proposes a few candidate times.
2. Elevare emails the candidate's on-file address (parsed CV email for
   sourced profiles, account email for self-registered) a one-time link —
   same shape as `IntroductionRequest`'s accept/decline email.
3. Candidate opens the link (no login) → picks one of the proposed times to
   accept, or declines. No calendar event exists yet at this point.
4. On accept: backend calls the Google Calendar API to create an event with
   `conferenceData` (auto-generates the Meet link), invites employer +
   candidate as guests, stores `meet_link` and `calendar_event_id`, emails
   both sides the confirmed details.
5. On decline / no response within N days: request marked `DECLINED` /
   `EXPIRED`, employer notified, entry stays on the Interview List — same
   "no penalty, no dead end" shape `IntroductionRequest` already has for
   declines.

## Explicitly out of scope for this round

- **Flowmingo integration itself** — sequenced after this ships fully,
  not in parallel (two new external integrations — Calendar OAuth/API and
  Flowmingo's API-key/webhook model — at once is a lot of new surface area
  to get right simultaneously; see the Flowmingo discussion in this
  session's notes for the async-interview design).
- **Real subscription/entitlement gating** — no plan/billing system exists
  yet. Leave the seam, don't build the check.
- **Rescheduling / cancellation UI** — first version is accept-or-decline
  only; changing an already-accepted time is a fast-follow, not MVP.

## Prerequisite research (see chat for the phased task breakdown and
resource pointers — not duplicated here since this doc is the design
record, not the build plan)
