# 10. Bookings App

Date: 2024-06.23

## Status

Accepted

## Context

The project aims at making room bookings a lot easier. It needs to be developed with little ressources and quickly.
There is an existing booking process, that start with a wordpress form, a pdf, e-mail and a crm system and two spreadsheets.
It is mandatory, that users can - in the new system - perform these (booking related) actions:
- create a booking request for an organizations
- cancel a booking
- write a message for a specific booking
- create multiple bookings for recurring meetings at once

Resource administrators on the other hand mus be able to:
- confirm a booking request (or multiple bookings being part of the same recurrence)
- cancel a booking request (or multiple bookings being part of the same recurrence)

## Decision
We will handle all things closely related to a booking in the Booking App. This Booking app will specifically at least contain these models:
- _Booking_ (itself), which is the single most important Model of the whole application
- _RecurrenceRule_, which can be linked from one or multiple Bookings, if they are part of the same recurrence rule
- _BookingMessage_, which allows users to write Messages directly attached to one Booking


## Consequences
The Bookings app is at the very heart of the whole application.
Errors or integrity failures in the respective models and database tables might make the whole app useless and changes should be made very carefully.
