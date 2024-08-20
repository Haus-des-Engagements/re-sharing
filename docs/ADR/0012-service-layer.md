# 12. Service Layer

Date: 2024-08-20

## Status

Accepted

## Context

In Django, the standard way (that you find in tutorials and books) is to put business logic (meaning the code, that as specific to your application) into the views and to test the views.
In most cases though, you will hand some parts of the request over to a specific function and then build the response with the result of the function.

## Decision

The business logic mainly resides in _services.py_ or (when only concerning a single model) in the _models.py_ in each app.
The views (views.py) should be very minimal and mainly handle requests, invoke a service and return a response.

## Consequences
- the views should be very simple and short
- the services (and models) contain all the business logic and become therefor the "heart" of the whole application
- forms will still be handled in views, as otherwise we won't be able to profit from the django-inbuilt form-handling
- services need to be tested heavily
- the services file can get quite big, as it might contain a lot of functionality
- the principle of "locality of behaviour" is not applied here, as the code is even dispersed into more files (templates, urls, views, models, services, forms, admin)
