## Context

The custom organization email page (`/organizations/custom-email/`) is a manager-only tool built from two function views (`custom_organization_email_view`, `send_custom_organization_email_view` in `re_sharing/organizations/views.py`), one selector (`get_filtered_organizations` in `re_sharing/organizations/selectors.py`), one django-tasks task (`send_custom_organization_email` in `re_sharing/organizations/mails.py`) and one template (`re_sharing/templates/organizations/custom_organization_email.html`).

Current state:

```
GET ?include_groups&exclude_groups&min_bookings&months&max_amount
  → view parses ints/floats
  → get_filtered_organizations(...)
      confirmed orgs
      if months: annotate booking_count / total_amount over CONFIRMED bookings
                 with timespan.start >= now - months*30d
      if months and min_bookings: filter booking_count >= min_bookings
      if months and max_amount:   filter total_amount  <= max_amount
  → table with per-org stats, hidden fields carry filters into the POST form
POST /custom-email/send/
  → view re-runs the selector, intersects with checked orgs
  → per org: task(org_id, subject, body, filter_context={"min_bookings", "months"})
      task re-fetches the org, so `hasattr(organization, "booking_count")` is always False
      → number_of_bookings via get_organization_booking_count(org, months)
      → total_amount never set
```

`months` is the linchpin: it gates the annotations, is carried as a hidden field, is a template tag in emails, and drives the per-org count in the task. Every one of these places changes.

Constraints: HackSoft style (reads in selectors, views thin), JSON-serialisable task arguments, `TIME_ZONE = "Europe/Berlin"` with `LANGUAGE_CODE = "de"`, >95% coverage, pre-commit (ruff, djlint) must pass.

## Goals / Non-Goals

**Goals:**
- Manager can bound the counted bookings by an explicit day range, open on either side, including future days.
- Manager can narrow the counted bookings to a set of rooms and parking lots.
- The preview table and the sent email always show the same numbers.
- `min_bookings` and `max_amount` work with or without a date range.

**Non-Goals:**
- Overlap-based counting, location filtering, lendable items, saved presets, changes to email delivery or access control.

## Decisions

### D1: Statistics are always annotated

`get_filtered_organizations` always annotates `booking_count` and `total_amount`. The date and resource criteria only shape the `Q` filter passed to `Count`/`Sum`. With no dates and no resources the filter is `status=CONFIRMED` alone, giving all-time statistics.

