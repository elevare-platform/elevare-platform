# AI Talent Match — Monetization & Introduction Workflow

Status: MVP scoped, not yet built. Product direction agreed 2026-07-16.
Owner: Elevare Dev.

## 1. Goal

Turn the AI Talent Match tab from a passive candidate list into a monetized
action, without giving employers direct contact access to candidates. Elevare
stays the intermediary for every introduction.

## 2. Candidate populations (this is the key architectural fork)

Two different kinds of profiles exist in `talent_pool_profiles`, and they
need different consent handling:

| | Self-registered candidate | Sourced-only CV |
|---|---|---|
| Has `CandidateProfile` row | Yes | No |
| Has a login / account | Yes | No |
| Set their own `cv_sharing_consent` | Yes, explicitly | N/A — never asked |
| Appears in AI Talent Match tab today | Yes (`cv_sharing_consent=True` required) | Yes (outer join — sourced profiles pass through unconditionally) |
| Appears in existing Talent Pipeline tab | Yes | Yes (no consent gate there) |
| Contact channel we can use | In-app + email | Email only (parsed from CV) |

Decision (2026-07-16): **both populations get monetized introduction actions**,
but through different mechanics — self-registered candidates get an
in-app accept/decline flow eventually; sourced CVs get an automated email
sent to the address already captured in `ParsedCVSubmission.parsed_data`.

**MVP simplification — recommended, confirm before building:** build ONE
mechanic first — email + one-time magic link (same pattern as
`JobAccessTokens`) — for both populations. It works whether or not the
person has an account. Defer the "real" in-app candidate inbox (logged-in
accept/decline UI) to Future, once employer willingness-to-pay is proven.
This avoids building new candidate-facing UI before you know anyone will pay
for the employer side. If you'd rather build the two mechanics in parallel
now, say so and this doc will split into two MVP tracks instead of one.

## 3. MVP scope

### 3.1 Billing — no gateway yet
No Stripe/Paystack/subscription code exists in the repo today. MVP does NOT
integrate a payment gateway. Instead:
- A `employer_credits` balance (per employer `User`, or per `EmployerProfile`
  if you want it company-wide later) + a `credit_transactions` ledger table
  (amount, reason, reference id, created_at).
- Credits are **granted manually by an admin** (admin panel action, reuses
  the existing admin module pattern) — no self-serve checkout.
- This validates "will employers spend credits" before any payment
  integration work happens.

### 3.2 Actions
- **Shortlist** — free. A flag/status on the talent pool profile from the
  employer's point of view (no credit cost, no candidate-facing effect).
- **Request Introduction** — 1 credit. Creates an `IntroductionRequest`
  record, deducts a credit, sends a one-time email with a magic link to the
  candidate's email (from `CandidateProfile`/`User` for self-registered, or
  from `ParsedCVSubmission.parsed_data.email` for sourced CVs).
  - Candidate clicks the link → accept or decline, no login required.
  - Accept → employer is notified and contact info / CV unlocked.
  - Decline → credit refunded, employer notified with no identity reveal.
  - No response within N days → request expires, credit refunded.
- **Unlock Full Profile** — 1 credit, self-registered candidates only
  (sourced CVs have no extra "profile" beyond the CV itself, so this action
  doesn't apply to them). Reveals full CV/skills/education without any
  contact exchange — pure information unlock, no candidate action required
  (their `cv_sharing_consent = True` already covers this case, per the
  Phase 1 query).

### 3.3 Data model additions (conceptual — no code yet)
- `employer_credits` — employer_id, balance
- `credit_transactions` — employer_id, delta, reason (`grant`, `intro_request`,
  `intro_refund`, `unlock_profile`), reference_id, created_at
- `introduction_requests` — employer_id, job_id, talent_pool_profile_id,
  status (`PENDING`, `ACCEPTED`, `DECLINED`, `EXPIRED`), token (unique,
  single-use, mirrors `JobAccessTokens.token` pattern), expires_at,
  responded_at

### 3.4 Reused patterns (don't reinvent)
- Magic-link token: same shape as `JobAccessTokens` (token, expires_at,
  is_active, revoked_at).
- Email sending: same `get_email_service()` / `settings.email_stub_mode`
  pattern already used in `talent_pool/service.py` (`promote`,
  `update_status` shortlist notification).
- Admin credit grant: same module structure as `admin/service.py`.

## 4. Flows

**Self-registered candidate (MVP — email mechanic):**
```
Employer clicks "Request Introduction" on a matched card
  → credit check → deduct 1 credit
  → IntroductionRequest created, status=PENDING
  → email sent to candidate (existing User.email) with magic link
  → candidate clicks link, no login needed → Accept / Decline
  → Accept: employer notified, CandidateProfile contact info revealed
  → Decline: credit refunded, employer notified (no identity shown)
  → No response after N days: auto-expire, credit refunded
```

**Sourced-only CV (MVP):**
```
Same as above, but:
  → candidate email comes from ParsedCVSubmission.parsed_data.email
  → no CandidateProfile exists, so "accept" just flips
    TalentPoolProfiles.status and reveals the parsed CV to the employer
  → this is effectively a lightweight version of the existing promote()
    flow, minus creating a full user account
```

**Unlock Full Profile (self-registered only):**
```
Employer clicks "Unlock Full Profile"
  → credit check → deduct 1 credit
  → full CandidateProfile detail returned immediately (no candidate
    action needed — cv_sharing_consent=True already covers this)
```

## 5. Future roadmap (post willingness-to-pay validation)
- Real payment gateway (Stripe/Paystack) + self-serve credit purchase
- Subscription tiers with bundled monthly credits (anchor to existing
  `PricingPage.jsx` Starter/Professional/Enterprise tiers)
- In-app candidate inbox for self-registered candidates (logged-in
  accept/decline, replaces the email-only mechanic for that population)
- AI Recruiter suite at `/talent-pipeline`: JD writer, auto-screening,
  interview question generator, salary benchmarking, sourcing digest
- Success-fee tracking on confirmed hires (Enterprise tier)

## 6. Open risks / questions
- Manual admin credit grants won't scale past a handful of pilot employers
  — fine for MVP, becomes a bottleneck fast, flag before wider rollout.
- Sourced-CV candidates never agreed to being contacted at all (only the
  employer/admin who uploaded them did). The email-consent-first flow
  in this doc is the mitigation — do not skip the accept step for this
  population even though it adds friction.
- Credit refund logic (decline / expiry) needs to be atomic with the
  ledger — a naive implementation could double-refund or leak credits.
