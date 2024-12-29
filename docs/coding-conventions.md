# Coding Conventions


In general, we are following the Coding Conventions of PEP 8. In case of questions, use
* the Style Guide for Python Code (https://www.python.org/dev/peps/pep-0008/) and the
* Coding style for Django (https://docs.djangoproject.com/en/dev/internals/contributing/writing-code/coding-style/).

## 1. Naming

* Everything (and code) is written in English.
* The use of camelCase is prohibited for variables and only possible for classes. Avoid too much underscores in variable
names.

### Models
* A class representing a database model is always written in singular (e.g. "RoomBooking") and should be in CamelCase 
without underscores.
* Variable names for backward resolution:
  * Used for finding all occurrences of a referenced attribute as a foreign key:
https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.ForeignKey.related_name
  * Both corresponding variables should be set.
  * 'related_name': 'current class in plural' + '_of_' + 'foreign key class', e.g. 'bookings_of_organization' is the 
related_name of the Organization in Bookings class.
  * 'related_query_name': Like 'related_name', but the current class is written in singular.

### Apps
* We seperate the Django-project in multiple apps. Each app has some core functionality.
* An app’s name should be a plural version of the app’s main model (e.g. appname "resources" as the main model is "resource").
* When there are no models inside the app (e.g. for pure API apps), the app's name should reflect what it is doing or 
for whom (e.g. "api_mobile_app")

## 3. Code documentation

* If a method, function, class or module is complicated, use Docstrings: """ Here you write in the doc. """ 
(https://www.python.org/dev/peps/pep-0257/)
* Comment only complicated parts.

## 4. Git commit conventions

Every commit message should follow the following convention:
 * 'sort'('scope'): 'What was done?' \
    'Why was it done?'
 * e.g. test(bookings): a time-slot can't be booked twice.
 * Sorts: feat (for feature), test, doc, refa, i18n (internationalization / translations)
 * Possible scopes: an app, a (model/view) class, a function/method

## 5. Testing conventions
We only test our own custom code. So we won't test if Django is correctly translating a model into the respective 
Database fields.

