# 14. Recurring Bookings

Date: 2024-09-13

## Status

Accepted

## Context

Recurring Bookings are a central requirement for this application, as many organizations use the resources on a regular basis.
There are multiple ways of implementing Recurrences, see discussions about it here:
- https://github.com/bmoeskau/Extensible/blob/master/recurrence-overview.md
- https://stackoverflow.com/questions/85699/whats-the-best-way-to-model-recurring-events-in-a-calendar-application
- http://martinfowler.com/apsupp/recurring.pdf

## Decision

- We will implement Recurrences by iCalender RFC 5545 (https://tools.ietf.org/html/rfc5545)
- We will not implement it fully, as we only need a subset of options.
- We will make use of the library _dateutils_ and its rrule  ccapabilities (https://dateutil.readthedocs.io/en/stable/rrule.html)
- As our main model is a Booking, we will create all instances of recurring bookings that fall within the allowed future booking timeframe. Bookings that extend beyond this timeframe will be generated daily.

## Consequences

- we add another dependency
- we trade consistency for abstraction by instantiating all bookings (in the allowed future timeframe) instead of creating them on the fly.
- Bookings stay our source of truth
- we need to add a routine to create new occurrences automatically before the allowed future timeframe moves on
