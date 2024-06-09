from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.organizations.models import OrganizationMembership
from roomsharing.organizations.tests.factories import OrganizationFactory
from roomsharing.organizations.tests.factories import OrganizationMembershipFactory
from roomsharing.organizations.views import show_organization_view
from roomsharing.users.tests.factories import UserFactory


class TestShowOrganizationView(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.organization = OrganizationFactory()
        self.show_organization_url = reverse(
            "organizations:show-organization",
            kwargs={"organization": self.organization.slug},
        )

    def test_access_user_is_member(self):
        user = UserFactory()
        self.client.force_login(user)
        OrganizationMembershipFactory(
            user=user,
            organization=self.organization,
            role=OrganizationMembership.Role.BOOKER,
        )

        response = self.client.get(self.show_organization_url)
        assert response.status_code == HTTPStatus.OK
        assert not response.context["is_admin"]
        assert "membership_status" not in response.context["members"].values()[0]

    def test_access_user_is_admin(self):
        user = UserFactory()
        self.client.force_login(user)
        OrganizationMembershipFactory(
            user=user,
            organization=self.organization,
            role=OrganizationMembership.Role.ADMIN,
        )

        response = self.client.get(self.show_organization_url)
        assert response.status_code == HTTPStatus.OK
        assert response.context["is_admin"]
        assert "membership_status" in response.context["members"].values()[0]

    def test_access_by_anonymous_user(self):
        request = self.rf.get("/fake-url/")
        request.user = AnonymousUser()

        response = show_organization_view(request, self.organization.slug)
        login_url = reverse(settings.LOGIN_URL)

        assert isinstance(response, HttpResponseRedirect)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"{login_url}?next=/fake-url/"
