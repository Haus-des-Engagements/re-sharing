# 21. Providers App - Staff Management System

Date: 2025-10-20

## Status

Accepted

## Context

The booking platform requires two distinct permission models:
1. **Organization-level permissions**: Regular users belong to organizations with roles (admin/booker)
2. **Staff-level permissions**: Administrative staff need to manage resources, organizations, and access codes across the platform

Initially, Django's built-in `is_staff` flag was used for administrative access, but this provided all-or-nothing permissions. As the platform evolved, we needed more granular staff permissions:
* Some staff members manage specific resources or locations only
* Some staff approve organizations for specific organization groups
* Some staff need access to view/manage access codes for their resources
* Staff permissions are fundamentally different from organization membership permissions

The challenge was where to implement this functionality:
1. Extend the `organizations` app with staff-specific models
2. Extend the `resources` app with manager relationships
3. Create a dedicated app for staff/manager functionality
4. Use Django admin groups and permissions

Key requirements:
* Staff can be scoped to specific resources (location-based management)
* Staff can be scoped to specific organization groups (regional approval workflows)
* Staff need different permissions than regular organization admins
* The system should support future expansion (auditors, analysts, etc.)
* Clear separation between "who belongs to what organization" vs. "who manages what"

## Decision

We will create a dedicated **providers** app with a **Manager** model representing staff users with administrative permissions.

### Naming Convention
The app is named "providers" to represent staff who **provide management services** to the platform, not to be confused with organizations that provide bookable resources. This naming emphasizes the service-provider role of administrative staff.

### Manager Model Structure
A `Manager` model with:
* **One-to-one relationship** with User (extends user with manager capabilities)
* **Many-to-many to Resource**: Managers are assigned specific resources they oversee
* **Many-to-many to OrganizationGroup**: Managers can be scoped to organization groups
* **Scoping logic**:
  - If `organization_groups` is empty → manager can access ALL organizations (unrestricted)
  - If `organization_groups` is set → manager only accesses organizations in those groups
  - Managers must be assigned to resources to manage bookings for those resources

### Permission Methods
The Manager model provides these permission checks:
* `can_manage_organization(org)` - Validates organization group access
* `can_manage_booking(booking)` - Requires BOTH organization AND resource access
* `get_accessible_access_codes()` - Returns access codes for manager's resources

### Authorization Layer
* Custom decorators: `@manager_required` for function views, `ManagerRequiredMixin` for class-based views
* User model extension: `is_manager()` and `get_manager()` methods
* View-level permission enforcement (no views in providers app itself)

### Integration Pattern
Manager functionality integrates across apps:
* **Organizations app**: Manager views for approving/rejecting organizations
* **Bookings app**: Manager access to view/manage bookings within their scope
* **Resources app**: Manager CRUD operations for AccessCode objects

### Dual Permission Model Philosophy
This creates a two-tier permission architecture:
1. **BookingPermission** (organization membership) - handled in organizations app
2. **Manager** (staff administrative access) - handled in providers app

These are intentionally separate concerns with different scoping mechanisms.

## Consequences

* The providers app contains only the Manager model, no views (views distributed across other apps)
* Managers have a fundamentally different permission model than organization admins
* Staff access is granted by creating a Manager record and assigning resources/groups
* The "providers" naming may be initially confusing (staff management vs. resource providers)
* Permission checks require understanding both BookingPermission AND Manager models
* A manager without assigned resources can view organizations but not manage bookings
* The dual permission model adds complexity but provides clear separation of concerns
* Manager permissions can evolve independently from organization permissions
* Scoping logic (empty groups = unrestricted) must be carefully documented
* Testing requires scenarios covering both permission models
* The app follows ADR #9 pattern: minimal cross-app dependencies, clear domain boundaries
* Future expansion could include other "provider" roles (auditors, analysts, report viewers)
* Migration from `@staff_member_required` to `@manager_required` provides better access control
* Admin interface uses `filter_horizontal` for easy many-to-many selection
* The Manager model is audit-logged via django-auditlog for accountability
* Access code management is inherently scoped by manager's assigned resources
* Booking management requires dual validation (organization access + resource access)
* The separation enables different permission evolution paths for staff vs. users
* Documentation must clearly explain when to use BookingPermission vs. Manager
* The app name "providers" is maintained for consistency despite potential confusion
