# ADR-0003: Concurrency for allocation and booking

- **Status:** accepted, 2026-11-21
- **Deciders:** daksh, flat-orchid, northern-envelope

## Context

Two rules are vulnerable to races:

1. one active allocation per asset;
2. no overlapping bookings for the same asset in a time range.

A Python `search_count` before `create` is not enough: two requests can both read "no conflict" and
both commit. The demo may not hit the race, but the brief explicitly tests double allocation and
overlap, and a corrupt database is hard to unwind during a hackathon.

Odoo 19 gives us:

- `models.Constraint` for table constraints;
- `models.Index` and `models.UniqueIndex` with full SQL definitions, including `WHERE`;
- `lock_for_update()` / `try_lock_for_update()` for row locks;
- one transaction per request.

PostgreSQL also supports exclusion constraints (`EXCLUDE USING gist`) with `btree_gist`, which would
enforce non-overlapping ranges declaratively.

## Decision

### Allocation

Use a partial unique index declared on the model:

```python
_only_one_active = models.UniqueIndex(
    "(asset_id) WHERE state = 'active'",
    "This asset already has an active allocation.",
)
```

The database rejects the second active allocation even if every Python guard is bypassed (SQL, RPC,
concurrent transactions). Asset state changes happen in the same transaction as the allocation write.

### Booking

Use half-open intervals and a row lock:

1. validate `end > start` and the bookable flag;
2. `asset.lock_for_update()` to serialize writers for this asset;
3. search for any non-cancelled booking where
   `existing.start_datetime < new.end_datetime` and `existing.end_datetime > new.start_datetime`;
4. create or write only if the search is empty.

Half-open `[start, end)` keeps `09:00-10:00` and `10:00-11:00` adjacent rather than overlapping.

A cancelled booking is excluded from the check so the slot becomes reusable.

### Transfer and audit

- Transfer approval locks the asset before closing the old allocation and creating the new one.
- Audit close locks the cycle row and checks that every line is decided before writing statuses.

## Why not PostgreSQL exclusion constraints

- They need `btree_gist` and a range column or expression; the extension may not be installed on
  every host, including the official Docker image, without a migration.
- Odoo's addon install path would have to create the extension and the constraint; that is more
  moving parts than a hackathon needs.
- They protect bookings only, not the allocation rule, so we would still need the unique index.

The chosen approach has no extension dependency and is testable with Odoo's own primitives.

## Consequences

**Positive**

- The allocation invariant is enforced by PostgreSQL, not by convention.
- Booking serializes per asset, not globally, so different assets still book in parallel.
- Errors are explicit: unique violation or `LockError`, both mapped to a user-readable message.
- The rules are testable in `TransactionCase` and with a direct SQL attempt.

**Negative**

- `lock_for_update()` raises `LockError` when the row is busy; the UI must tell the user to retry
  rather than hanging.
- The booking check is still application-level; a bug that skips the method could insert an overlap.
  A database-level exclusion is the only absolute guarantee.
- Long-running transactions holding the asset lock can block booking for that asset; keep the
  transaction short and do not call external services while holding it.

## Verification

- Two concurrent allocation creates: exactly one commits; the other fails with the constraint message.
- Direct SQL insert of a second active allocation fails.
- Overlap matrix: adjacent allowed; partial, contained, containing, and identical overlaps rejected.
- Cancelling then rebooking the same slot succeeds.
- A forced concurrent booking test asserts the second request sees the first (or gets `LockError`).
- Transfer double-approval creates exactly one new allocation.
- Audit double-close changes asset statuses once.

## Alternatives considered

1. **Python check only.** Rejected: race-prone.
2. **Global lock on the asset model.** Rejected: serializes unrelated assets and hurts the demo.
3. **PostgreSQL exclusion constraint for bookings.** Rejected for portability and setup cost; revisit
   if the app outgrows the hackathon.
4. **Advisory locks (`pg_advisory_xact_lock`).** Viable, but Odoo's row lock is clearer and testable;
   an advisory lock keyed on asset id is the fallback if row locking proves too coarse.
