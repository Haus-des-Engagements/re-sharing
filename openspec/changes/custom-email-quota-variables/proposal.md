## Why

Before the free bookings quota is applied to bookings made earlier, organizations have to be told what it means for them. The custom email page can already address the right organizations, but it cannot say how many of their bookings lie above the free allowance or what those would cost.

## What Changes

- Three new template tags for custom emails, each limited to the selected period and resources:
  - `bookings_above_limit`: bookings above the free allowance that would be charged.
  - `cost_above_limit`: what those bookings would cost in total.
  - `bookings_above_limit_without_rate`: bookings above the allowance on rooms without a paid rate, which would be removed instead of charged.
- The values come from a dry run of the existing quota transition, so an email announces exactly what the transition will do. Only bookings that were not yet priced against the quota count; once the transition has run for an organization, all three are 0.
- The page help lists the new tags.
- Out of scope: showing the values in the organization preview table or filtering organizations by them. Texts can be made conditional in the body with `{% if bookings_above_limit %}`.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `organization-custom-email`: adds requirements for the three quota template tags and their documentation on the page.

## Impact

- `re_sharing/bookings/services_quota_transition.py`: new read-only preview function on top of the existing dry run.
- `re_sharing/organizations/mails.py`: `send_custom_organization_email` adds the values to the template context when the email uses them.
- `re_sharing/templates/organizations/custom_organization_email.html`: help text.
- No model, migration or dependency changes. The transition itself is unchanged.
- Builds on `custom-email-formatting`, which is implemented but not yet archived; archive that change first.
