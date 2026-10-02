## 1. Data model and migrations

- [ ] 1.1 Add `free_bookings_per_year` (PositiveIntegerField, null) and `free_bookings_valid_from` (DateField, null) to `OrganizationGroup` with verbose names and help texts (the help text states that changes affect only later bookings); `clean()` and a `CheckConstraint` require both set or both empty; add migration
- [ ] 1.2 Add `counts_against_free_bookings` (BooleanField, default False) to `Compensation`; `clean()` and a `CheckConstraint` reject the flag when `hourly_rate` or `daily_rate` is set; add migration
- [ ] 1.3 Add `uses_free_booking` (BooleanField, default False) to `Booking`; add migration
- [ ] 1.4 Add to `BookingSeries` a nullable `fallback_compensation` ForeignKey (PROTECT) to `Compensation` and `is_quota_priced` (BooleanField, default False); add one migration (existing series get False)
- [ ] 1.5 Expose the new fields in `OrganizationGroupAdmin`, `CompensationAdmin` (list_display and list_filter for the flag), the `Booking` admin (list_filter for `uses_free_booking`) and the `BookingSeries` admin
- [ ] 1.6 Extend `OrganizationGroupFactory`, `CompensationFactory`, `BookingFactory` and `BookingSeriesFactory` with the new fields (defaults keep current behaviour)
- [ ] 1.7 Add model tests for defaults and field constraints in the three apps' `test_models.py`: number without date and date without number rejected on `full_clean()` and on save; flag on a compensation with an hourly or daily rate rejected on `full_clean()` and on save

## 2. Allowance and usage selectors (red, then green)

