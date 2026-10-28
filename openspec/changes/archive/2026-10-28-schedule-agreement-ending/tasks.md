## 1. Services (red, then green)

- [x] 1.1 Tests for `end_agreement`: the given date replaces a stored end date, ending before the start date is allowed, collections after the end date are deleted when planned and cancelled when notified
- [x] 1.2 Implement `_drop_collections_after` and use it in `end_agreement`; date handling per design D2
- [x] 1.3 Tests and implementation for `schedule_agreement_end`: scope, active only, future date only, not before start, collections dropped, group and code unchanged, no email; moving the date later lets `create_due_collections` recreate planned periods; the daily command ends it after the date with the email
- [x] 1.4 `manager_update_agreement` drops collections after a changed end date, with a test

## 2. View and page

- [x] 2.1 `manager_end_agreement_view` defaults to today and schedules future dates; error messages for refused dates; tests for both paths
- [x] 2.2 Agreement page: scheduled end shown, end form prefilled, button "Change end date" while pending; form help text updated; view test

## 3. Wrap-up

- [x] 3.1 German translations, compile messages
- [x] 3.2 Full test suite and pre-commit
