# 13. Auditlog

Date: 2024-08-20

## Status

Accepted

## Context

In this project, changes made to an object (e.g. a booking as been approved) are important to the user and the admins to see what has actually happened (who? what? when?).

## Decision

We will use the library _django-auditlog_ (https://github.com/jazzband/django-auditlog) to log the changes made to an object.

## Consequences

- we add another dependency
- we need to rely on the project to work as expected, as the auditlog is of (great) importance to th end-user and also admin-user
- we don't create our own model-logging-models
- a removal of the library would mean (some) reorganization of the code and some migrations, that we currently judge to be feasible but time-consuming
