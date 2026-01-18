# 0022. Lendable Items Feature

Date: 2026-01-16

## Status

Proposed

## Context

The application currently supports booking rooms and parking lots. Users have requested the ability to borrow equipment and items (e.g., projectors, tools, devices) through the same platform. These lendable items have different booking semantics than rooms:

- Items are priced per calendar day rather than per hour
- Multiple quantities of the same item can exist (e.g., 5 projectors)
- Items can be borrowed for multi-day periods
- Users may want to borrow multiple different items in a single transaction
- Items have specific pickup and return time windows (global settings)

We considered two approaches:
1. Create a new "lendables" app with separate models
2. Extend the existing Resource model with a new type

## Decision

We will extend the existing Resource model with a new `LENDABLE_ITEM` type and add item-specific fields:

### 1. Resource Model Changes

New fields:
- `quantity_available` (PositiveIntegerField, nullable) - number of items in stock
- New type choice: `LENDABLE_ITEM = "lendable_item", _("Lendable item")`

For lendable items:
- `access` field will be NULL (no access codes needed - pickup is in-person)
- Fields like `square_meters`, `max_persons` are not applicable (nullable)

### 2. Compensation Model Changes

New field:
- `daily_rate` (IntegerField, nullable) - price per calendar day (alongside existing `hourly_rate`)

Pricing calculation: Count distinct calendar days in the booking range. Example: Borrow Monday, return Wednesday = 3 days.

### 3. Booking Model Changes

New fields:
- `quantity` (PositiveIntegerField, default=1) - number of items booked
- `booking_group` (FK to BookingGroup, nullable) - groups items booked together
- `actual_pickup_time` (DateTimeField, nullable) - when items were actually picked up
- `actual_return_time` (DateTimeField, nullable) - when items were actually returned

The `timespan` field stores the full datetime range from pickup window start to return window end.

### 4. ExclusionConstraint Modification

The existing `exclude_overlapping_reservations` constraint will be modified to only apply to rooms and parking lots:

```python
ExclusionConstraint(
    name="exclude_overlapping_reservations",
    expressions=[
        ("timespan", RangeOperators.OVERLAPS),
        ("resource", RangeOperators.EQUAL),
    ],
    condition=Q(status=2) & ~Q(resource__type="lendable_item"),
)
```

For lendable items, availability is validated in the service layer using optimistic locking within a database transaction.

### 5. BookingGroup Model (New)

```python
class BookingGroup(TimeStampedModel):
    uuid = UUIDField(default=uuid.uuid4, editable=False)
    slug = AutoSlugField(populate_from="uuid", editable=False)
    organization = ForeignKey(Organization, on_delete=PROTECT)
    user = ForeignKey(User, on_delete=PROTECT)
    status = IntegerField(choices=BookingStatus.choices)
    invoice_number = CharField(max_length=160, blank=True)
    invoice_address = CharField(max_length=256, blank=True)
```

