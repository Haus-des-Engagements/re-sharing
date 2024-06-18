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


class ConfirmMembershipView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.confirm_membership_url = reverse(
            "organizations:confirm-membership",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_confirm_already_confirmed_membership_by_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Membership has already been confirmed.")

    def test_confirm_new_membership_by_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.PENDING,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Membership has been confirmed.")

    def test_confirm_new_membership_by_non_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.PENDING,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.confirm_membership_url)
        self.assertContains(
            response, "You are not allowed to confirm this membership.", status_code=401
        )


class CancelMembershipView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.cancel_membership_url = reverse(
            "organizations:cancel-membership",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_cancel_existing_membership_by_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )

        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.cancel_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Membership has been cancelled.",
        )
        assert (
            not Membership.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )

    def test_cancel_not_existing_membership_by_admin(self):
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.cancel_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Membership does not exist.",
        )
        assert (
            not Membership.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )

    def test_cancel_membership_by_non_admin(self):
        orga_booker = UserFactory()
        MembershipFactory(
            user=orga_booker,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(orga_booker)

        response = self.client.get(self.cancel_membership_url)
        self.assertContains(
            response, "You are not allowed to cancel this membership.", status_code=401
        )

    def test_cancel_membership_by_user_itself(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.user)

        response = self.client.get(self.cancel_membership_url)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(
            response,
            "Membership has been cancelled.",
        )
        assert (
            not Membership.objects.filter(organization=self.organization)
            .filter(user__slug=self.user)
            .exists()
        )


class PromoteToAdminMembershipView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.promote_to_admin_membership = reverse(
            "organizations:promote-to-admin-membership",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_promote_to_admin_membership_by_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.promote_to_admin_membership)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Member has been promoted to admin.")
        assert (
            Membership.objects.filter(organization=self.organization, user=self.user)
            .first()
            .role
            == Membership.Role.ADMIN
        )

    def test_promote_to_admin_membership_by_non_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.promote_to_admin_membership)
        self.assertContains(
            response,
            "You are not allowed to promote.",
            status_code=HTTPStatus.UNAUTHORIZED,
        )


class DemoteToBookerMembershipView(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.orga_admin = UserFactory()
        self.organization = OrganizationFactory()
        self.demote_to_booker_membership = reverse(
            "organizations:demote-to-booker-membership",
            kwargs={"organization": self.organization.slug, "user": self.user.slug},
        )

    def test_demote_to_booker_membership_by_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.demote_to_booker_membership)
        assert response.status_code == HTTPStatus.OK
        self.assertContains(response, "Member has been demoted to booker.")
        assert (
            Membership.objects.filter(organization=self.organization, user=self.user)
            .first()
            .role
            == Membership.Role.BOOKER
        )

    def test_demote_to_admin_membership_by_non_admin(self):
        MembershipFactory(
            user=self.user,
            organization=self.organization,
            role=Membership.Role.ADMIN,
            status=Membership.Status.CONFIRMED,
        )
        MembershipFactory(
            user=self.orga_admin,
            organization=self.organization,
            role=Membership.Role.BOOKER,
            status=Membership.Status.CONFIRMED,
        )
        self.client.force_login(self.orga_admin)

        response = self.client.get(self.demote_to_booker_membership)
        self.assertContains(
            response,
            "You are not allowed to demote.",
            status_code=HTTPStatus.UNAUTHORIZED,
        )
