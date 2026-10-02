## 1. Selectors (red, then green)

- [x] 1.1 Add tests in `re_sharing/organizations/tests/test_selectors.py` for `get_limited_organizations()`: confirmed organizations in a limited group are returned; organizations also in an unlimited group, pending organizations and organizations without groups are not; each organization once
- [x] 1.2 Add tests in `re_sharing/bookings/tests/test_services_quota_transition.py` for `get_legacy_consuming_bookings(organization)`: standalone booking and legacy series occurrence selected; quota-priced series occurrence, flagged booking, invoiced booking, past booking, paid compensation, unavailable occurrence, cancelled booking and booking before the valid-from date excluded; ordered by start
- [x] 1.3 Implement `get_limited_organizations` in `organizations/selectors.py` and `get_legacy_consuming_bookings` in `bookings/services_quota_transition.py`; confirm 1.1 and 1.2 pass

## 2. Transition service

- [x] 2.1 Add tests for `apply_free_bookings_quota(organization)`: chronological allocation per year with quota-priced bookings already counted; charging at the cheapest bookable rate with the correct amount; deletion of occurrences and cancellation of standalone bookings without a paid compensation and without enqueued emails; legacy series marked with fallback, series without occurrences marked too, paid series untouched; a second run changes nothing; `dry_run=True` returns the same report and persists nothing
- [x] 2.2 Implement `TransitionReport` (dataclass with allowance per year, kept free, charged, deleted, cancelled, updated series, totals) and `apply_free_bookings_quota` with `transaction.atomic()`, `select_for_update` on the organization and `transaction.set_rollback(True)` in dry run; use `price_booking` with the fallback and a running reserved count per year
- [x] 2.3 Confirm the tests from 2.1 pass and that `price_booking` is the only place amounts are computed

## 3. Management command

- [x] 3.1 Add tests in `re_sharing/bookings/tests/test_commands.py` for `apply_free_bookings_quota`: summary line per organization with counts and charged total; verbosity 2 lists bookings with date, resource and outcome; "nothing to do" for untouched organizations; `--dry-run` prefix and no changes; `--organizations` restricts the run and an unknown slug fails before any change; an error in one organization is reported and earlier organizations keep their changes
- [x] 3.2 Implement `bookings/management/commands/apply_free_bookings_quota.py` with `--dry-run`, `--organizations`, the report output and totals; catch exceptions per organization and exit non-zero when any failed

## 4. Documentation and quality

- [x] 4.1 Extend the README rollout section with the command: dry run first, review, real run, optional batching by organization, re-running is safe
- [x] 4.2 Add a short note to `docs/ADR/0023-Free-Bookings-Quota.md` under Consequences that the one-time transition allocates chronologically
- [x] 4.3 Run the full test suite with coverage and confirm the new modules are fully covered
- [x] 4.4 Run pre-commit on all changed files
