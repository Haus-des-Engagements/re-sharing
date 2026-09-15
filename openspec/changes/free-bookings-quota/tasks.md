## 1. Data model and migrations

- [ ] 1.1 Add `free_bookings_per_year` (PositiveIntegerField, null) and `free_bookings_valid_from` (DateField, null) to `OrganizationGroup` with verbose names and help texts; add migration
- [ ] 1.2 Add `counts_against_free_bookings` (BooleanField, default False) to `Compensation`; add migration
- [ ] 1.3 Add `uses_free_booking` (BooleanField, default False) to `Booking`; add migration
- [ ] 1.4 Add nullable `fallback_compensation` ForeignKey (PROTECT) on `BookingSeries` to `Compensation`; add migration
- [ ] 1.5 Expose the new fields in `OrganizationGroupAdmin`, `CompensationAdmin` (list_display and list_filter for the flag), the `Booking` admin (list_filter for `uses_free_booking`) and the `BookingSeries` admin
- [ ] 1.6 Extend `OrganizationGroupFactory`, `CompensationFactory`, `BookingFactory` and `BookingSeriesFactory` with the new fields (defaults keep current behaviour)
- [ ] 1.7 Add model tests for defaults and field constraints in the three apps' `test_models.py`

## 2. Allowance and usage selectors (red, then green)

- [ ] 2.1 Add tests in `re_sharing/organizations/tests/test_selectors.py` for `get_free_bookings_allowance(organization, on_date)`: no groups with value → unlimited; value with valid-from in the future → unlimited; value with valid-from in the past → number; several limited groups → maximum; one unlimited group → unlimited
- [ ] 2.2 Add tests for `get_free_bookings_used(organization, year, exclude_booking=None)`: pending and confirmed bookings with the flag count as one each regardless of duration; cancelled and unavailable do not; bookings without the flag do not; other years do not; excluded booking is skipped
- [ ] 2.3 Add tests for `get_remaining_free_bookings(organization, on_date, exclude_booking=None)`: unlimited passthrough, subtraction, floor at zero
- [ ] 2.4 Add tests in `re_sharing/resources/tests/test_selectors.py` (or `test_services.py`, following the app's existing layout) for `get_paid_fallback_compensations(organization, resource)`: active compensations with an hourly rate bookable by the org for the resource; inactive, rate-less and group-restricted ones excluded
- [ ] 2.5 Implement the selectors in `organizations/selectors.py` and the fallback selector in `resources`; represent "unlimited" with `None`
- [ ] 2.6 Confirm the tests from 2.1 to 2.4 pass

## 3. Pricing service

- [ ] 3.1 Add tests in `re_sharing/bookings/tests/test_services.py` for `price_booking(booking, compensation, fallback_compensation=None, exclude_booking=None)` covering every scenario of the `booking-free-bookings-pricing` spec: free booking left, last free booking, exhausted with fallback, exhausted without fallback, unlimited organization, non-consuming compensation, long booking still counts as one, quota year taken from start date
- [ ] 3.2 Implement `price_booking` and a `FreeBookingsExhaustedError` in `bookings/services.py`
- [ ] 3.3 Wire `price_booking` into `generate_booking` for new bookings and for edits (pass the existing booking as `exclude_booking`); update existing `generate_booking` tests and add the edit scenarios (same-year edit stays free even with a longer duration, edit into exhausted year is rejected, switching a paid booking to the consuming compensation uses a free booking if one is left)
- [ ] 3.4 Lock the organization row (`select_for_update`) and re-run pricing inside `save_booking` before saving; add a test that the stored values match the re-priced result
- [ ] 3.5 Extend `is_bookable_by_organization` to reject a consuming compensation when remaining free bookings are zero; add tests for the rejection and for managers following the same rule

## 4. Compensation selector and single booking preview

- [ ] 4.1 Add view tests for `resources:get-compensations`: consuming compensation hidden when exhausted, shown with remaining free bookings when limited, shown without note for unlimited organizations, empty choices when only the consuming compensation exists and it is exhausted
- [ ] 4.2 Move the choice filtering into a selector (`get_bookable_compensations(organization, resource, on_date)`) used by the view, applying the quota rule; pass remaining free bookings to the template
- [ ] 4.3 Update `bookings/partials/compensations.html` to render the remaining-free-bookings note
- [ ] 4.4 Update `preview-booking.html` to state that the booking uses a free booking and how many remain in that year afterwards; add a view test
- [ ] 4.5 Show whether a booking used a free booking on the booking detail page and in the manager booking list row where the amount is shown; add view tests

## 5. Booking series

- [ ] 5.1 Add tests in `test_services.py` (series module) for `generate_bookings` pricing occurrences individually: first five free, rest paid with the fallback; allowance resets in the next year; running count within one run; unavailable occurrences do not use a free booking; unpriceable occurrences are dropped
- [ ] 5.2 Implement per-occurrence pricing in `generate_bookings` using `price_booking` with the series fallback and a running in-memory count per year; drop occurrences that raise the exhausted error and return their count (note the current `ThreadPoolExecutor`: the running count needs occurrences processed in date order, so price sequentially after the parallel availability check)
- [ ] 5.3 Make `create_booking_series_and_bookings` read `fallback_compensation` from booking data, set it on the series and return the pricing breakdown (free, paid, dropped, rate, total)
- [ ] 5.4 Add tests for `extend_booking_series`: new occurrence priced with fallback when exhausted, dropped when no fallback, free again in a new year
- [ ] 5.5 Update `extend_booking_series` to use the same pricing path
- [ ] 5.6 Add form tests: fallback required for a limited organization with consuming compensation on a room with a paid option; not required for unlimited organizations or rooms without paid option; fallback choices limited to hourly compensations bookable by the org for the resource
- [ ] 5.7 Add the `fallback_compensation` field to the booking form (rendered inside the compensations partial, shown only when a series is selected and a consuming compensation is chosen) and its validation in `clean`; include it in `create_booking_data`
- [ ] 5.8 Update `preview-booking-series.html` to show the pricing breakdown and dropped occurrences; add view tests
- [ ] 5.9 Show per-occurrence amounts and the free-booking marker in the series detail page; add a view test

## 6. Documentation and rollout

- [ ] 6.1 Write `docs/ADR/0023-Free-Bookings-Quota.md` (allowance on groups, flag on compensation, a booking counts as one and stores that it did, series occurrences count individually, first created first served, no re-pricing of existing bookings)
- [ ] 6.2 Add a README section on configuring the quota: flag the free compensation, set allowance and valid-from on the limited groups, create paid compensations for rooms that should remain bookable
- [ ] 6.3 Add German translations for all new strings (with plural forms for "free booking(s)") and compile messages
- [ ] 6.4 Run the full test suite with coverage and confirm coverage stays at or above 95 percent
- [ ] 6.5 Run pre-commit on all changed files
