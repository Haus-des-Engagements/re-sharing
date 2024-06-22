# 9. High-level Apps Architecture

Date: 2024-06-22

## Status

Accepted

## Context

The modelling and separation of the code into multiple app is an important way to structure the project and keep it maintainable.

## Decision

The app structure reflects the organization of code. Inside one app, the code can be intertwining. But there should only be minimal relations and code-sharing between apps. 
We decided to create four basic apps with corresponding models to start with.

In the best case, one App has only one (!) relation to another app 
(of course the Model have the relations, but there should only one important relation from all models within an app to the models of another app).
* Bookings: the main model, handling Bookings itself. And auxiliary models, handling message for bookings and recurrence.
* Organizations: as only organizations are allowed to book, organizations handels booking permissions for organizations and their users.
* Rooms: the central unit, that can be booked. Rooms have access codes.
* User: Only contains the barbone User model and the registration user profile actions.

## Consequences

* We orientate our DB scheme to the four basic apps. Other apps might fit in or around the four basic apps.
* It is relatively easy to restructure the three basic apps within the corresponding Django app border, if it does not concern the app model
or a model with a connection going outside the Django app border.
* It is possible later on but associated with significant effort to change the connections between the basic apps.
