# Roomsharing

Easily share resources!

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/Haus-des-Engagements/resourcesharing/branch/main/graph/badge.svg?token=JDD51UPVQ8)](https://codecov.io/gh/Haus-des-Engagements/resourcesharing)

License: GPLv3

## Settings

Settings: https://cookiecutter-django.readthedocs.io/en/latest/settings.html


## Setup and run local server
* Setup: https://cookiecutter-django.readthedocs.io/en/latest/developing-locally.html


## Basic Commands
* Start server: `python manage.py runserver 0.0.0.0:8000`

### Setting Up Your Users
*To create a **normal user account**, just go to Sign Up and fill out the form. Once you submit it, you'll see a "Verify Your E-mail Address" page. Go to your console to see a simulated email verification message. Copy the link into your browser. Now the user's email should be verified and ready to go.
* To create a **superuser account**: `python manage.py createsuperuser`
For convenience, you can keep your normal user logged in on Chrome and your superuser logged in on Firefox (or similar), so that you can see how the site behaves for both kinds of users.


### Migrations
After you've made changes in a model, you have to propagate your changes to the database:

* Create new migrations: `python manage.py makemigrations [app_label]`
* Apply migrations: `python manage.py migrate [app_label]`

[app_label] is optional.

### Adding new apps
Our code is organised in so-called "apps", where we try to isolate functionalities and contexts:

Currently, we have the following apps:
- users
- bookings
- resources
- organizations

To create a new app, first create the new folder, then run: `django-admin startapp newappname ./resourcesharing/newappname`.

### Translations
To make strings available for translations in Django:

1. Make gettext_lazy available as _: `from django.utils.translation import gettext_lazy as _`
2. Mark strings as translatable: `_('string to be translated)`
3. Run `python manage.py makemessages -l de` (for German in this case)
4. Translate the strings now available in _/locale/de/LC_MESSAGES/django.po_
5. Compile the .po file with `python manage.py compilemessages` to a .mo file

### Python packages
The used packages are listed in /requirements. When packages are added or removed, execute this command to make the needed packages available and remove the unneeded:

`pip install --upgrade pip && pip install -r /vagrant/requirements/local.txt`

## Database

### Postgres
Django connects to a Postgres Database, that runs inside vagrant. The database can be recreated with these commands:

* Delete the database: `dropdb devicedb`
* Create database: `createdb devicedb`

After creating the new (empty) database, migrations need to be applied again.

## Linting & Coding Style with Ruff
Before committing we locally verify the correct coding style with different tools.
Ruff is a Python linter and code formatter, written in Rust. It is a aggregation of flake8, pylint, pyupgrade and many more.

Ruff comes with a linter `ruff check` and a formatter `ruff format` .
The linter is a wrapper around flake8, pylint, and other linters, and the formatter is a wrapper around black, isort, and other formatters.

Hint: You can also use an installed pre-commit hook with `pre-commit run --all-files`, included:
* Trim Trailing Whitespaces
* Fix end of files
* check Yaml
* flake8
* black
* mypy
* pylint has been excluded because it takes too long
* isort
* djhtml (indent html templates that contain django syntax correctly)

## Testing
To run the tests, check your test coverage, and generate an HTML coverage report in the vagrant machine:

1. Run tests without test coverage analysis: `pytest`
  * If the database schema has changed, use `--create-db`, as pytest will otherwise use the previous one (as it is much faster).
  * To see the slowest tests, use `--durations=10` (to get the 10 slowest tests)
2. Run test with test coverage analysis (and branch analysis) and create the html report: `coverage run --branch -m pytest && coverage html`
3. You can find the report in `htmlcov/index.html`.

## Continuous Integration (CI)
To help keeping a good style, GitLab is running the following pipeline after pushing to the repository:

* pre-commit hook
* pytest

## Deployment
We currently deploy automatically the main branch to https://raum.apps.haus-des-engagements.de/ via caprover.

## Production

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/signup/?code=cookiecutter> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.
