# 2. CRUD-Framework

Date: 2024-03-12

## Status

Accepted

## Context

"Haus des Engagements" has currently to administer 7 resources, each one with several bookings a day. This is a very time
and energy consuming activity, especially because the process is half-manual.
To facilitate the process for both the resource provider (currently only "Haus des Engagements") and the clients, the 
process should be fully digital with more automation and less manual work.

We could easily use existing software but our use-case deviates in three aspects from all the booking software, that 
we know of:
1. The pricing: for non-profits, our resources are for free. However, if they wish, they can pay for it (that happens e.g.
when they have funding and need to spend it). For-profits have to pay for the resources, but they can choose between
different prices depending on what they can pay.
2. We plan to open the platform for other hosts / resource providers. The whole software then rather becomes a platform or
a marketplace.
3. Organization-orientation: usually, the bookings are for organizations, not for individuals. Of course, we need to have
individual user-accounts, but bookings are always in the name of organizations.

We considered the following __options__:
1. Use simple wordpress-booking-plugin (as we do it in our "Materialverleih")
2. Use an existing booking-plattform.
3. Use an existing standalone software.

All three options have severe drawbacks, especially looking at the three aspects shown above.

## Decision

We will build our own, specialised software. We will adjust it to our requirements in the first place but keep in mind
that others might want to use it as well for their resources. We will surley not build the software from scratch but use 
sone existing Web-Framework.

## Consequences

* We need to decide which Web-Framework will be used.
* We will focus on the needs of the "Haus des Engagements" first and provide a good bookings process for their use-case.
* The database is generated and managed by the Web-Frameworks. We should not need to write custom SQL.
* The Web-Frameworks is the application layer around the database. The data is the heart of the project and the Web-
framework the brain. Switching to another approach (or framework) will be time-consuming.
* The data written in the database by the framework shouldn't be framework-specific. So replacing the application layer
around the existing database will always be possible.
