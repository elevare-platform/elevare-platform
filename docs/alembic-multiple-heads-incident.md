# Incident: Alembic "Can't locate revision" (multiple heads)

## Problem

Two branches each added a migration on top of the same parent revision
(`a90a457e7f79`) without either knowing about the other:

- `develop` (KYC feature) → `e3f1a2b4c5d6`
- `feature/monetization-ingestion` (this branch) → `b4e7f1a2c9d3`

Both migrations correctly said "I come right after `a90a457e7f79`" — because
that was genuinely the newest file each branch had *at the time it was
created*. Alembic can only chain onto what's in the `alembic/versions/`
folder at that moment; it has no way to know about a sibling migration
written on a different branch.

## Error

The shared Docker database had been upgraded via the `develop` chain at some
point, landing on `e3f1a2b4c5d6`. Switching to
`feature/monetization-ingestion` — whose files never included that
migration — broke `alembic current`:

```
ERROR [alembic.util.messaging] Can't locate revision identified by 'e3f1a2b4c5d6'
```

## What should have been done

Before creating the new migration on this branch, sync with the target
branch first:

```
git fetch origin
git log HEAD..origin/develop -- backend/alembic/versions/
```

This lists any migration files that exist on `develop` but not locally. Pull
those in *before* running `alembic revision --autogenerate`, so the new
migration chains onto the true latest head instead of a stale one:

```
a90a457e7f79 → e3f1a2b4c5d6 → b4e7f1a2c9d3   (one straight line, no fork)
```

## Fix applied

1. Pulled the missing file onto this branch (file only, not the whole branch):
   ```
   git fetch origin
   git checkout origin/develop -- backend/alembic/versions/e3f1a2b4c5d6_add_kyc_to_employer_profiles.py
   ```
2. Added a no-op merge migration reconciling both heads:
   ```python
   down_revision = ("b4e7f1a2c9d3", "e3f1a2b4c5d6")
   ```
   → `f9a3c7e1b2d4_merge_kyc_and_monetization_heads.py`
3. Verified a single head: `alembic heads` → `f9a3c7e1b2d4 (head)`
4. Remaining step (run by the team, not run here): `alembic upgrade head` —
   only the new migration and the empty merge point actually execute, since
   `a90a457e7f79` and `e3f1a2b4c5d6` were already applied.

## Prevention checklist

- Run `alembic heads` before pushing — more than one line means a fork exists.
- Sync migration files from the target branch before cutting a new one, not after.
- Rebase long-lived branches onto `develop`/`main` often.
- Optional: add an `alembic heads` check to CI to catch this at PR time.
