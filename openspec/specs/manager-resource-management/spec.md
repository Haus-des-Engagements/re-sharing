# manager-resource-management Specification

## Purpose
TBD - created by archiving change add-manager-create-resource. Update Purpose after archive.
## Requirements
### Requirement: Manager entry point to create a resource

The manager resource list page (`/resources/manager/`) SHALL present a "New Resource" action in the page heading that links to the resource creation view, consistent with the "New Organization" action on the manage-organizations page.

#### Scenario: Button shown in heading

- **WHEN** a manager opens `/resources/manager/`
- **THEN** the page heading includes a "New Resource" button linking to the `resources:manager-create-resource` URL

### Requirement: Manager can create a resource

The system SHALL provide a manager-only view at `manager/new/` that lets a manager create a new `Resource`. The creation route MUST be resolved before the `manager/<slug:resource_slug>/` detail route so that `new` is not interpreted as a resource slug.

#### Scenario: Render blank creation form

- **WHEN** a manager sends a GET request to `resources:manager-create-resource`
- **THEN** the system responds with 200 and renders a blank resource form

#### Scenario: Create resource with valid data

- **WHEN** a manager submits the creation form with valid data via POST
- **THEN** a new `Resource` is created with a slug auto-generated from its name
- **AND** the manager is redirected to that resource's manager detail page (`resources:manager-show-resource`)

#### Scenario: Reject invalid submission

- **WHEN** a manager submits the creation form with invalid data via POST
- **THEN** no `Resource` is created
- **AND** the form is re-rendered with validation errors

### Requirement: Resource creation is restricted to managers

The resource creation view SHALL be protected by the manager authorization decorator and SHALL only accept GET and POST methods.

#### Scenario: Non-manager is denied

- **WHEN** a user who is not a manager requests `resources:manager-create-resource`
- **THEN** access is denied by the manager authorization decorator and no resource is created
