## Why

Managers can view equipment (lendable-item) booking groups but can only cancel whole groups or single items, and even those actions disappear once a booking is in the past — the manager detail UI hides them behind `Booking.is_cancelable()`, which returns `False` for past bookings. Managers routinely need to correct bookings after the fact (a customer picked up an extra item, a price needs adjusting, a note needs recording), so this gap forces them into the Django admin.

## What Changes

- Add a manager action to **add an item** to an existing booking group, reusing the group's pickup/return dates and skipping availability/lending-day validation (manager override). Requires resource + quantity + price.
- Add a manager action to **set a custom price** on an item by editing its total amount directly.
- Keep **remove item** as a cancel (item status set to Cancelled, row retained) — reusing the existing item-cancel service.
- Add a manager action to **post a comment** on a booking group as a `BookingMessage` that sends **no** email and is **visible to the customer** on their booking-group page.
- **Keep item bookings out of the free bookings quota**: item bookings are never free. Compensation selection for items (customer flow and manager add-item) skips compensations that count against free bookings, item bookings never set `uses_free_booking`, and the `apply_free_bookings_quota` transition skips item bookings.
- **Un-gate cancellation of past bookings**: show the "Cancel All" and per-item cancel actions in the manager detail view whenever the group/item is not already cancelled, instead of hiding them for past bookings.

## Capabilities

### New Capabilities
- `manager-item-booking-management`: Manager-facing management of equipment (lendable-item) booking groups — adding items, cancelling items/groups (including past bookings), setting custom item prices, and posting customer-visible comments without email notification. Also states that item bookings never use free bookings.

### Modified Capabilities
- `free-bookings-transition`: the legacy-booking selection skips item bookings.

## Impact

- Code: `re_sharing/bookings/services_item_bookings.py` (new manager services; compensation selection skips free-booking compensations), `re_sharing/bookings/services_quota_transition.py` (skip item bookings), `re_sharing/bookings/views_item_bookings.py` (new views + detail-view context), `re_sharing/bookings/urls.py` (three new routes), `re_sharing/templates/bookings/manager_show_booking_group.html` (add-item form, price editing, comment card, un-gated cancel), `re_sharing/templates/bookings/show-booking-group.html` (customer-visible comments), tests in `re_sharing/bookings/tests/`.
- Reuses existing pieces: `MessageForm`, `BookingMessage`, `calculate_item_total`, `get_lendable_items`, `Resource.get_bookable_compensations`, and the existing `manager_cancel_*` services.
- No data-model or migration changes; the manager comment path deliberately bypasses `save_bookingmessage` so `send_new_booking_message_email` is never enqueued.
- Access is limited to managers via the existing `@manager_required` decorator and service-level manager checks.