*Alternative considered*: keep the annotation conditional on a date range (today's behaviour). Rejected because it leaves `max_amount` and `min_bookings` silently dead and the preview table shows misleading zeros.

### D2: A single `Q` object built once and shared by count and sum

Build `booking_filter = Q(booking_of_organization__status=CONFIRMED)` and add `timespan__startswith__gte`, `timespan__startswith__lte` and `resource__in` conditions to it. Pass the same object to both `Count(..., filter=booking_filter)` and `Sum(..., filter=booking_filter)`. This guarantees count and amount are computed over the same set of bookings.

### D3: Day-to-datetime conversion happens in the selector, not the view

The selector accepts `from_date: date | None` and `to_date: date | None`. It converts `from_date` to `make_aware(datetime.combine(from_date, time.min))` and `to_date` to `make_aware(datetime.combine(to_date, time.max))` (Europe/Berlin), then compares the booking start with `>=` / `<=`. Views only parse strings to `date` objects (`date.fromisoformat`, matching the `<input type="date">` format).

*Alternative considered*: pass aware datetimes from the view (as `bookings/services.py` does). Rejected because the task also needs to call the selector from ISO date strings, and keeping the boundary rule in one place avoids two implementations drifting apart.

*Alternative considered*: `timespan__startswith__lt = next day 00:00`. Equivalent; `time.max` is chosen because it reads as "inclusive to-day" and mirrors the existing pattern in `bookings/services.py`.

### D4: Resource filter takes IDs and is type-guarded inside the selector

The selector accepts `resource_ids: list[int] | None`. When non-empty it resolves them to `Resource.objects.filter(id__in=resource_ids, type__in=[ROOM, PARKING_LOT])` and adds `booking_of_organization__resource__in=<that queryset>` to the shared `Q`. IDs of other types are dropped there, so the view, the task and any future caller get the same guarantee without repeating the check. If every submitted ID is dropped, the filter becomes an empty set and all counts are zero. This is intentional (the manager asked for resources that do not qualify) rather than silently widening to "all resources".

The view's template context provides the list of selectable resources via a small selector `get_custom_email_filterable_resources()` (rooms and parking lots ordered by type then name) so the template can render `<optgroup>` per type. The existing `include_groups` multi-select pattern is reused for markup and "selected" state.

### D5: One stats selector serves both the task and the preview

Add `get_organization_booking_stats(organization, from_date, to_date, resource_ids) -> dict` with keys `booking_count` and `total_amount`. Internally it reuses the same `Q` builder as `get_filtered_organizations` (factored into a private helper `_confirmed_booking_filter(from_date, to_date, resource_ids)`), then runs one aggregate on `organization.bookings_of_organization`. `get_organization_booking_count` is removed. The task calls this selector unconditionally whenever a `filter_context` is present and always sets `number_of_bookings` and `total_amount` in the email context. The dead `hasattr` branch is deleted.

### D6: Filter context is a flat JSON dict with ISO dates

`filter_context = {"min_bookings": int | None, "max_amount": float | None, "from_date": "YYYY-MM-DD" | None, "to_date": "YYYY-MM-DD" | None, "resource_ids": [int, ...]}`. Keys are always present (value `None` or `[]` when unset) so the task does not branch on key existence. The task parses ISO strings back with `date.fromisoformat` before calling the selector. The context is now always passed to the task (not only when `min_bookings` and `months` were both set), because the stats tags are always meaningful.

### D7: Email template tags for dates are pre-formatted strings

The task puts `from_date` and `to_date` into the render context as strings produced by `django.utils.formats.date_format(value, "SHORT_DATE_FORMAT")` (with `LANGUAGE_CODE = "de"` this yields `01.01.2026`), or an empty string when the bound is open. Emails render with `Context(..., autoescape=False)` and plain `Template`, so pre-formatting is simpler and safer than relying on filters inside manager-typed templates. `{{ months }}` is removed from the context and from the help text.

### D8: Views validate the range and never touch the ORM directly

Both views parse `from_date`, `to_date` (ISO strings → `date`, invalid → treated as validation error), `resources` (`getlist`, ints), `min_bookings` (`is not None` semantics, `0` is a value), `max_amount`. Parsing lives in a small private helper in `views.py` returning a dataclass-like dict shared by GET and POST so the two views cannot drift. If `from_date > to_date` or a date fails to parse, the GET view renders the page with a `messages.error` and no result list; the POST view redirects back with the same error. The GET view calls the selector whenever any filter is present (groups, dates, resources, min_bookings, max_amount), matching today's "empty form shows nothing" behaviour.

## Risks / Trade-offs

- [Existing tests reference `months` in 23 selector tests plus view and mail tests] → migrate them mechanically to `from_date`/`to_date` computed from `timezone.localdate()`; keep the assertions, add boundary and resource cases.
- [`timezone.now()`-based test fixtures near midnight Berlin time can straddle a day boundary] → build fixtures from explicit dates (`datetime.combine(date, time(10))` made aware) instead of `now()`.
- [All-time stats query over every confirmed booking per organization] → the query is one aggregated `JOIN` with the existing GiST index on `timespan`; the page is a manager tool with low traffic. No new index needed. Revisit if the preview becomes slow.
- [Old bookmarked URLs with `months=`] → parameter is ignored; the manager sees all-time stats and can set dates. Acceptable for an internal manager page.
- [`max_amount` over future ranges relies on `total_amount` being set at confirmation] → confirmed by the product owner; no additional handling.
- [Dropping non-qualifying resource IDs can yield an all-zero preview] → help text explains that only rooms and parking lots are counted; the UI never offers other types.

## Migration Plan

No database migration. Deploy as a normal release. Rollback is a code revert.

## Open Questions

None. All product decisions (all-time default, start-within-range rule, formatted date tags, fixing `total_amount`) were confirmed before this proposal.
