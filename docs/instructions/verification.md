# Verification

What must be proven before a phase is accepted. Every item is evidence-based: a test name, a command,
or a screenshot. "It worked when I clicked it" is not evidence.

## 1. Test matrix

### `assetflow_base`

| Case | Type | Asserts |
|------|------|---------|
| Department cycle rejected | Python | writing a descendant as parent raises `ValidationError` |
| Duplicate department code | Python | unique constraint fails |
| Disabled department not selectable | Python | domain in views excludes it; creating a record with it is rejected |
| Role compute | Python | groups -> `employee`/`department_head`/`asset_manager`/`admin` |
| Promotion authorization | Access | employee cannot write `groups_id`; admin can |
| Signup creates employee | Http/Form | new account has `base.group_user`, no AssetFlow group, an employee row |
| Notification ownership | Access | user A cannot read/write user B's notification |
| Activity log immutability | Access | employee has no access; manager read-only |

### `assetflow_assets`

| Case | Type | Asserts |
|------|------|---------|
| Tag sequence | Python | first asset is `AF-0001`; tag cannot be written |
| Double allocation | Python + DB | second active allocation raises; direct SQL insert also fails |
| Allocation requires available | Python | allocating a maintenance/lost asset raises |
| Return requires notes | Python | missing condition/notes raises |
| Return reopens asset | Python | state `available`, holder cleared |
| Transfer approval atomic | Python | old allocation returned, new active, asset holder updated |
| Double transfer approval | Python | second approval is rejected, no duplicate allocation |
| One pending transfer | DB | partial unique index rejects a second request |
| Overdue computed | Python | expected date yesterday -> `is_overdue` true; today -> false |
| Overdue notification idempotent | Python | two cron runs in one day create one notification |
| Employee sees own allocation only | Access | second employee's allocation is invisible |
| Department head scope | Access | sees department, not another department |

### `assetflow_booking`

| Case | Type | Asserts |
|------|------|---------|
| Adjacent slots | Python | 09:00-10:00 then 10:00-11:00 succeeds |
| Overlap rejected | Python | 09:30-10:30 raises with the conflicting slot |
| Contained/containing overlap | Python | 09:15-09:45 and 08:00-12:00 both rejected |
| Cancelled slot reusable | Python | cancel then book the same slot |
| Non-bookable asset | Python | create raises |
| End before start | Python | raises |
| Past booking | Python | raises |
| Reminder once | Python | cron twice -> one notification, `reminder_sent` true |
| State sync | Python | upcoming -> ongoing -> completed; asset reserved then available |
| Concurrency | Thread/test | two overlapping creates in parallel: exactly one succeeds |
| Employee scope | Access | only own/department bookings visible |

### `assetflow_maintenance`

| Case | Type | Asserts |
|------|------|---------|
| Pending does not change asset | Python | asset state unchanged on create |
| Approval flips state | Python | asset `maintenance`, `previous_asset_state` stored |
| Rejection requires reason | Python | raises; asset unchanged |
| Resolve restores | Python | available -> available; allocated -> allocated |
| Duplicate open request | DB | second open request rejected |
| Booking conflict | Python | approval blocked while a booking is active |
| Role matrix | Access | only manager/admin approve; employee can raise for own asset |
| History | Python | resolved request remains linked to the asset |

### `assetflow_audit`

| Case | Type | Asserts |
|------|------|---------|
| Line generation scope | Python | only assets in department/location get lines |
| Location snapshot | Python | moving an asset later does not change the line's expected location |
| Close with pending line | Python | raises and lists the offending assets |
| Close locks cycle | Python | line writes after close raise |
| Repeated close | Python | second close is a no-op/raises, no double status change |
| Missing -> Lost | Python | asset state `lost` |
| Damaged -> condition | Python | condition `damaged`, state preserved |
| Auditor scope | Access | auditor writes only assigned cycle lines |
| Discrepancy count | Python | missing + damaged |

### `assetflow_reports`

