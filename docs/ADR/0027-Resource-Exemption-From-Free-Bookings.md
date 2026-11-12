# 27. Resource exemption from free bookings

Date: 2026-11-11

## Status

Accepted

Extends [23. Free bookings quota](0023-Free-Bookings-Quota.md)

## Context

Whether a booking uses one of an organization's free bookings per year was decided only by its compensation (`counts_against_free_bookings`). Some resources should never count, whatever compensation is chosen. Compensations are shared between resources and tied to organization groups, so taking one resource out of the quota meant splitting every free compensation that covers it, and a resource added to a flagged compensation later counted without anyone deciding so.

## Decision

A resource gets a boolean `exempt_from_free_bookings`, default false, editable in the admin.

A booking uses a free booking only when its compensation counts against free bookings and its resource is not exempt. This rule lives in one place, `consumes_free_booking(compensation, resource)` in `bookings/services_pricing.py`, and every step that prices or checks a booking uses it.

- On an exempt resource a flagged compensation behaves like an unflagged one: the booking is free, is not marked as using a free booking and is possible however many free bookings are left. The booking form shows no remaining count and a series needs no paid fallback.
- The quota transition skips bookings and series on exempt resources. They take no place in the allocation of the allowance, and their series stay unmarked.
- Changing the switch affects only bookings priced afterwards. Bookings already marked as using a free booking keep the mark and still count as used.

We chose an exception flag on the resource over a second "counts" flag, because the default then keeps the previous behaviour without a data migration and the two flags cannot be confused.

## Consequences

- One switch takes a resource out of the quota for every organization and compensation.
- Nothing changes on deployment; every resource starts as not exempt.
- When a resource becomes exempt, free bookings already used on it stay used. Staff can clear the mark on single bookings in the admin.
- When an exemption is removed, bookings and series made earlier on that resource keep their pricing until the transition command is run again; it is idempotent.
- The switch is not part of the manager's resource form.
