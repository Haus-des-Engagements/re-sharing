# 3. Batteries-Included Framework

Date: 2024-03-12

## Status

Accepted

## Context

We decided to use a Web-Framework in ARD 0002. Therefore, we had to decide which kind of framework should be used to
implement the storing of the data.
Web-Frameworks tend to fall into two camps: micro-frameworks and 'batteries-included' frameworks. Whereas the former
provides a ground to integrate with many other tools (like an ORM-Layer) the later provides the main stack itself.

At this point we already had the basic design prototype for the main application parts and knew the current
requirements:
* an user can create new bookable resources for an organization
* a user can book a (free) resource for its organization

## Decision

To reduce the development-time and not repeating generic functionality, we decided to go with the "batteries-included"
frameworks, that should fulfill the generic parts of our requirements.

## Consequences

* We need to decide which "batteries-included"-Framework we will use.
