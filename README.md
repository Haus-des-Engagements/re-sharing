# Re(source)-Sharing

A comprehensive platform for organizations to share and book resources efficiently.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![codecov](https://codecov.io/gh/Haus-des-Engagements/resourcesharing/branch/main/graph/badge.svg?token=JDD51UPVQ8)](https://codecov.io/gh/Haus-des-Engagements/resourcesharing)

License: GPLv3

## Overview

Re(source)-Sharing is a Django-based web application designed to facilitate resource sharing between organizations. The platform allows organizations to list their resources (such as rooms, equipment, vehicles, etc.) and make them available for booking by other organizations, with customizable restrictions, compensation options, and scheduling capabilities.

### Key Features

- **Resource Management**: Create, update, and manage various types of resources with detailed descriptions and images
- **Organization Management**: Register and manage organizations with different activity areas and legal forms
- **Booking System**: Book resources with one-time or recurring schedules
- **Compensation Options**: Set up different compensation models for resource usage
- **Access Control**: Define who can access resources and when
- **Restriction Management**: Set restrictions on resource availability based on time or organization
- **User Management**: Manage users with different roles and permissions within organizations
- **Email Notifications**: Automated email notifications for booking confirmations, cancellations, etc.

## Project Structure

The project is organized into several Django apps:

- **users**: User management and authentication
- **resources**: Resource definition, restrictions, and compensation models
- **organizations**: Organization management, permissions, and communication
- **bookings**: Booking management, scheduling, and messaging

## Installation and Setup

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis
- Git

### Local Development Setup
1. Clone the repository:
   ```bash
   git clone https://github.com/Haus-des-Engagements/resourcesharing.git
   cd resourcesharing
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements/local.txt
   ```

4. Set up the database:
   ```bash
   createdb re-sharing
   python manage.py migrate
   ```

5. Create a superuser:
   ```bash
   python manage.py createsuperuser
   ```

6. Run the development server:
   ```bash
   python manage.py runserver 0.0.0.0:8000
   ```

For more detailed setup instructions, see: https://cookiecutter-django.readthedocs.io/en/latest/developing-locally.html

### Settings
For information about settings configuration, see: https://cookiecutter-django.readthedocs.io/en/latest/settings.html

## Basic Commands

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

* Delete the database: `dropdb re-sharing`
* Create database: `createdb re-sharing`

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

## Usage Guide

### For Organizations

#### Registering an Organization
1. Create a user account and verify your email
2. Navigate to the Organizations section and click "Register New Organization"
3. Fill in the required information about your organization
4. Submit the form and wait for admin approval

#### Managing Resources
1. Once your organization is approved, navigate to the Resources section
2. Click "Add New Resource" to register a resource for sharing
3. Fill in the resource details, including:
   - Name and description
   - Resource type
   - Availability schedule
   - Access information
   - Compensation requirements
   - Upload images of the resource
4. Set any restrictions on who can book the resource and when
5. Publish the resource to make it available for booking

#### Managing Bookings
1. Navigate to the Bookings section to view all booking requests for your resources
2. Approve or reject booking requests
3. Communicate with users through the messaging system
4. View your booking calendar to see all upcoming bookings

### For Users

#### Finding Resources
1. Browse the Resources section to see available resources
2. Use filters to narrow down resources by type, location, or availability
3. Click on a resource to view detailed information

#### Booking Resources
1. Select the resource you want to book
2. Choose the date and time for your booking
3. For recurring bookings, set the frequency and end date
4. Submit your booking request
5. Wait for approval from the resource owner
6. Once approved, you'll receive access information for the resource

## Contribution Guidelines

We welcome contributions to the Re(source)-Sharing project! Here's how you can contribute:

### Reporting Issues
- Use the GitHub issue tracker to report bugs
- Provide detailed steps to reproduce the issue
- Include information about your environment

### Contributing Code
1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Write tests for your changes
4. Ensure all tests pass with `pytest`
5. Make sure your code follows our coding style (use `ruff format` and `ruff check`)
6. Submit a pull request with a clear description of your changes

### Documentation
- Help improve the documentation by fixing typos or clarifying instructions
- Add examples and use cases to make the documentation more helpful

## Production

### Deployment
For production deployment, follow these steps:
1. Set up a production server with the required dependencies
2. Configure environment variables for production settings
3. Set up a PostgreSQL database
4. Set up Redis for caching
5. Configure a web server (e.g., Nginx) and WSGI server (e.g., Gunicorn)
6. Set up SSL certificates for secure connections
7. Deploy the application code
8. Run migrations and collect static files
9. Start the application

### Sentry

Sentry is an error logging aggregator service. You can sign up for a free account at <https://sentry.io/> or download and host it yourself.
The system is set up with reasonable defaults, including 404 logging and integration with the WSGI application.

You must set the DSN url in production.
