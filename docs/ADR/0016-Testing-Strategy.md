# 16. Testing Strategy

Date: 2025-10-20

## Status

Accepted

## Context

Testing is critical for maintaining code quality and preventing regressions in a booking system where data integrity is paramount. Django provides its own test framework based on unittest, but the Python ecosystem offers alternative testing tools with different philosophies and capabilities.

The project has specific requirements:
* High test coverage target (>95%) to ensure reliability
* Need for realistic test data generation (users, bookings, organizations, resources)
* Complex business logic in service layer that requires thorough testing
* Time-dependent functionality (bookings, reminders, recurring events) requiring time manipulation
* Database-heavy operations requiring efficient test database management

We considered the following options:
1. Django's built-in unittest-based TestCase (default approach)
2. pytest with pytest-django plugin
3. Hybrid approach using both frameworks

Key considerations:
* Test readability and maintainability
* Fixture management and test data creation
* Test discovery and execution speed
* Integration with coverage reporting
* Developer experience and learning curve

## Decision

We will use pytest as our primary testing framework with the following stack:
* **pytest** with **pytest-django** for Django integration
* **factory_boy** for test data generation using factory classes
* **pytest-cov** for coverage reporting with a target of >95%
* **freezegun** for time manipulation in time-sensitive tests
* **Faker** for generating realistic random data
* **pytest-sugar** for enhanced test output readability

We will maintain the >95% test coverage requirement and focus testing efforts on:
* Business logic in services.py files (the "heart" of the application)
* Model methods and custom behavior
* Permission and authorization logic
* View integration tests where necessary

Test organization:
* Tests in `/tests/` subdirectory within each Django app
* Factory classes in `tests/factories.py`
* Mix of pytest fixtures and Django TestCase where appropriate
* Parametrized tests for testing multiple scenarios efficiently

## Consequences

* Developers need to learn pytest conventions and fixtures (beyond Django's TestCase)
* Test files use `pytest.mark.django_db` decorator for database access
* Factory classes provide consistent, reusable test data creation across all tests
* Time-dependent tests can freeze time for deterministic results
* Coverage reporting is integrated into the test workflow with HTML reports
* The service layer receives heavy testing focus, ensuring business logic reliability
* Test execution is generally faster than Django's default test runner
* Parametrized tests reduce code duplication for similar test scenarios
* pytest's assertion introspection provides better error messages than unittest
* The project depends on pytest ecosystem packages that must be maintained
* Some Django-specific test utilities may require pytest-django adaptations
* Mixing pytest and Django TestCase is possible but should be minimized for consistency
