from http import HTTPStatus

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseRedirect
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from roomsharing.organizations.models import Membership
from roomsharing.organizations.tests.factories import MembershipFactory
from roomsharing.organizations.tests.factories import OrganizationFactory
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
        MembershipFactory(
            user=user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
        )

        response = self.client.get(self.show_organization_url)
        assert response.status_code == HTTPStatus.OK
        assert not response.context["is_admin"]
        assert "membership_status" not in response.context["members"].values()[0]

    def test_access_user_is_admin(self):
        user = UserFactory()
        self.client.force_login(user)
        MembershipFactory(
            user=user,
            organization=self.organization,
            role=Membership.Role.ADMIN,
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


class TestRequestMembershipView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.organization = OrganizationFactory()
        self.request_membership_url = reverse(
            "organizations:request-membership",
            kwargs={"organization": self.organization.slug},
        )

    def test_request_pending(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.PENDING,
        )

        response = self.client.get(self.request_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "You are already requested to become a member. Please wait patiently.",
        )

    def test_already_confirmed(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )

        response = self.client.get(self.request_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "You are already member of this organization.")

    def test_rejected(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.REJECTED,
        )

        response = self.client.get(self.request_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response, "You have already been rejected by this organization."
        )

    def test_new_request(self):
        response = self.client.get(self.request_membership_url)
        membership = (
            Membership.objects.filter(organization=self.organization)
            .filter(user=self.user)
            .first()
        )
        assert membership
        assert membership.organization == self.organization
        assert membership.user == self.user
        assert membership.role == Membership.Role.BOOKER
        assert membership.status == Membership.Status.PENDING

        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Successfully requested. "
            "You will be notified when your request is approved or denied.",
        )
