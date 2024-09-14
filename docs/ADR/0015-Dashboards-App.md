# 14. Dashboards App

Date: 2024-09-14

## Status

Accepted

## Context

To give the users some orientation in the interface, we wanted to provide some kind of (simple) dashboard.
We weren't sure in which app swe should put the code, as it already shows information coming from two different, but important models from different apps (Organization & Booking).

## Decision

- We create a new app, called "Dashboards".
- This app will contain this dashboard but also others, that might be coming (e.g. for managing rooms)


## Consequences

- we have another app, that should have no models itself
- we don't litter the data-centric other apps with displaying only code
- we might regret not having followed the YAGNI (you ain't gonna need it), as we don't know yet for sure, if we will ever build other dashboards.
