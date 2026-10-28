from http import HTTPStatus

from allauth.mfa.models import Authenticator
from django.conf import settings
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.providers.tests.factories import ManagerFactory
from re_sharing.users.middleware import requires_mfa
from re_sharing.users.tests.factories import UserFactory


def _enable_totp(user):
    Authenticator.objects.create(
        user=user, type=Authenticator.Type.TOTP, data={"secret": "unused"}
    )


@override_settings(REQUIRE_STAFF_MFA=True)
class RequireStaffMFATest(TestCase):
    def setUp(self):
        self.manager = ManagerFactory().user
        self.setup_url = reverse("mfa_index")
        self.manager_page = reverse("agreements:manager-list-agreements")

    def test_who_requires_mfa(self):
        assert requires_mfa(self.manager)
        assert requires_mfa(UserFactory(is_staff=True))
        assert requires_mfa(UserFactory(is_superuser=True))
        assert not requires_mfa(UserFactory())

    def test_manager_without_mfa_is_redirected_with_message(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.manager_page, follow=True)

        self.assertRedirects(response, self.setup_url)
        assert "must use two-factor authentication" in response.content.decode()

    def test_staff_redirected_from_admin(self):
        self.client.force_login(UserFactory(is_staff=True))

        response = self.client.get(f"/{settings.ADMIN_URL}")

        self.assertRedirects(response, self.setup_url, fetch_redirect_response=False)

    def test_htmx_request_gets_hx_redirect(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.manager_page, headers={"HX-Request": "true"})

        assert response.status_code == HTTPStatus.NO_CONTENT
        assert response["HX-Redirect"] == self.setup_url

    def test_setup_and_logout_reachable(self):
        self.client.force_login(self.manager)

        assert self.client.get(self.setup_url).status_code == HTTPStatus.OK
        totp = self.client.get(reverse("mfa_activate_totp"))
        assert totp.status_code in (HTTPStatus.OK, HTTPStatus.FOUND)
        assert totp.get("Location", "") != self.setup_url
        assert self.client.get(reverse("account_logout")).status_code == HTTPStatus.OK

    def test_static_files_exempt(self):
        self.client.force_login(self.manager)

        response = self.client.get(f"{settings.STATIC_URL}missing.css")

        assert response.get("Location") != self.setup_url

    def test_manager_with_mfa_passes(self):
        _enable_totp(self.manager)
        self.client.force_login(self.manager)

        assert self.client.get(self.manager_page).status_code == HTTPStatus.OK

    def test_recovery_codes_alone_do_not_count(self):
        Authenticator.objects.create(
            user=self.manager,
            type=Authenticator.Type.RECOVERY_CODES,
            data={"seed": "unused"},
        )
        self.client.force_login(self.manager)

        response = self.client.get(self.manager_page)

        self.assertRedirects(response, self.setup_url, fetch_redirect_response=False)

    def test_other_users_not_affected(self):
        organization = AgreementFactory().organization
        self.client.force_login(make_admin(organization))

        response = self.client.get(
            reverse(
                "agreements:organization-agreements",
                kwargs={"organization": organization.slug},
            )
        )

        assert response.status_code == HTTPStatus.OK

    def test_anonymous_not_affected(self):
        response = self.client.get(self.manager_page)

        assert response.get("Location", "").startswith(reverse("account_login"))

    def test_impersonated_session_not_redirected(self):
        self.client.force_login(self.manager)
        session = self.client.session
        session["hijack_history"] = ["1"]
        session.save()

        assert self.client.get(self.manager_page).status_code == HTTPStatus.OK

    @override_settings(REQUIRE_STAFF_MFA=False)
    def test_switched_off(self):
        self.client.force_login(self.manager)

        assert self.client.get(self.manager_page).status_code == HTTPStatus.OK
