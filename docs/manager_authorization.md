# Manager Authorization Implementation

This document outlines the changes needed to implement proper authorization for managers in the re-sharing application. The goal is to ensure that managers can only view, update, and delete organizations that are part of the organization_groups they are assigned to.

## Completed Changes

### 1. Custom Authorization Decorator

Created a custom decorator `manager_required` in `re_sharing/providers/decorators.py` that:
- Checks if the user is authenticated
- Checks if the user is a manager
- Denies access if the user is not a manager

```python
def manager_required(view_func):
    """
    Decorator for views that checks that the user is a manager.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request: HttpRequest, *args, **kwargs):
        if not request.user.is_manager():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view
```

### 2. Modified Organization Filtering

Updated the `manager_filter_organizations_list` function in `re_sharing/organizations/services.py` to:
- Take a manager parameter
- Filter organizations based on the manager's assigned organization_groups
- Return all organizations if the manager has no assigned organization_groups

```python
def manager_filter_organizations_list(status, group, manager=None):
    """
    Filter organizations based on status, group, and manager.
    If manager is provided and has organization_groups assigned, only organizations
    that are part of those groups will be returned.
    """
    organizations = Organization.objects.all()
    
    # Filter by manager's organization groups if manager is provided and has organization groups
    if manager and manager.organization_groups.exists():
        organizations = organizations.filter(
            organization_groups__in=manager.organization_groups.all()
        ).distinct()
    
    # ... rest of the function ...
```

### 3. Updated Manager List Organizations View

Updated the `manager_list_organizations_view` in `re_sharing/organizations/views.py` to:
- Use the new `manager_required` decorator instead of `@staff_member_required`
- Get the manager object for the current user
- Pass the manager to the `manager_filter_organizations_list` function
- Filter the available organization groups to only include those that the manager has access to

```python
@require_http_methods(["GET"])
@manager_required
def manager_list_organizations_view(request: HttpRequest) -> HttpResponse:
    """
    Shows the organizations for a manager so that they can be confirmed or cancelled.
    Only shows organizations that are part of the organization_groups that the manager is assigned to.
    """
    status = request.GET.get("status") or "all"
    group = request.GET.get("group") or "all"
    
    # Get the manager object for the current user
    manager = request.user.get_manager()
    
    # Filter organizations based on the manager's assigned organization_groups
    organizations = manager_filter_organizations_list(status, group, manager)
    
    # Get only the organization groups that the manager has access to
    available_groups = OrganizationGroup.objects.all()
    if manager and manager.organization_groups.exists():
        available_groups = manager.organization_groups.all()

    context = {
        "organizations": organizations,
        "statuses": Organization.Status.choices,
        "groups": available_groups,
    }
    
    # ... rest of the function ...
```

## Pending Changes

The following changes are needed to complete the implementation of manager authorization for all manager-related views:

### 1. Update Manager Cancel Organization Service

The `manager_cancel_organization` function in `re_sharing/organizations/services.py` needs to be modified to:
- Take a manager parameter or get the manager from the user
- Check if the manager has permission to manage the organization using the `can_manage_organization` method
- Only proceed with the operation if the manager has permission

```python
def manager_cancel_organization(user, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)
    
    # Get the manager object
    manager = user.get_manager()
    
    # Check if the manager has permission to manage this organization
    if manager and not manager.can_manage_organization(organization):
        raise PermissionDenied
    
    if organization.is_cancelable():
        with set_actor(user):
            organization.status = BookingStatus.CANCELLED
            organization.save()
        from re_sharing.organizations.mails import organization_cancellation_email
        
        organization_cancellation_email(organization)
        return organization
    
    raise InvalidOrganizationOperationError
```

### 2. Update Manager Confirm Organization Service

The `manager_confirm_organization` function in `re_sharing/organizations/services.py` needs similar modifications:

```python
def manager_confirm_organization(user, organization_slug):
    organization = get_object_or_404(Organization, slug=organization_slug)
    
    # Get the manager object
    manager = user.get_manager()
    
    # Check if the manager has permission to manage this organization
    if manager and not manager.can_manage_organization(organization):
        raise PermissionDenied
    
    if organization.is_confirmable():
        with set_actor(user):
            organization.status = BookingStatus.CONFIRMED
            organization.save()
        from re_sharing.organizations.mails import organization_confirmation_email
        
        organization_confirmation_email(organization)
        return organization
    
    raise InvalidOrganizationOperationError
```

### 3. Update Manager Cancel Organization View

The `manager_cancel_organization_view` in `re_sharing/organizations/views.py` needs to be updated to:
- Use the new `manager_required` decorator instead of `@staff_member_required`

```python
@require_http_methods(["PATCH"])
@manager_required
def manager_cancel_organization_view(request, organization_slug):
    organization = manager_cancel_organization(request.user, organization_slug)
    
    return render(
        request,
        "organizations/partials/manager_organization_item.html",
        {"organization": organization},
    )
```

### 4. Update Manager Confirm Organization View

The `manager_confirm_organization_view` in `re_sharing/organizations/views.py` needs similar modifications:

```python
@require_http_methods(["PATCH"])
@manager_required
def manager_confirm_organization_view(request, organization_slug):
    organization = manager_confirm_organization(request.user, organization_slug)
    return render(
        request,
        "organizations/partials/manager_organization_item.html",
        {"organization": organization},
    )
```

## Testing

Comprehensive tests have been created in `re_sharing/organizations/tests/test_manager_views.py` to verify that:
1. Regular users cannot access the manager list view
2. Managers can access the manager list view
3. Managers only see organizations from their assigned organization groups
4. Managers only see their assigned organization groups in the filter dropdown
5. Managers with no assigned organization groups see all organizations and all groups

Similar tests should be created for the other manager-related views once they are updated.
