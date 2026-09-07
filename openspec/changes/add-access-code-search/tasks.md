## 1. Service: resolve bookings by code (red)

- [x] 1.1 Add tests in `re_sharing/bookings/tests/test_services.py` for `manager_filter_bookings_list` with an access code: booking-code match, organization permanent-code match, general permanent-code match
- [x] 1.2 Add tests for the phantom cases that must NOT match: stored code shadowed by an org permanent code, stored code on a resource without a smartlock, stored code on a resource with no access
- [x] 1.3 Add tests for blank, whitespace-only and too-short input performing no filtering (in particular that bookings with `access_code=""` are not selected)
- [x] 1.4 Add a test that a code matching a booking outside the manager's organizations or resources returns nothing
- [x] 1.5 Run the new tests and confirm they fail (red)

## 2. Service: implement the lookup (green)

- [x] 2.1 Add an `access_code_search` argument to `manager_filter_bookings_list`; trim it and treat blank or shorter than three characters as absent
- [x] 2.2 Build the candidate prefilter: bookings whose `access_code` matches, unioned with bookings whose organization and resource access are covered by a `PermanentCode` with that code, valid at `timespan.lower`
- [x] 2.3 Verify each candidate with `get_access_code(booking) == query`, loading candidates with `select_related("resource__access__parent_access", "organization")`
- [x] 2.4 Confirm the tests from section 1 pass (green)

## 3. Filter defaults and date window

- [x] 3.1 Add tests: an active code search returns confirmed bookings under the default status filter, and returns bookings that have already ended under the default past-bookings option
- [x] 3.2 Add tests: an explicitly selected status or date range still applies during a code search
- [x] 3.3 Add tests for the default date window being applied when no explicit range is given, and skipped when one is
- [x] 3.4 Implement: skip the status and past/recurring defaults while a code search is active unless the querystring set them explicitly
- [x] 3.5 Implement the default −7/+90 day window and an explicit unbounded mode
- [x] 3.6 Order results by proximity to now while a code search is active

## 4. View and template

- [x] 4.1 Add a view test asserting the access-code parameter reaches the service and the matched booking appears in the rendered partial
- [x] 4.2 Read `access_code` in `manager_list_bookings_view`, pass it to the service, and add it plus the applied window to the template context
- [x] 4.3 Add the search input to the filter form in `manager_list_bookings.html`, next to the organization search, wired to the existing htmx trigger
- [x] 4.4 Render the Code column and its per-row value only while a code search is active
- [x] 4.5 Show the applied date window with a "show all dates" link, and an empty state naming what was searched
- [x] 4.6 Confirm view tests pass

## 5. Organization search by permanent code

- [x] 5.1 Add tests in `re_sharing/organizations/tests/` for `manager_filter_organizations_list`: match by active code, match by expired code, an organization with several codes appears once, name search still works
- [x] 5.2 Extend the `search` branch to also match `PermanentCode.code` across all codes regardless of validity, with `.distinct()`
- [x] 5.3 Update the search field placeholder to mention codes
- [x] 5.4 Confirm the tests pass

## 6. Permissions

- [x] 6.1 Add tests that a non-manager receives a forbidden response and an anonymous user is redirected to login when requesting the booking list with an access-code search
- [x] 6.2 Confirm the existing `@manager_required` gate covers both cases without change

## 7. Verify

- [x] 7.1 Run the bookings and organizations test suites
- [x] 7.2 Run the full test suite and confirm coverage has not dropped below the project's level
- [x] 7.3 Run pre-commit (Ruff, djLint, django-upgrade) on the changed files
- [x] 7.4 Sanity-check the query count of a code search against a realistic candidate set; cap candidates before verification if it is out of line