- [ ] 2.1 Add tests in `re_sharing/organizations/tests/test_selectors.py` for `get_free_bookings_allowance(organization, on_date)`: no groups with value → unlimited; valid-from 2027-01-01 → unlimited on 2026-12-31 and limited on 2027-01-01 (boundary, independent of today's date); several limited groups → maximum; one unlimited group → unlimited
- [ ] 2.2 Add tests for `is_free_bookings_allowance_limited_until(organization, last_date)`: false when the last date is before the valid-from date, true when on or after it, false for unlimited organizations
- [ ] 2.3 Add tests for `get_free_bookings_used(organization, year, exclude_booking=None)`: pending and confirmed bookings with the flag count as one each regardless of duration; cancelled and unavailable do not; bookings without the flag do not; other years do not; excluded booking is skipped
- [ ] 2.4 Add tests for `get_remaining_free_bookings(organization, on_date, exclude_booking=None)`: unlimited passthrough, subtraction, floor at zero (also when the allowance was lowered below the used count), full allowance for an organization that left its unlimited group with unflagged free bookings
- [ ] 2.5 Add tests in `re_sharing/resources/tests/test_selectors.py` (or `test_services.py`, following the app's existing layout) for `get_paid_fallback_compensations(organization, resource)`: active compensations with an hourly rate bookable by the org for the resource; inactive, rate-less and group-restricted ones excluded
- [ ] 2.6 Implement the selectors in `organizations/selectors.py` and the fallback selector in `resources`; represent "unlimited" with `None`
- [ ] 2.7 Confirm the tests from 2.1 to 2.5 pass

## 3. Pricing service

- [ ] 3.1 Add tests in `re_sharing/bookings/tests/test_services.py` for `price_booking(booking, compensation, fallback_compensation=None, exclude_booking=None)` covering every scenario of the `booking-free-bookings-pricing` spec: free booking left (`total_amount` stays `None`), last free booking, exhausted with fallback, exhausted without fallback, unlimited organization, non-consuming compensation, long booking still counts as one, quota year taken from start date, booking on 2026-12-31 not limited and booking on 2027-01-01 limited with valid-from 2027-01-01, nothing configured → unchanged pricing
- [ ] 3.2 Implement `price_booking` and a `FreeBookingsExhaustedError` in `bookings/services.py`
- [ ] 3.3 Add tests for a helper `needs_quota_reevaluation(booking, organization, compensation, start_date)`: true for new bookings and when organization, compensation or start year changes; false for changes of title, time, duration or room within the same year
- [ ] 3.4 Wire `price_booking` into `generate_booking` for new bookings and for edits that need re-evaluation (pass the existing booking as `exclude_booking`); for other edits keep `uses_free_booking` and compute `total_amount` as today. Update existing `generate_booking` tests and add the edit scenarios: same-year edit with longer duration and other room stays free; title edit of a pre-quota booking (`uses_free_booking` false) with 0 remaining is accepted and stays unflagged; edit into exhausted year is rejected; switching a paid booking to the consuming compensation uses a free booking if one is left
- [ ] 3.4a Add view tests for `preview_and_save_booking_view`: `FreeBookingsExhaustedError` on GET and on POST shows the message, creates no booking and redirects to the booking form with the session data kept; implement the handling in the view
- [ ] 3.5 Lock the organization row (`select_for_update`) and re-run pricing inside `save_booking` before saving, applying the same re-evaluation rule; add a test that the stored values match the re-priced result
- [ ] 3.6 Extend `is_bookable_by_organization` to reject a consuming compensation when remaining free bookings are zero, only for new bookings and edits that need re-evaluation; move the quota check in front of the early return for managers; add tests for the rejection, for the accepted pre-quota edit, and for a manager booking for a limited organization being rejected the same way
- [ ] 3.7 Give `is_bookable_by_organization` the series case (D5): with a paid fallback available for the room and organization the quota rule is skipped, without one it applies to the first occurrence; add tests for a series starting in an exhausted year with and without fallback

## 4. Compensation selector and single booking preview

- [ ] 4.1 Add view tests for `resources:get-compensations`: consuming compensation hidden when exhausted, shown with remaining free bookings when limited, shown without note for unlimited organizations, empty choices when only the consuming compensation exists and it is exhausted
- [ ] 4.2 Move the choice filtering into a selector (`get_bookable_compensations(organization, resource, on_date)`) used by the view, applying the quota rule; pass remaining free bookings to the template
- [ ] 4.3 Update `bookings/partials/compensations.html` to render the remaining-free-bookings note
- [ ] 4.4 Update `preview-booking.html` to state that the booking uses a free booking and how many remain in that year afterwards; add a view test
- [ ] 4.5 Show whether a booking used a free booking on the booking detail page and in the manager booking list row where the amount is shown; add view tests
- [ ] 4.6 Add view tests for `resources:get-compensations` in the edit case: current compensation of a pre-quota booking stays in the choices and selected with 0 remaining; a free booking is excluded from the remaining count shown; the compensation is hidden when the requested start year or organization differs from the booking's and nothing is left there
- [ ] 4.7 Pass the edited booking to the endpoint (optional `booking` parameter, set in the htmx attributes of the form fields in `bookings/forms.py` when the form has an instance) and to `get_bookable_compensations(organization, resource, on_date, booking=None)`; only accept a booking the user has booking permission for
- [ ] 4.8 Add view tests for the series case of the endpoint: consuming compensation offered for a series starting in an exhausted year when a paid fallback is available, hidden when none is; implement it in `get_bookable_compensations` using the repetition field of the request

## 5. Booking series

- [ ] 5.1 Add tests in `test_services.py` (series module) for `generate_bookings` pricing occurrences individually: first five free, rest paid with the fallback; allowance resets in the next year; running count within one run; unavailable occurrences do not use a free booking; unpriceable occurrences are dropped; a weekly series from 2026-11-02 into 2027 with valid-from 2027-01-01 keeps 2026 occurrences free and unflagged and counts only 2027 occurrences
- [ ] 5.2 Implement per-occurrence pricing in `generate_bookings` using `price_booking` with the series fallback and a running in-memory count per year; drop occurrences that raise the exhausted error and return their count (note the current `ThreadPoolExecutor`: the running count needs occurrences processed in date order, so price sequentially after the parallel availability check)
- [ ] 5.3 Make `create_booking_series_and_bookings` read `fallback_compensation` from booking data, set it and `is_quota_priced = True` on the series and return the pricing breakdown (free, paid, dropped, rate, total)
- [ ] 5.4 Add tests for `extend_booking_series`: for a quota-priced series, new occurrence priced with fallback when exhausted (at the fallback's current rate), dropped when no fallback or when the fallback is inactive or no longer bookable, free again in a new year; for a series with `is_quota_priced` false, the occurrence is created with the series compensation and `total_amount_per_booking` and `uses_free_booking` false even when the allowance is exhausted
- [ ] 5.5 Put the branch on `is_quota_priced` inside `generate_bookings`, so that series creation, `extend_booking_series` and the "Generate bookings" admin action share it; add admin tests for the action on a legacy series (series pricing, unflagged) and on a quota-priced series (fallback when exhausted)
- [ ] 5.6 Add form tests: fallback required for a limited organization with consuming compensation on a room with a paid option; required for a series starting in 2026 without end date when the allowance is limited from 2027-01-01; not required for a series ending before the valid-from date, for unlimited organizations or rooms without paid option; fallback choices limited to hourly compensations bookable by the org for the resource
- [ ] 5.7 Add the `fallback_compensation` field to the booking form (rendered inside the compensations partial, shown only when a series is selected and a consuming compensation is chosen) and its validation in `clean`, using `is_free_bookings_allowance_limited_until` with the series' last date or today plus 730 days, whichever is earlier; include it in `create_booking_data`
- [ ] 5.8 Update `preview-booking-series.html` to show the pricing breakdown and dropped occurrences; add view tests
- [ ] 5.9 Show per-occurrence amounts and the free-booking marker in the series detail page; add a view test

- [ ] 5.10 Add tests for `save_booking_series`: rejected with `PermissionDenied` when the series compensation is not bookable by the organization; rejected when the fallback is inactive, has no hourly rate or is not bookable for the resource; rejected when a fallback is required (D11) but missing; occurrences re-priced at save when free bookings were used after the preview; nothing is stored on rejection
- [ ] 5.11 Implement the guard, the fallback validation, the lock on the organization row and the re-pricing in `save_booking_series`
- [ ] 5.12 Wrap each series in `extend_booking_series` and in the admin action in `transaction.atomic()` with the lock on the organization row; add a test that an error in one series keeps the occurrences of the others
- [ ] 5.13 Add tests for `manager_confirm_booking_series` on a quota-priced series: unavailable occurrence that became free uses a free booking when one is left, is priced with the fallback when none is left, is deleted when it cannot be priced; occurrences are handled in date order; a legacy series keeps today's behaviour
- [ ] 5.14 Implement the pricing of `UNAVAILABLE` occurrences that become `CONFIRMED` in `manager_confirm_booking_series`
- [ ] 5.15 Add admin tests for `BookingSeriesAdmin.save_model`: saving a quota-priced series keeps `compensation`, `total_amount` and `uses_free_booking` of its bookings and still copies organization, user and title; a legacy series is synced as today
- [ ] 5.16 Restrict the pricing fields in `BookingSeriesAdmin.save_model` to series with `is_quota_priced` false

## 6. Dashboard

- [ ] 6.1 Add tests in `re_sharing/dashboards/tests/test_services.py` for `get_free_bookings_overview(user)`: one entry per organization with a limited allowance, with used and allowance for the current and the following year; unlimited organizations omitted; a year before the valid-from date omitted
- [ ] 6.2 Implement `get_free_bookings_overview` in `dashboards/services.py` on top of the organization selectors and pass it from `users_bookings_and_permissions_dashboard_view`
- [ ] 6.3 Render the numbers in the "My organizations" table of `dashboards/users_bookings_and_permissions.html`; add view tests for a limited and an unlimited organization

## 7. Documentation and rollout

- [ ] 7.1 Write `docs/ADR/0023-Free-Bookings-Quota.md` (allowance on groups with valid-from by booking start date, both fields set together, flag on compensation and never on a priced one, no manager bypass, changes affect only later bookings, free bookings keep an empty amount, a booking counts as one and stores that it did, series occurrences count individually, fallback for series crossing into a limited year, edits re-evaluated only on organization, compensation or year change, pre-quota series keep today's pricing in every generation path, unavailable occurrences priced on confirmation, admin series edits keep per-occurrence pricing, first created first served, no re-pricing of existing bookings)
- [ ] 7.2 Add a README section on configuring the quota: deploying changes nothing; the restriction starts when the free compensation is flagged and allowance and valid-from (2027-01-01) are set on the limited groups, which should happen when the announcement goes out; create paid compensations for rooms that should remain bookable; existing series stay on today's pricing until the transition command marks them as quota-priced; managers check new organizations for splits that only multiply the allowance
- [ ] 7.3 Add German translations for all new strings (with plural forms for "free booking(s)") and compile messages
- [ ] 7.4 Run the full test suite with coverage and confirm coverage stays at or above 95 percent
- [ ] 7.5 Run pre-commit on all changed files
