# 20. Urls and Naming

Date: 2024-06-03

## Status

Accepted

## Context

Urls, Views and Models - the three basic concepts in Django - need to be named in each case.

## Decision

* Apps are named by the main model in plural, all in lowercase. E.g. "rooms".
* Model are named in singular, with CamelCase. E.g. "BookingMessage".
  * Variable names for backward resolution:
    * Used for finding all occurrences of a referenced attribute as a foreign key: https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ForeignKey.related_name
    * Both corresponding variables should be set.
    * 'related_name': 'current class in plural' + '_of_' + 'foreign key class', e.g. 'boookingmessages_of_booking' is the related_name of Booking in BookingMessage class.
    * 'related_query_name': Like 'related_name', but the current class is written in singular.
* Standard Url and View naming
  * base url for an app just like the app name. E.g.: "rooms/"
  * htmx-patterns should be listed separately int the url file.
  * view name: action_model(if multiple, then plural)_view, e.g.: show_booking_view
  * name: action-model(if multiple, then plural), e.g.: show-booking
  * examples:
    * Detail: path("<slug:slug>", show_booking_view, name="show-booking")
    * List: path("", list_bookings_view, name="list-bookings"). 
* Functions are named in snake_case. E.G. "get_bookingmessage"

## Consequences

Alle new Urls should be named according to the above-mentioned patterns. That would currently lead to these Urls (not all of them are already implemented):
* rooms: 
  * rooms/ (list of all rooms)
  * rooms/slug (detail of one room)
  * rooms/new-room (create a new room)
* bookings:
  * bookings/ (list of bookings of my organizations)
  * bookings/filter-bookings (filter list of bookings)
  * bookings/create-booking (create new booking)
  * bookings/slug (show one of my bookings)
  * bookings/slug/write-bookingmessage (write BookingMessage for a Booking)
  * bookings/slug/cancel-booking (cancel Booking)
* organizations
  * organizations/ (list of my organizations)
  * organizations/all (list of all organizations)
  * organizations/create-organization (create new organization)
  * organizations/slug/join-organization (join an organization)
  * organizations/slug/leave-organization (leave an organization)


