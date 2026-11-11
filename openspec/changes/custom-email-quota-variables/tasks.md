## 1. Transition preview (red/green)

- [x] 1.1 In `re_sharing/bookings/tests/`, add failing tests for `get_quota_transition_preview(organization, from_date, to_date, resource_ids)` using the existing quota test setup (limited group with valid-from date, consuming compensation, paid compensation on the room, legacy bookings): counts and cost for a whole year; allocation across the year with a one-month range; range before the allowance is used up; open range; cost as `Decimal` with two decimals.
- [x] 1.2 Add failing tests for the resource filter (allocation across rooms, reporting only the selected room), a room without a paid compensation (series occurrence and single booking both counted in `without_rate`), an unlimited organization, and bookings already priced against the quota.
- [x] 1.3 Add a failing test that bookings and series are unchanged after the preview.
- [x] 1.4 Add the resource id to `RemovedBooking` and implement `get_quota_transition_preview` in `re_sharing/bookings/services_quota_transition.py` on top of `apply_free_bookings_quota(organization, dry_run=True)`, with the period rule of the custom email statistics. Run tests (green) and the existing transition tests.

## 2. Email task (red/green)

- [x] 2.1 In `re_sharing/organizations/tests/test_mails.py`, add failing tests: the three tags render in the body for a filter context with period and resources; they render `0` / `0.00` for an unlimited organization; the preview is not called when subject and body do not use the tags (mock); it is called when only the subject uses one; bookings are unchanged after sending.
- [x] 2.2 Add a failing view test that a test-send renders the tags for the organization it is rendered for.
- [x] 2.3 Implement in `send_custom_organization_email`: when subject or body contains `above_limit`, call the preview with the parsed filter and add `bookings_above_limit`, `cost_above_limit` and `bookings_above_limit_without_rate` to the context. Update the docstring. Run tests (green).

## 3. Page help

- [x] 3.1 Add a failing view test that the compose section lists the three tags.
- [x] 3.2 Add the tags and the one-line explanation to the help in `custom_organization_email.html`. Run tests (green).

## 4. Verification

- [x] 4.1 Run the full suite with coverage (`export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest --cov=re_sharing`) and confirm the touched modules stay above 95%.
- [x] 4.2 Run pre-commit on the changed files and fix any ruff, django-upgrade or djlint findings.
