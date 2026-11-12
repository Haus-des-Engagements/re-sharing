## 1. Resource switch

- [x] 1.1 Test: a new resource has `exempt_from_free_bookings` false
- [x] 1.2 Add `exempt_from_free_bookings` to `Resource` with help text naming the compensation flag, and create the migration
- [x] 1.3 Extend the help text of `Compensation.counts_against_free_bookings` to mention exempt resources (migration)
- [x] 1.4 Resource admin: show the field, add it to `list_display` and `list_filter`

## 2. Pricing and bookability

- [x] 2.1 Tests for `price_booking`: flagged compensation on an exempt resource with allowance left, with allowance used up, and with a fallback given; booking on a non-exempt resource still limited
- [x] 2.2 Add `consumes_free_booking(compensation, resource)` to `services_pricing.py` and use it in `price_booking`
- [x] 2.3 Tests for `is_bookable_by_organization` and `save_booking` on an exempt resource with the allowance used up
- [x] 2.4 Use the predicate in `_exceeds_free_bookings` and `save_booking`
- [x] 2.5 Tests for series: `series_needs_fallback` is false on an exempt resource; occurrences are neither marked, charged nor dropped
- [x] 2.6 Use the predicate in `series_needs_fallback`; check `price_series_bookings` needs no further change

## 3. Booking form

- [x] 3.1 Tests for `get_bookable_compensations` on an exempt resource: flagged compensation offered with the allowance used up, remaining count `None`
- [x] 3.2 Implement in `get_bookable_compensations`
- [x] 3.3 View tests for the compensation partial: no remaining hint, no fallback choices for a series, no "no free booking left" message on an exempt resource
- [x] 3.4 Adjust `resources/views.py` and `bookings/partials/compensations.html` where the tests require it

## 4. Transition and email tags

- [x] 4.1 Tests: legacy bookings on an exempt resource are not selected and take no place in the allocation; a legacy series on an exempt resource stays unchanged
- [x] 4.2 Exclude exempt resources in `get_legacy_consuming_bookings` and `get_legacy_consuming_series`
- [x] 4.3 Test: `get_quota_transition_preview` does not count bookings on an exempt resource
- [x] 4.4 Mention exempt resources in the help of the `apply_free_bookings_quota` command and in the tag explanation on the custom email page

## 5. Documentation and checks

- [x] 5.1 Add ADR 0027 (resource exemption from free bookings), referring to ADR 0023
- [x] 5.2 Update translations for the new field label and help texts
- [x] 5.3 Run the full test suite and pre-commit; check coverage of the changed modules
