# 18. Permission Model Architecture

Date: 2025-01-20

## Status

Accepted

## Context

The booking platform has complex authorization requirements that go beyond Django's default permission system. The system is organization-centric rather than individual-user-centric, with multiple layers of access control:

1. **Organization-level permissions**: Users need different roles within organizations (admin vs. booker)
2. **Resource-level permissions**: Some resources are public, others are private and restricted to specific organization groups
3. **Staff/Manager permissions**: Staff users need to manage resources, access codes, and organizations
4. **Permission workflows**: Users request access to organizations, which must be approved

Django's built-in permissions system provides:
* Object-level permissions are not built-in
* Group-based permissions are user-centric, not organization-centric
* No workflow support for permission requests/approvals
* Limited role differentiation beyond boolean flags

We considered these approaches:
1. Django's built-in User groups and permissions
2. django-guardian for object-level permissions
3. Custom permission models tailored to our domain
4. Role-based access control (RBAC) library like django-role-permissions

Key requirements:
* Users belong to multiple organizations with different roles in each
* Organizations can have admin users (full control) and booker users (limited)
* Permission requests must be tracked (pending/confirmed/rejected states)
* Staff users (Managers) need granular control over resources and organizations
* Resources can be restricted to specific organization groups
* Permission checks need to be efficient (avoid N+1 queries)

## Decision

We will implement a custom multi-layered permission architecture with the following models:

### 1. BookingPermission Model
A junction table between User and Organization with:
* **Role field**: ADMIN (role=1) or BOOKER (role=2)
* **Status field**: PENDING (0), CONFIRMED (1), or REJECTED (2)
* Audit logging via django-auditlog
* Unique constraint on (user, organization, role)

Admin users can:
* Manage organization settings
* Approve/reject booking permission requests
* Promote/demote other users
* Cancel bookings
* View all organization bookings

Booker users can:
* Create booking requests for the organization
* View organization's bookings
* Cancel their own bookings

### 2. Manager Model (Staff Access)
A one-to-one relationship with User for staff members:
* Optional restriction to specific organization groups
* Optional restriction to specific resources
* Access to manage access codes
* Can view and manage bookings across their assigned scope

### 3. OrganizationGroup Model
Groups organizations together for permission inheritance:
* **bookable_private_resources**: Resources that group members can book
* **auto_confirmed_resources**: Resources that bypass approval workflow
* **default_group**: Flag for automatic membership
* Enables bulk permission management

### Permission Check Pattern
Service layer functions validate permissions before operations:
* `user.get_organizations_of_user()` - organizations where user has confirmed permission
* `user.get_resources()` - resources accessible to user (public + organization group resources)
* `is_bookable_by_organization(resource, organization)` - checks resource restrictions
* Manager access checked via `user.is_manager()` and scope validation

## Consequences

* Custom permission logic must be maintained and tested thoroughly
* Permission checks are explicit in service layer rather than view decorators
* Database queries require careful optimization (select_related/prefetch_related)
* Permission request workflow adds complexity but provides audit trail
* Organization admins have significant control, requiring careful initial setup
* Managers provide a parallel permission hierarchy for staff access
* OrganizationGroup abstraction enables efficient bulk permission management
* The multi-layered approach is more complex than Django's built-in permissions
* Permission changes are audit-logged, providing accountability
* Adding new permission types requires model changes and migrations
* The system is specific to our domain and not reusable across projects
* Testing must cover all permission scenarios and edge cases
* Performance depends on efficient queryset construction in permission checks
* Documentation and training needed for admin users managing permissions
* The BookingPermission model serves as both permissions and membership tracking
* Role-based access is simpler than attribute-based access control (ABAC) but less flexible
* Migration to a different permission system would require significant refactoring
