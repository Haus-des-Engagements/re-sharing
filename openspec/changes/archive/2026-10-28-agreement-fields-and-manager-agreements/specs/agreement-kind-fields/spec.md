## ADDED Requirements

### Requirement: Kinds define their application fields

Each agreement kind SHALL have an ordered list of application fields, edited in the admin together with the kind. A field SHALL have a key unique within the kind, a label, a type of text, whole number, decimal, date or choice, a required flag, an optional help text, for choice fields a list of choices, for number fields an optional minimum, an order and an active flag. Keys SHALL NOT collide with the agreement's own fields. A kind without fields SHALL ask only for the common agreement data.

#### Scenario: Choice field without choices

- **WHEN** staff save a choice field without any choices
- **THEN** the admin rejects it with a message

#### Scenario: Reserved key

- **WHEN** staff save a field with the key `amount`
- **THEN** the admin rejects it with a message

#### Scenario: Kind without fields

- **WHEN** a kind has no application fields
- **THEN** its application form shows only start date, amount, contact person function and the kind-dependent end date and deposit

### Requirement: Forms are built from the field definitions

The application form, the manager's create form and the manager's edit form SHALL show the kind's active fields in order, with their label, help text and required flag, and SHALL validate each answer by its type, its minimum and its choices. Answers SHALL be stored in the agreement's details under the field key: text and choice as text, whole numbers as integers, decimals as decimal strings and dates as ISO dates.

#### Scenario: Answers are validated by type

- **WHEN** an applicant enters `abc` for a whole-number field
- **THEN** the form is rejected with a message on that field

#### Scenario: Minimum enforced

- **WHEN** a field has the minimum 1 and the applicant enters 0
- **THEN** the form is rejected with a message on that field

#### Scenario: Optional field left empty

- **WHEN** an applicant leaves an optional field empty
- **THEN** the application is accepted and the field's answer is stored as empty

#### Scenario: Inactive field not asked

- **WHEN** a field is inactive
- **THEN** new applications and the edit form do not ask for it

### Requirement: Answers stay visible

The agreement page SHALL show the answers of the kind's active fields in order with their labels, followed by any other stored answers, labelled with their field's label or, where no field exists, the key.

#### Scenario: Deactivated field keeps its answers

- **WHEN** a field is deactivated after agreements answered it
- **THEN** those agreements still show the answer with the field's label

### Requirement: Answered fields keep their key

A field's key SHALL NOT be changeable after the field was created. A field SHALL NOT be deletable while an agreement of the kind has an answer under its key; staff deactivate it instead. A stored answer that is no longer one of a choice field's choices SHALL remain selectable in the edit form of that agreement.

#### Scenario: Delete refused for answered field

- **WHEN** staff try to delete a field that agreements have answered
- **THEN** the admin refuses with a message to deactivate it instead

#### Scenario: Removed choice is kept

- **WHEN** a choice is removed from a field and a manager edits an agreement that chose it
- **THEN** the edit form preselects the stored answer and saving keeps it

### Requirement: Existing form types are converted

The upgrade SHALL replace each kind's form type by field definitions with the keys already used in stored answers: coworking with desks and hours per week (whole numbers, minimum 1), office with room (text), cellar with area in m² (decimal, minimum 1), membership with none. The form type setting SHALL be removed.

#### Scenario: Coworking kind upgraded

- **WHEN** the upgrade runs on a kind with the coworking form type
- **THEN** the kind has the required fields `desks` and `hours_per_week` and its agreements show their stored answers with these labels
