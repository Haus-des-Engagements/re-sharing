from io import StringIO

import pytest
from django.core.management import call_command

from re_sharing.users.models import User


@pytest.mark.django_db()
class TestUserManager:
    def test_create_user(self):
        user = User.objects.create_user(
            email="john@example.com",
            password="something-r@nd0m!",  # noqa: S106
            first_name="John",
            last_name="Doe",
        )
        assert user.email == "john@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert not user.is_staff
        assert not user.is_superuser
        assert user.check_password("something-r@nd0m!")
        assert user.username is None

    def test_create_user_without_email(self):
        """Test that creating a user without email raises ValueError"""
        with pytest.raises(ValueError, match="The given email must be set"):
            User.objects.create_user(email="", password="test123")  # noqa: S106

    def test_create_user_with_none_email(self):
        """Test that creating a user with None email raises ValueError"""
        with pytest.raises(ValueError, match="The given email must be set"):
            User.objects.create_user(email=None, password="test123")  # noqa: S106

    def test_create_superuser(self):
        user = User.objects.create_superuser(
            email="admin@example.com",
            first_name="Admin",
            last_name="Example",
            password="something-r@nd0m!",  # noqa: S106
        )
        assert user.email == "admin@example.com"
        assert user.first_name == "Admin"
        assert user.last_name == "Example"
        assert user.is_staff
        assert user.is_superuser
        assert user.username is None

    def test_create_superuser_username_ignored(self):
        user = User.objects.create_superuser(
            email="test@example.com",
            password="something-r@nd0m!",  # noqa: S106
        )
        assert user.username is None

    def test_create_superuser_without_is_staff(self):
        """Test that creating a superuser with is_staff=False raises ValueError"""
        with pytest.raises(ValueError, match="Superuser must have is_staff=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="test123",  # noqa: S106
                is_staff=False,
            )

    def test_create_superuser_without_is_superuser(self):
        """Test that creating a superuser with is_superuser=False raises ValueError"""
        with pytest.raises(ValueError, match="Superuser must have is_superuser=True"):
            User.objects.create_superuser(
                email="admin@example.com",
                password="test123",  # noqa: S106
                is_superuser=False,
            )


@pytest.mark.django_db()
def test_createsuperuser_command():
    """Ensure createsuperuser command works with our custom manager."""
    out = StringIO()
    command_result = call_command(
        "createsuperuser",
        "--email",
        "henry@example.com",
        "--first_name",
        "Henry",
        "--last_name",
        "Super",
        interactive=False,
        stdout=out,
    )

    assert command_result is None
    assert out.getvalue() == "Superuser created successfully.\n"
    user = User.objects.get(email="henry@example.com")
    assert not user.has_usable_password()
