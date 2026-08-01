# Admin job intake on behalf of a real employer

Status: proposed, not implemented.

## Problem

Admins can post jobs directly (`JobService.create_job` bypasses the profile-completeness/KYC
gate and the moderation queue for admin posters — see `backend/app/modules/jobs/service.py`).
Those jobs have no `employer_profile` behind them, so `JobResponse.from_job` had nothing to
source `company_name` from and fell back to `None`, which the frontend rendered as
"Unknown company" (see `backend/app/modules/jobs/schemas.py`, `PLATFORM_COMPANY_NAME`).

That's now fixed at the display layer: an admin-posted job with no backing profile shows a
fixed platform name, "Elevare Human Solutions Ltd". That's the right default for jobs the
platform itself posts, but it's the wrong label for the case this doc is about: an admin
acting as intake for a real employer who called or emailed in a vacancy instead of
registering and posting it themselves. Those jobs should show the real company's name, not
the platform's.

## Goal

Let an admin post a job "on behalf of" a specific real company, chosen at post time, without
requiring that company to have (or ever create) its own Elevare account.

## Chosen approach

Add a nullable `posted_on_behalf_of_employer_id` column on `Job`, pointing at an
`employer_profile`-bearing `User`. `job.employer_id` keeps meaning what it already means
everywhere else in the codebase: *who is accountable for this listing on the platform* — the
admin who did the data entry. The new column is purely a display/attribution override,
resolved by `JobResponse.from_job` in preference to the poster's own profile.

This was picked over the alternative (pointing `job.employer_id` itself at the real company)
because `employer_id` is load-bearing everywhere: `_check_ownership`, `close_job`,
`update_job`, `publish_job`, `delete_job`, `get_job_matches`, and the on-demand
`score_profile_against_job` endpoint all gate on "does the caller's user id match
`job.employer_id`, or are they admin." Repointing `employer_id` at a company that has no
logged-in user acting on its behalf would either break every one of those checks or require
threading a second identity concept through all of them. A separate display field avoids
that entirely — zero changes to any permission check already in this codebase.

## Data model

```
Job.posted_on_behalf_of_employer_id: UUID | None, FK -> users.id, nullable, ON DELETE SET NULL
```

`ON DELETE SET NULL`, not CASCADE — if the target employer account is later deleted, the job
shouldn't disappear, it should fall back to the existing `PLATFORM_COMPANY_NAME` default.

No new table needed if the target is always an existing `employer_profile`-bearing user. If
admins need to attribute a job to a company that has genuinely never touched the platform
(true cold intake, no account at all), that needs a lightweight `company_name`/`company_logo`
pair stored directly on the column set instead of a FK — see "Open questions" below for why
that's deliberately deferred rather than decided here.

## Display resolution (`JobResponse.from_job`)

Current order after this change:

1. `job.posted_on_behalf_of_employer_id` resolved → that user's `employer_profile` fields, if set.
2. Else the poster's own `employer_profile` (existing real-employer path, unchanged).
3. Else, if poster is admin, `PLATFORM_COMPANY_NAME` (the fallback just shipped).
4. Else `None` (existing behavior for a real employer with a somehow-incomplete profile).

## API / request surface

- `JobCreateRequest` gets an optional `posted_on_behalf_of_employer_id: UUID | None`.
- `JobService.create_job` accepts it only when `is_admin` — a non-admin employer posting on
  behalf of someone else is out of scope and should be rejected, not silently ignored.
- Needs a lookup endpoint for the admin UI's company picker: search existing
  `employer_profile` rows by company name. Reuse `AdminRepository`'s existing employer listing
  rather than adding a new one if it already supports a search param.

## Frontend

- `PostJobPage.jsx`: admin-only "Posting on behalf of a company" picker — search/select an
  existing employer account. Skipping the picker keeps today's platform-name behavior, so
  this is additive, not a breaking change to the existing admin post flow.
- No changes needed to `JobCard.jsx` or `TalentMatchCard.jsx` — they already just render
  whatever `company_name` the API returns.

## Explicitly out of scope for this change

- **Notifying the real employer.** Whether that employer should get an email/dashboard entry
  when an admin posts "for" them is a product decision, not implied by the data model above.
- **KYC/moderation on the target company.** An admin vouching for a company by selecting them
  doesn't imply that company passed KYC — moderation status still tracks `job.employer_id`
  (the admin), unchanged.
- **Letting the real employer manage the listing themselves afterward.** If that's wanted
  later, it's a bigger change — transferring `employer_id` itself, with its own audit-trail
  question (does the transfer show up in job history?) — not something this doc's
  display-only field enables on its own.

## Open questions before implementation starts

1. Does intake ever need to cover a company with **no** Elevare account at all, or is the
   admin always selecting from existing registered employers? This decides whether the FK
   design above is sufficient or a lightweight non-account company record is also needed.
2. Should `posted_on_behalf_of_employer_id` be settable/changeable after the job is posted
   (e.g. via `update_job`), or fixed at creation? Fixed-at-creation is simpler and matches how
   `employer_id` itself already works (never reassigned post-creation anywhere in this
   codebase).
3. Related but separate: if "Elevare Human Solutions Ltd" (the current fixed fallback) is also
   the name a real employer account has registered under, admin-posted jobs using the fallback
   and that employer's real postings will look identical to candidates with no way to tell them
   apart. Worth resolving — either rename one, or route platform-originated jobs through that
   real account via this same mechanism — independently of whether intake-for-arbitrary-
   companies gets built.
