from unittest.mock import Mock
from unittest.mock import patch

from django.conf import settings
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings

from re_sharing.users.adapters import AccountAdapter
from re_sharing.users.adapters import SocialAccountAdapter
from re_sharing.users.models import User


class TestAccountAdapter(TestCase):
    def setUp(self):
        self.adapter = AccountAdapter()
        self.factory = RequestFactory()

    def test_is_open_for_signup_default_true(self):
        """Test signup is open when ACCOUNT_ALLOW_REGISTRATION is True"""
        request = self.factory.get("/")
        with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
            assert self.adapter.is_open_for_signup(request) is True

    def test_is_open_for_signup_false(self):
        """Test signup is closed when ACCOUNT_ALLOW_REGISTRATION is False"""
        request = self.factory.get("/")
        with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
            assert self.adapter.is_open_for_signup(request) is False

    def test_is_open_for_signup_not_set(self):
        """Test signup defaults to True when ACCOUNT_ALLOW_REGISTRATION not set"""
        request = self.factory.get("/")
        # Remove the setting if it exists
        if hasattr(settings, "ACCOUNT_ALLOW_REGISTRATION"):
            delattr(settings, "ACCOUNT_ALLOW_REGISTRATION")
        assert self.adapter.is_open_for_signup(request) is True


class TestSocialAccountAdapter(TestCase):
    def setUp(self):
        self.adapter = SocialAccountAdapter()
        self.factory = RequestFactory()

    def test_is_open_for_signup_default_true(self):
        """Test social signup is open when ACCOUNT_ALLOW_REGISTRATION is True"""
        request = self.factory.get("/")
        sociallogin = Mock()
        with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
            assert self.adapter.is_open_for_signup(request, sociallogin) is True

    def test_is_open_for_signup_false(self):
        """Test social signup is closed when ACCOUNT_ALLOW_REGISTRATION is False"""
        request = self.factory.get("/")
        sociallogin = Mock()
        with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
            assert self.adapter.is_open_for_signup(request, sociallogin) is False

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_with_name(self, mock_parent_populate):
        """Test populate_user sets name from 'name' field"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {"name": "John Doe", "email": "john@example.com"}

        # Mock parent to return user without name
        mock_user = User()
        mock_user.name = ""
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        assert user.name == "John Doe"

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_with_first_name_only(self, mock_parent_populate):
        """Test populate_user sets name from first_name only"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {"first_name": "John", "email": "john@example.com"}

        # Mock parent to return user without name
        mock_user = User()
        mock_user.name = ""
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        assert user.name == "John"

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_with_first_and_last_name(self, mock_parent_populate):
        """Test populate_user combines first_name and last_name"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
        }

        # Mock parent to return user without name
        mock_user = User()
        mock_user.name = ""
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        assert user.name == "John Doe"

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_name_priority(self, mock_parent_populate):
        """Test populate_user prioritizes 'name' over first/last name"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {
            "name": "John Doe",
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "john@example.com",
        }

        # Mock parent to return user without name
        mock_user = User()
        mock_user.name = ""
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        assert user.name == "John Doe"

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_no_name_data(self, mock_parent_populate):
        """Test populate_user when no name data is provided"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {"email": "john@example.com"}

        # Mock parent to return user without name
        mock_user = User()
        mock_user.name = ""
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        # Name should remain empty
        assert user.name == ""

    @patch("re_sharing.users.adapters.DefaultSocialAccountAdapter.populate_user")
    def test_populate_user_existing_name_not_overwritten(self, mock_parent_populate):
        """Test populate_user doesn't overwrite existing user name"""
        request = self.factory.get("/")
        sociallogin = Mock()
        data = {
            "name": "New Name",
            "email": "john@example.com",
        }

        # Mock parent to return user with existing name
        mock_user = User()
        mock_user.name = "Existing Name"
        mock_parent_populate.return_value = mock_user

        user = self.adapter.populate_user(request, sociallogin, data)

        # Name should remain as set by parent
        assert user.name == "Existing Name"
