## Why

Managers use `/organizations/custom-email/` to email organizations selected by their booking activity, but the only time filter is "last X months" counted backwards from now. Managers need to target a specific period, including future periods (e.g. "everyone with a confirmed booking in the next quarter"), and to restrict the count to specific rooms or parking lots. On top of that, the `{{ total_amount }}` template tag advertised on the page is never populated in sent emails, so managers cannot trust the numbers they send out.

## What Changes

- **BREAKING (UI/URL)**: Replace the `months` filter with `from_date` and `to_date` filters (day granularity, either bound optional, future dates allowed). A booking counts when it is confirmed and its start lies within the range. No dates means all-time statistics.
- Booking statistics (`booking_count`, `total_amount`) are always computed, so `min_bookings` and `max_amount` work without a time filter (today they are silently ignored unless `months` is set).
- Add a multi-select **Resources** filter listing rooms and parking lots only. Selected resources narrow which bookings are counted. Empty selection means all resources. Resource IDs of other types are ignored server-side.
- Validate `from_date <= to_date` and show an error instead of a result list.
- Fix the email task so `{{ number_of_bookings }}` and `{{ total_amount }}` are both populated from the same criteria as the preview table (dates and resources).
- Replace the `{{ months }}` email template tag with `{{ from_date }}` and `{{ to_date }}`, rendered as localized short dates (e.g. `01.01.2026`). Update the on-page help text.
- Treat `min_bookings=0` as a set value instead of "unset".

## Capabilities

### New Capabilities
- `organization-custom-email`: Manager-only page to filter confirmed organizations by groups, booking date range, resources, booking count and total amount, preview the result, and send templated emails with per-organization statistics.

### Modified Capabilities
<!-- none: no existing spec covers the custom email page -->

## Non-goals

- Saving or reusing filter presets or email drafts.
- Counting bookings that merely overlap the range (only the booking start is considered).
- Filtering by lendable items or by location.
- Changing who may access the page (still `@manager_required`).
- Changing how emails are queued or delivered.

## Impact

- `re_sharing/organizations/selectors.py`: `get_filtered_organizations` signature changes (`months` removed; `from_date`, `to_date`, `resource_ids` added). `get_organization_booking_count` is replaced by a stats selector returning count and amount.
- `re_sharing/organizations/views.py`: both custom email views parse the new parameters and pass a JSON-serialisable filter context to the task.
- `re_sharing/organizations/mails.py`: `send_custom_organization_email` uses the new stats selector; dead `hasattr` branch removed.
- `re_sharing/templates/organizations/custom_organization_email.html`: new inputs, hidden fields, help text.
- Tests in `re_sharing/organizations/tests/` (`test_selectors.py`, `test_views.py`, `test_mails.py`): existing `months` tests migrated, new cases added.
- Bookmarked URLs containing `months=` stop filtering by time (they fall back to all-time stats). No data migration.
