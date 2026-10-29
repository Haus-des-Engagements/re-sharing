## MODIFIED Requirements

### Requirement: Existing agreements entered in the admin

Staff SHALL be able to create an active agreement with its mandate in the admin for an organization that already holds the kind's group, without triggering the approval side effects. Staff SHALL also be able to import agreements from a spreadsheet in the admin, with organization id, kind slug, status, amounts, dates, function, details and notes but without signed documents; rows SHALL be validated like the admin form including the unique constraints, the import SHALL only be offered after a preview without errors, and it SHALL trigger no emails, groups, codes or collections. The admin SHALL offer an export of agreements in the same format, including the organization's name. Managers SHALL be able to create agreements in the frontend as described in `manager-agreement-management`.

#### Scenario: Existing member entered

- **WHEN** staff create an active membership agreement with a paper mandate reference for an organization that is already in the member group
- **THEN** the agreement and mandate exist, no email is sent, and the organization's groups and codes are unchanged

#### Scenario: Members imported from a spreadsheet

- **WHEN** staff import rows of active memberships
- **THEN** the agreements exist with status `Active`, no email is sent, no collections exist, and the organizations' groups are unchanged

#### Scenario: Duplicate in the spreadsheet

- **WHEN** two rows describe an open agreement of the same kind for the same organization
- **THEN** the preview shows the error and nothing is imported
