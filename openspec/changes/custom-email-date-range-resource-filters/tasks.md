## 1. Selector: date range and always-on statistics (red/green)

- [x] 1.1 In `re_sharing/organizations/tests/test_selectors.py`, migrate every `months=` test of `get_filtered_organizations` to `from_date`/`to_date` built from explicit local dates (not `timezone.now()`), keeping the existing assertions. Run and confirm they fail (red).
- [x] 1.2 Add failing selector tests for the boundary rules: start at `from_date` 00:00 counts, start at `to_date` 23:59 counts, start the day after `to_date` does not, start the day before `from_date` does not, booking overlapping into the range but starting before it does not.
- [x] 1.3 Add failing selector tests for open-ended ranges (only `from_date`, only `to_date`), all-time when no dates, future range, and `min_bookings`/`max_amount` working with no date range and with `min_bookings=0`.
- [x] 1.4 Implement in `re_sharing/organizations/selectors.py`: private `_confirmed_booking_filter(from_date, to_date, resource_ids) -> Q` that converts days to aware datetimes (`time.min` / `time.max`, project time zone); rewrite `get_filtered_organizations(include_groups, exclude_groups, min_bookings, max_amount, from_date, to_date, resource_ids)` to always annotate `booking_count` and `total_amount` with that shared `Q`. Run tests (green).

## 2. Selector: resource filter (red/green)

- [x] 2.1 Add failing tests: a selected room narrows count and amount, multiple selected resources combine, no selection counts all, a `lendable_item` ID is dropped and yields zero counts, resource filter combines with a date range, thresholds use the narrowed statistics.
- [x] 2.2 Add failing test for `get_custom_email_filterable_resources()` returning rooms and parking lots ordered by type then name and excluding lendable items.
- [x] 2.3 Implement the `resource_ids` branch in `_confirmed_booking_filter` (type-guarded queryset on `Resource.ResourceTypeChoices.ROOM`/`PARKING_LOT`) and `get_custom_email_filterable_resources()`. Run tests (green).

## 3. Selector: per-organization stats for emails (red/green)

- [x] 3.1 Add failing tests for `get_organization_booking_stats(organization, from_date, to_date, resource_ids)` returning `{"booking_count", "total_amount"}`: matches the preview for the same organization and filter, all-time when no dates, `total_amount` is `0` (not `None`) when nothing matches, resource narrowing.
- [x] 3.2 Implement `get_organization_booking_stats` using `_confirmed_booking_filter` and one aggregate on `organization.bookings_of_organization`; remove `get_organization_booking_count` and its tests. Run tests (green).

## 4. Email task (red/green)

- [x] 4.1 In `re_sharing/organizations/tests/test_mails.py`, replace the `months` test with failing tests for the new `filter_context` shape: `number_of_bookings` populated, `total_amount` populated, both respect `resource_ids`, `from_date`/`to_date` rendered as `dd.mm.yyyy`, open bound renders empty string, all-time stats when no dates, `months` not in context.
- [x] 4.2 Implement in `re_sharing/organizations/mails.py`: parse ISO dates from `filter_context`, call `get_organization_booking_stats`, always set `number_of_bookings` and `total_amount`, format dates with `date_format(value, "SHORT_DATE_FORMAT")`, delete the dead `hasattr` branch. Update the docstring. Run tests (green).

## 5. Views (red/green)

- [x] 5.1 In `re_sharing/organizations/tests/test_views.py`, migrate the `months` view tests to `from_date`/`to_date` and add failing tests for the GET view: date range and resources are passed to the selector, `from_date > to_date` shows an error and no list, invalid date shows an error, `min_bookings=0` is honoured, context contains `filterable_resources`, `selected_resources`, `from_date`, `to_date`.
- [x] 5.2 Add failing tests for the POST view: `filter_context` enqueued with keys `min_bookings`, `max_amount`, `from_date`, `to_date`, `resource_ids` (ISO strings, ints); invalid range redirects with an error and enqueues nothing; resources narrow the sent set.
- [x] 5.3 Implement in `re_sharing/organizations/views.py`: a private helper that parses the filter parameters from a `QueryDict` (dates via `date.fromisoformat`, `resources` via `getlist`, `min_bookings` with `is not None`) and validates the range; rewire both views to use it and the new selector signature; build the JSON-serialisable `filter_context` and always pass it to the task. Run tests (green).

## 6. Template

- [x] 6.1 Replace the `months` input in `re_sharing/templates/organizations/custom_organization_email.html` with `from_date` and `to_date` `<input type="date">` fields (pattern from `bookings/manager_list_bookings.html`), add the `resources` multi-select with `<optgroup>` per type, and update the hidden fields in the send form.
- [x] 6.2 Update the compose help text (add `from_date`, `to_date`, keep `number_of_bookings`, `total_amount`, drop `months`) and the right-hand help card (date range, resources limited to rooms and parking lots). Add view tests asserting the rendered page contains the new inputs and not the `months` input.
- [x] 6.3 Run `djlint` via pre-commit on the template and fix findings.

## 7. Verification

- [x] 7.1 Run the full suite with coverage (`export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest --cov=re_sharing`) and confirm coverage stays above 95% for the touched modules.
- [x] 7.2 Run `pre-commit run --all-files` and fix any ruff, django-upgrade or djlint findings.
