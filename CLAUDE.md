# Claude Development Guidelines

This file contains specific development guidelines and rules for working with this Django project.

## Code Quality and Standards

### Pre-commit Configuration
- **Always respect the `.pre-commit-config.yaml` configuration**
- All code changes must pass pre-commit checks before committing
- **Commit only when asked.** Never auto-commit — report what changed and wait
  for an explicit "commit" / "commit and push".
- **Ship on `main`** , no feature branch / PR. The direct-to-main approval prompt is expected — surface it and
  proceed once confirmed.
- **Commit messages:** no `Co-Authored-By` trailer; no real-world names
  (networks, cities, companies) in messages or comments — keep it generic.

### Test Coverage Requirements
- **Aim for high test coverage (>95%)**
- Current coverage is 95% - maintain or improve this level
- Focus on testing business logic and self-written code
- Use existing patterns: Django TestCase, Factory classes, pytest fixtures
- Test critical paths: permissions, booking logic, user authentication
- Add tests for new functionality before implementation when possible

## Development Practices

### Code Organization
- Follow Django project structure and conventions
- Use existing factories for test data creation
- Maintain consistency with current naming conventions
- Group related functionality in appropriate Django apps
- try to follow the hacksoft djangostylguide: https://github.com/HackSoftware/Django-Styleguide

### Testing Guidelines
- Write comprehensive tests for models, services, and views
- Use meaningful test method names that describe the scenario
- Set up proper test data using factories
- Test both success and failure scenarios
- Mock external dependencies appropriately
- Combine duplicate test classes when found

## Project-Specific Rules

### ADR
- read the "Architecure Decision Records" to understand past decision.
- add an ADR if you think one is necessary

### Django Applications
- `bookings/` - Core booking functionality and business logic
- `organizations/` - Organization and permission management
- `resources/` - Resource and location management
- `users/` - User management and authentication
- `providers/` - Manager and provider functionality

### Key Models and Relationships
- User ↔ Organization (via BookingPermission)
- Organization ↔ Resource (via OrganizationGroup)
- Booking relationships with User, Organization, Resource
- Manager permissions and resource access

### Testing Commands
- Run tests: `export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest`
- Coverage report: `export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest --cov=re_sharing --cov-report=html`
- Specific test: `export DJANGO_READ_DOT_ENV_FILE=true && python -m pytest path/to/test.py::TestClass::test_method`

---
*This file should be updated as the project evolves and new patterns emerge.*
