## 1. Tests (red)

- [ ] 1.1 Add service test: `manager_add_item_to_booking_group` creates an item in the group with the supplied custom `total_amount`, and the group total reflects it
- [ ] 1.2 Add service test: `manager_add_item_to_booking_group` succeeds on a group whose pickup/return dates are in the past (no availability/lending-day errors)
- [ ] 1.3 Add service test: `manager_update_item_price` updates an item's `total_amount`
- [ ] 1.4 Add service test: `manager_add_booking_group_message` creates a `BookingMessage` on the group and does NOT enqueue `send_new_booking_message_email` (patch/assert not called)
- [ ] 1.5 Add service test: each new manager service raises `PermissionDenied` for a non-manager
- [ ] 1.6 Add view test: manager GET detail page of a past, non-cancelled group renders the "Cancel All" and per-item cancel actions
- [ ] 1.7 Add view test: manager can add an item, update a price, cancel a past group/item, and post a comment via their endpoints; non-manager is denied
- [ ] 1.8 Add view test: posted comment appears in `group_messages` for both the manager and customer group views
- [ ] 1.9 Add service test: `manager_add_item_to_booking_group` skips a compensation that counts against free bookings and raises `ValidationError` when only such compensations exist
- [ ] 1.10 Add service test: `create_item_booking_group` without `compensation_id` skips a compensation that counts against free bookings; item bookings keep `uses_free_booking=False` and leave the remaining free bookings unchanged
- [ ] 1.11 Add service test: `get_legacy_consuming_bookings` does not select item bookings with a free-booking compensation
- [ ] 1.12 Run the new tests and confirm they fail

## 2. Services (green)

- [ ] 2.1 Extract a helper in `services_item_bookings.py` that picks an item compensation (bookable compensations excluding `counts_against_free_bookings=True`, prefer `daily_rate`) and use it in `create_item_booking_group`
- [ ] 2.2 Add `manager_add_item_to_booking_group(user, slug, resource_id, quantity, total_amount=None)` to `services_item_bookings.py` (manager check; derive dates from `bookings_of_bookinggroup.first()`; pick compensation via the helper from 2.1, with fallback to any non-free-booking compensation on the resource; create `Booking` with `is_item_booking=True`, skipping availability/day validation; use custom `total_amount` or `calculate_item_total`)
- [ ] 2.3 Add `manager_update_item_price(user, slug, booking_id, total_amount)` to `services_item_bookings.py`
- [ ] 2.4 Add `manager_add_booking_group_message(user, slug, text)` to `services_item_bookings.py` that creates a `BookingMessage` on the group's first booking WITHOUT enqueueing any email
- [ ] 2.5 Exclude `is_item_booking=True` in `get_legacy_consuming_bookings` (`services_quota_transition.py`)

## 3. Views & URLs (green)

- [ ] 3.1 Add `manager_add_item_to_group_view`, `manager_update_item_price_view`, and `manager_add_booking_group_message_view` to `views_item_bookings.py` (`@require_http_methods(["POST"])` + `@manager_required`, catch `PermissionDenied`/`ValidationError`, redirect back to `bookings:manager-show-booking-group` with a message)
- [ ] 3.2 Extend `manager_show_booking_group_view` context with `lendable_items`, `group_messages`, and `message_form`
- [ ] 3.3 Extend `show_booking_group_view` (customer) context with `group_messages`
- [ ] 3.4 Register three routes in `urls.py`: `manager-add-item-to-group`, `manager-update-item-price`, `manager-add-booking-group-message`

## 4. Templates (green)

- [ ] 4.1 In `manager_show_booking_group.html`, change cancel gating from `is_cancelable` to `status != 3` for both "Cancel All" and per-item cancel
- [ ] 4.2 Add a per-item inline price-edit form (number input + save) posting to `manager-update-item-price`
- [ ] 4.3 Add an "Add item" form (resource select from `lendable_items`, quantity, total €) posting to `manager-add-item-to-group`
- [ ] 4.4 Add a "Comments" card listing `group_messages` and a `MessageForm` posting to `manager-add-booking-group-message`, noting the comment is visible to the customer
- [ ] 4.5 In `show-booking-group.html` (customer), add a read-only "Comments" section listing `group_messages`

## 5. Verify

- [ ] 5.1 Run the full bookings test suite and confirm all tests pass
- [ ] 5.2 Run pre-commit (ruff, django-upgrade, djLint) and fix any findings
