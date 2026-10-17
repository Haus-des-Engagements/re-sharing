## Context

Equipment (lendable-item) bookings are modelled as a `BookingGroup` with one child `Booking` per item (`re_sharing/bookings/models.py`). Managers view a group at `manager_show_booking_group_view` (`re_sharing/bookings/views_item_bookings.py`) rendered by `manager_show_booking_group.html`. The template gates its cancel actions behind `Booking.is_cancelable()` / `BookingGroup.is_cancelable()`, both of which return `False` once the booking start is in the past (`Booking.is_cancelable` in `models.py`). The manager cancel *services* (`manager_cancel_booking_group`, `manager_cancel_item_in_booking_group` in `services_item_bookings.py`) already ignore `is_cancelable`, so the block is purely in the UI.

Item creation logic lives in `create_item_booking_group` / `validate_item_booking_data` (`services_item_bookings.py`), which already has a manager-bypass branch for private-item bookability. `BookingMessage` (`models.py`) attaches to a single `Booking`, and `save_bookingmessage` (`services.py`) always enqueues `send_new_booking_message_email`. The customer-facing group page (`show-booking-group.html`) currently shows no messages.

The yearly free bookings quota (`Compensation.counts_against_free_bookings`, `Booking.uses_free_booking`) applies to room bookings. Item bookings are never free, but nothing enforces that yet: the customer item flow falls back to `compensations.first()`, which can be a no-rate compensation that counts against free bookings, and `get_legacy_consuming_bookings` in `services_quota_transition.py` does not filter out item bookings.

## Goals / Non-Goals

**Goals:**
- Let managers correct booking groups after the fact — add an item, cancel items/groups (including past ones), set a custom item price, and post a customer-visible comment with no email.
- Reuse existing services, forms, and helpers; keep creation/cancel logic in the service layer per the Hacksoft styleguide.
- Follow existing manager-view conventions (`@manager_required`, service-level manager checks, redirect back to the detail page).

**Non-Goals:**
- No data-model or migration changes.
- No changes to the customer booking flow or to room/parking-lot bookings, except that item compensation selection skips free-booking compensations.
- No editing of pickup/return dates on an existing group (add-item reuses the group's dates).
- No new email notifications.

## Decisions

- **Edit `total_amount` directly for custom prices.** The `Booking.total_amount` field already exists and the group total is a `Sum` of it, so a single number input per item is the least-code path. Alternative — a per-booking custom daily rate — would need a new field/model change for no functional gain here.

- **"Remove item" = cancel, reusing `manager_cancel_item_in_booking_group`.** Keeps the row for audit/history (auditlog is registered on `Booking`). A hard delete was considered but loses the record; cancel already exists and is what the manager list expects.

- **Add-item is a manager override.** A new `manager_add_item_to_booking_group` service derives the timespan/dates from an existing child booking (`bookings_of_bookinggroup.first()`), picks a compensation via `Resource.get_bookable_compensations(org)` excluding compensations that count against free bookings (prefer one with a `daily_rate`, else any remaining compensation on the resource), and creates the `Booking` with `is_item_booking=True` — mirroring `create_item_booking_group` but skipping availability and lending-day validation. `total_amount` uses the manager-supplied value, else `calculate_item_total(...)`. The `is_item_booking=True` flag keeps it out of the room-overlap exclusion constraint.

- **Item bookings never use free bookings.** Item bookings are never free, so they are kept out of the quota entirely: compensation selection for items (customer flow and manager add-item) excludes compensations with `counts_against_free_bookings=True`, item bookings always keep `uses_free_booking=False`, and the quota transition skips `is_item_booking=True` bookings. `get_free_bookings_used` needs no change, since it only counts `uses_free_booking=True`. Alternative — rejecting such compensations on item resources at model level — was not chosen because a compensation can be shared by room and item resources.

- **Comment bypasses `save_bookingmessage`.** A new `manager_add_booking_group_message` service creates the `BookingMessage` on the group's first booking and saves it directly, so `send_new_booking_message_email` is never enqueued. Messages are queried group-wide (`BookingMessage.objects.filter(booking__booking_group=group)`) and rendered on both the manager and customer group templates so the customer can see them.

- **Un-gate cancel in the template only.** Switch the cancel-action conditions from `is_cancelable` to `status != CANCELLED` (value `3`). The services already permit it, so no service change is needed for past-booking cancellation.

- **Plain POST + redirect for the new manager actions.** Add-item, price edit, and comment are simple correction actions; standard forms that redirect back to `manager-show-booking-group` with a `messages.success`/`error` are simpler and more robust than htmx partial swaps. The existing htmx item-cancel is retained.

## Risks / Trade-offs

- **Add-item requires a valid compensation** (FK is `PROTECT`, non-null). → Service falls back from bookable compensations to any compensation on the resource (both excluding free-booking compensations), and raises `ValidationError` with a clear message if none exists.
- **Group with no remaining bookings can't derive dates.** → Because remove = cancel (rows retained), `bookings_of_bookinggroup.first()` still returns a (cancelled) booking; the service raises `ValidationError` only in the degenerate empty-group case.
- **Item resource with only free-booking compensations.** → Customers and managers get the existing "No compensation available" error instead of a silently free booking; the manager fixes the resource's compensations in the admin.
- **Custom price is unvalidated free input.** → Acceptable: managers are trusted; the field is a standard `DecimalField(max_digits=8, decimal_places=2)` and normal form/decimal validation applies.
- **Comment visibility now spans the group.** → Querying by `booking__booking_group` shows all item messages together, which is the desired behaviour for a group-level comment thread.
