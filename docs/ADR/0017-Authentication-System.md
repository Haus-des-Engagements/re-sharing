# 17. Authentication System - django-allauth

Date: 2025-10-20

## Status

Accepted

## Context

User authentication and registration are fundamental security requirements for the booking platform. Users need to create accounts, log in securely, verify their email addresses, and potentially use multi-factor authentication for enhanced security.

Django provides a built-in authentication system with User models and login/logout views, but it requires significant customization for modern authentication workflows including:
* Email-based authentication (without usernames)
* Email verification requirements
* Password reset flows
* Social authentication (Google, GitHub, etc.)
* Multi-factor authentication (MFA)
* Account management (email changes, password changes)

We considered the following options:
1. Django's built-in authentication system with custom views
2. django-allauth - comprehensive authentication package
3. djoser or django-rest-auth (API-focused)
4. Custom authentication implementation

Key requirements:
* Email-based login (no username field)
* Mandatory email verification before account activation
* Password reset functionality
* Future-proof for MFA and social authentication
* Well-maintained and security-focused
* Integration with existing User model
* German language support for user-facing text

## Decision

We will use **django-allauth** as our authentication system with the following configuration:
* Email-only authentication (ACCOUNT_AUTHENTICATION_METHOD = "email")
* Username field not used (ACCOUNT_USER_MODEL_USERNAME_FIELD = None)
* Mandatory email verification (ACCOUNT_EMAIL_VERIFICATION = "mandatory")
* MFA support enabled via allauth[mfa] package
* Social authentication capabilities configured but optional

Configuration choices:
* Email is required and unique across all users
* Users must verify email before accessing the platform
* Login redirect goes to user dashboard
* Logout redirect to homepage
* Email confirmation required for email changes
* Support for social auth providers (ready for future use)

## Consequences

* The project depends on django-allauth and its continued maintenance
* All authentication-related views and templates come from allauth
* Email delivery infrastructure is critical (account activation emails must be sent)
* Username field exists in User model but remains unused (allauth requirement)
* Social authentication can be enabled by adding provider configurations
* MFA can be enabled per-user without code changes
* Custom authentication logic must integrate with allauth's session management
* Email verification step adds friction to user registration but improves security
* Password policies and validation can be configured through allauth settings
* Account management (password reset, email change) handled consistently
* Localization of authentication flows requires translating allauth templates
* allauth templates need customization to match Bootstrap 5 styling
* Session management and remember-me functionality provided by allauth
* Security updates and patches depend on allauth's release cycle
* Migration away from allauth would require reimplementing all auth flows
* The User model structure is constrained by allauth's expectations