Fields:
- `organization`, `user`: Copied from the booking request (won't change)
- `status`: Group-level status (PENDING, CONFIRMED, CANCELLED)
- `invoice_number`, `invoice_address`: One invoice per BookingGroup
- `total_amount`: Calculated dynamically from child Bookings (not stored)

Behavior:
- Groups bookings of lendable items that were booked together
- For lendable items, a BookingGroup is always created (even for single items) for consistency
- NULL for room/parking lot bookings

**Status cascade logic:**
- Manager confirms BookingGroup → all child Bookings become CONFIRMED
- Manager cancels BookingGroup → all child Bookings become CANCELLED
- User cancels individual item → that Booking becomes CANCELLED, BookingGroup stays CONFIRMED
- User cancels entire group → BookingGroup and all children become CANCELLED
- If user cancels all items one by one, BookingGroup remains CONFIRMED (simple, no auto-cancel)

### 6. Lending Window Configuration (Global Settings)

Pickup and return windows are configured globally in Django settings:

```python
# Weekdays when pickup is available (0=Monday, 6=Sunday)
LENDING_DAYS = [0, 1, 2, 3, 4]  # Mon-Fri
LENDING_START_TIME = "10:00"
LENDING_END_TIME = "12:00"

# Weekdays when return is available
RETURN_DAYS = [0, 1, 2, 3, 4]  # Mon-Fri
RETURN_START_TIME = "14:00"
RETURN_END_TIME = "16:00"
```

### 7. ResourceRestriction Behavior

The existing `ResourceRestriction` model applies to lendable items with modified interpretation:
- For rooms: checks if booking timespan overlaps with restricted time periods
- For lendable items: checks if pickup or return DATE falls on a restricted day (time fields ignored)

When a restriction applies, that date cannot be selected for pickup or return.

### 8. Availability Calculation

Available quantity for a date range is calculated as:

```python
def get_available_quantity(resource, start_datetime, end_datetime):
    overlapping_bookings = Booking.objects.filter(
        resource=resource,
        status=BookingStatus.CONFIRMED,
        timespan__overlap=(start_datetime, end_datetime)
    )
    booked_quantity = overlapping_bookings.aggregate(
        total=Sum('quantity')
    )['total'] or 0
    return resource.quantity_available - booked_quantity
```

Race conditions are handled via optimistic locking: check availability, save in transaction, re-verify, raise error if exceeded.

### 9. Email Template Changes

Add `resource_type` field to email template model:

```python
resource_type = CharField(
    max_length=50,
    choices=Resource.ResourceTypeChoices.choices,
    null=True,
    blank=True,
    help_text="If set, template only used for this resource type. If NULL, used as fallback for all types."
)
```

Template selection priority:
1. Match email type + resource type
2. Fallback to email type + resource_type=NULL

For lendable items, template context includes `booking_group` with all associated bookings/items.

New email behavior:
- Pickup reminder sent before lending window (configurable timing)
- Confirmation/cancellation emails reference the BookingGroup, not individual bookings

### 10. New Booking Flow

Dedicated `/bookings/items/` page:

1. **Date selection**: User chooses pickup date and return date
   - Only dates matching `LENDING_DAYS` / `RETURN_DAYS` are selectable
   - Dates with active ResourceRestrictions are disabled

2. **Item selection**: List of all lendable items showing:
   - Item name and description
   - Total quantity and available quantity for selected dates
   - Quantity selector (0 to available)

3. **Dynamic calculation**: HTMX-powered updates showing:
   - Selected items and quantities
   - Number of days
   - Price per item (daily_rate × days × quantity)
   - Total price

4. **Preview page**: Review dates, items, quantities, and total cost

5. **Confirmation**: Creates BookingGroup + individual Booking per item type

No booking series support for items (single bookings only).

### 11. Navigation & Item Details

**Main Navigation:**
- New top-level menu entry "Borrow Equipment" (next to "Rooms")
- Links directly to `/bookings/items/` - the combined list and booking page

**Item Details Modal:**
- Each item in the list has a "More details" link/button
- Clicking opens a Bootstrap modal displaying:
  - Full description
  - Images (if available)
  - Conditions/requirements
  - Daily rate
- Modal does not interrupt the booking flow - user can close and continue selecting

### 12. Dashboard: My Equipment Loans

New section on the user dashboard (below existing bookings):

**Section heading:** "My Equipment Loans" (or similar)

**List view:**
- Shows upcoming and recent BookingGroups for the current user
- Each entry displays:
  - Pickup date and return date
  - Summary of items (e.g., "2 Projectors, 1 Laptop")
  - Status (Pending, Confirmed, Cancelled)
  - Total amount

**Detail view** (`/bookings/items/<booking_group_slug>/`):
- Shows the BookingGroup with all associated Booking records
- Similar layout to BookingSeries view, but:
  - No link to individual item booking pages (items are managed as a group)
  - Displays pickup/return times and actual pickup/return if set
- **Cancel options:**
  - Cancel individual items (reduces quantity or removes item from group)
  - Cancel entire BookingGroup (cancels all items at once)
  - Cancel buttons only shown if still cancelable (before pickup time)

### 13. Checkout/Check-in Workflow

Staff can track actual pickup and return:
- Mark items as picked up → sets `actual_pickup_time`
- Mark items as returned → sets `actual_return_time`

This is managed via Django admin or a future dedicated staff interface.

### 14. Cancellation

Same rules as room bookings: cancelable until the pickup time starts (`is_cancelable()` logic).

### 15. Permissions

Item booking uses the same permission system as rooms:
- Users need a confirmed `BookingPermission` for an Organization to book items
- `is_private` field works the same: private items can be restricted to certain OrganizationGroups
- Staff and managers have elevated permissions as with room bookings

### 16. Manager Views

Separate management interface for item bookings:

**List view** (`/manager/items/`):
- Shows pending BookingGroups awaiting confirmation
- Displays: pickup/return dates, user, organization, item summary, total amount
- Actions: Confirm group, Cancel group (group-level only)
- Filters: status, organization, date range

**Detail view** (`/manager/items/<slug>/`):
- Shows BookingGroup with all child Bookings
- Same interface as user detail view
- Additional action: Cancel individual items

### 17. URL Structure

**User-facing URLs:**
| URL | Method | Purpose |
|-----|--------|---------|
| `/bookings/items/` | GET | Create form (date + item selection) |
| `/bookings/items/preview/` | GET/POST | Preview and confirm booking |
| `/bookings/items/<slug>/` | GET | Detail view of BookingGroup |
| `/bookings/items/<slug>/cancel/` | PATCH | Cancel entire group |
| `/bookings/items/<slug>/cancel-item/<booking_id>/` | PATCH | Cancel single item |

**Manager URLs:**
| URL | Method | Purpose |
|-----|--------|---------|
| `/manager/items/` | GET | List pending BookingGroups |
| `/manager/items/<slug>/` | GET | Detail view |
| `/manager/items/<slug>/confirm/` | PATCH | Confirm group |
| `/manager/items/<slug>/cancel/` | PATCH | Cancel group |
| `/manager/items/<slug>/cancel-item/<booking_id>/` | PATCH | Cancel single item |

### 18. Validation Messages

| Scenario | Message |
|----------|---------|
| Quantity exceeds available | "Only {n} available for the selected dates" |
| Pickup date restricted | "Pickup not available on this date" |
| Return date restricted | "Return not available on this date" |
| No items selected | "Please select at least one item" |
| Pickup date not a lending day | "Pickup only available on {weekday list}" |
| Return before pickup | "Return date must be after pickup date" |
| Concurrent booking conflict | "Some items are no longer available. Please adjust your selection." |

---

This approach reuses:
- Existing permission system (OrganizationGroup, BookingPermission)
- Resource restriction system (with modified interpretation for items)
- Compensation/pricing infrastructure
- Booking confirmation workflow
- Email notification system (with resource_type extension)

## Consequences

**Positive:**
- Minimal code duplication - reuses existing infrastructure
- Consistent permission model across rooms and items
- Single admin interface for all resource types
- Existing reports and dashboards can be extended to include items
- Checkout/check-in provides accountability for item lending
- Email templates can be customized per resource type while sharing common templates

**Negative:**
- Resource model becomes more complex with nullable fields
- Two validation paths: DB constraint for rooms, service layer for items
- UI code paths diverge between room and item booking
- Global lending windows less flexible than per-item configuration

**Neutral:**
- Migration adds new columns to existing tables
- Tests need to cover both room and item booking scenarios
- Email template model gains new field