| Case | Type | Asserts |
|------|------|---------|
| KPI counts | Python | seeded data -> exact values |
| Rule-filtered KPIs | Access | employee sees own numbers; manager sees all |
| Dashboard query count | Python | `assertQueryCount` within budget |
| PDF renders | Manual/Http | department allocation and discrepancy PDFs return 200 |
| Graphs/pivots load | Manual | no XML/JS errors in the browser console |

## 2. Running tests

Docker:

```powershell
docker compose exec odoo odoo -d assetflow -u assetflow_base --test-enable --test-tags /assetflow_base --stop-after-init
```

All addons:

```powershell
docker compose exec odoo odoo -d assetflow `
  -u assetflow_base,assetflow_assets,assetflow_booking,assetflow_maintenance,assetflow_audit,assetflow_reports `
  --test-enable `
  --test-tags /assetflow_base,/assetflow_assets,/assetflow_booking,/assetflow_maintenance,/assetflow_audit,/assetflow_reports `
  --stop-after-init
```

A clean run must show zero failures/errors and no tracebacks in the log. Save the tail of the log as
evidence.

## 3. Access testing pattern

```python
from odoo.tests import TransactionCase, new_test_user

class TestAllocationAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee_user = new_test_user(
            cls.env, login="emp1", groups="base.group_user,assetflow_base.group_assetflow_employee",
        )
        cls.manager_user = new_test_user(
            cls.env, login="mgr1", groups="base.group_user,assetflow_base.group_assetflow_asset_manager",
        )
        # create employees, departments, allocations with cls.env (admin)

    def test_employee_cannot_see_other_allocation(self):
        allocation = self.env["assetflow.allocation"].create({...})
        self.assertFalse(allocation.with_user(self.employee_user).exists())
```

Also test that the server rejects a write even when the UI is bypassed with `write()`/RPC. Hiding a
button is not authorization.

## 4. Concurrency testing

For allocation and booking, prove the database prevents the race:

- **Allocation:** attempt two `create` calls in separate transactions (or one direct SQL insert) for the
  same asset; assert one succeeds and one fails on the unique index.
- **Booking:** start two transactions that both pass the Python check before either commits; the row
  lock must serialize them and the second must see the first booking. If a deterministic test is hard,
  add a test that asserts the lock is acquired (`LockError` path) and document the manual check.

## 5. Manual demo checklist

Run on a **fresh** database with demo data:

- [ ] Admin logs in, creates a department and a category, promotes one Department Head and one Asset
      Manager from the Employee Directory.
- [ ] The promoted users can log in and see the expected menus; an unpromoted employee cannot.
- [ ] Asset Manager registers a laptop; tag `AF-0001`; photo and documents attach.
- [ ] Allocate the laptop to Priya; Raj's attempt is blocked with the holder name and Transfer action.
- [ ] Priya requests a transfer to Raj; the Department Head approves; history shows both.
- [ ] Book Room B2 09:00-10:00; 09:30-10:30 rejected; 10:00-11:00 accepted.
- [ ] Maintenance request stays pending; approval flips the asset; resolution restores it.
- [ ] Audit cycle start, mark one asset missing and one damaged, close, see Lost/damaged and the PDF.
- [ ] Dashboard KPI numbers match the records; overdue return and notifications appear.
- [ ] Log out and confirm a non-admin cannot reach admin URLs or RPC methods.

## 6. Evidence to capture per phase

1. Branch and commit SHA.
2. Install/update command and tail of the log (no warnings).
3. Test command and summary (`0 failed, 0 error`).
4. Screenshots of the main screen(s), including the conflict/error paths.
5. Any spec divergence and the commit that updated the spec.
6. Known limitations and the next task.

Paste these into the Murmur review thread and the review log. A phase without evidence is not
accepted.

## 7. CI sketch (when the repo gets one)

```yaml
# .github/workflows/odoo.yml
name: odoo19
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: odoo
          POSTGRES_PASSWORD: odoo
        options: >-
          --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 20
        ports: ["5432:5432"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: odoo-bin -d ci --db_host=localhost --db_user=odoo --db_password=odoo -i all --test-enable --stop-after-init
```

Keep CI optional until the addons install locally; a red CI that nobody can reproduce is worse than
no CI.
