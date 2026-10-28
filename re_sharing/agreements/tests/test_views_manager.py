from http import HTTPStatus

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import CoworkingKindFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory


class ManagerCreateAgreementViewsTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory(accepting_applications=False)
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.manager = make_manager(self.kind.organization_group)
        self.new_url = reverse("agreements:manager-new-agreement")
        self.create_url = reverse(
            "agreements:manager-create-agreement", kwargs={"kind": self.kind.slug}
        )

    def test_non_manager_denied(self):
        self.client.force_login(make_admin(self.organization))

        assert self.client.get(self.new_url).status_code == HTTPStatus.FORBIDDEN
        assert self.client.get(self.create_url).status_code == HTTPStatus.FORBIDDEN

    def test_kind_choice_lists_active_kinds_in_scope(self):
        inactive = MembershipKindFactory(
            organization_group=self.kind.organization_group, is_active=False
        )
        other = MembershipKindFactory()
        self.client.force_login(self.manager)

        response = self.client.get(
            self.new_url, {"organization": self.organization.slug}
        )

        content = response.content.decode()
        assert f"{self.create_url}?organization={self.organization.slug}" in content
        assert inactive.name not in content
        assert other.name not in content

    def test_out_of_scope_kind_not_found(self):
        self.client.force_login(make_manager(OrganizationGroupFactory()))

        assert self.client.get(self.create_url).status_code == HTTPStatus.NOT_FOUND

    def test_organization_preselected(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            self.create_url, {"organization": self.organization.slug}
        )

        assert response.context["form"].initial["organization"] == self.organization

    def test_create_active(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.create_url,
            {
                "organization": self.organization.id,
                "status": Agreement.Status.ACTIVE,
                "decided_at": "2025-11-20",
                "start_date": "2026-01-01",
                "amount": "60",
            },
        )

        agreement = Agreement.objects.get()
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == agreement.get_absolute_url()
        assert agreement.status == Agreement.Status.ACTIVE

    def test_duplicate_shows_error(self):
        existing = AgreementFactory(organization=self.organization, kind=self.kind)
        self.client.force_login(self.manager)

        response = self.client.post(
            self.create_url,
            {
                "organization": self.organization.id,
                "status": Agreement.Status.SUBMITTED,
                "start_date": "2026-01-01",
                "amount": "60",
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert escape(str(existing)) in response.content.decode()
        assert Agreement.objects.count() == 1


class ManagerEditAgreementViewsTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(
            kind=CoworkingKindFactory(),
            status=Agreement.Status.ACTIVE,
            details={"desks": 2, "hours_per_week": 10},
        )
        self.manager = make_manager(self.agreement.kind.organization_group)
        self.url = reverse(
            "agreements:manager-edit-agreement",
            kwargs={"agreement": self.agreement.uuid},
        )

    def test_out_of_scope_denied(self):
        self.client.force_login(make_manager(OrganizationGroupFactory()))

        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

    def test_edit_saves(self):
        self.client.force_login(self.manager)
        assert self.client.get(self.url).status_code == HTTPStatus.OK

        response = self.client.post(
            self.url,
            {
                "start_date": "2027-03-01",
                "amount": "99",
                "desks": "4",
                "hours_per_week": "10",
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        self.agreement.refresh_from_db()
        assert self.agreement.details["desks"] == 4  # noqa: PLR2004

    def test_invalid_shows_form(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            self.url, {"start_date": "2027-03-01", "amount": "99", "desks": "0"}
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].errors

    def test_closed_agreement_redirects(self):
        self.agreement.status = Agreement.Status.ENDED
        self.agreement.save()
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == self.agreement.get_absolute_url()


class ManagerDeleteAgreementViewsTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(with_signed_document=True)
        self.mandate = SepaMandateFactory(agreement=self.agreement)
        self.manager = make_manager(self.agreement.kind.organization_group)
        self.url = reverse(
            "agreements:manager-delete-agreement",
            kwargs={"agreement": self.agreement.uuid},
        )

    def test_confirmation_lists_what_is_removed(self):
        self.client.force_login(self.manager)

        response = self.client.get(self.url)

        content = response.content.decode()
        assert response.status_code == HTTPStatus.OK
        assert self.mandate.reference in content
        assert "signed contract" in content

    def test_post_deletes(self):
        self.client.force_login(self.manager)

        response = self.client.post(self.url)

        assert response.status_code == HTTPStatus.FOUND
        assert not Agreement.objects.exists()

    def test_active_refused(self):
        self.agreement.status = Agreement.Status.ACTIVE
        self.agreement.save()
        self.client.force_login(self.manager)

        response = self.client.post(self.url)

        assert response.url == self.agreement.get_absolute_url()
        assert Agreement.objects.exists()


class AgreementPageManagerActionsTest(TestCase):
    def test_edit_and_delete_shown_to_managers_only(self):
        agreement = AgreementFactory(notes="Internal")
        manager = make_manager(agreement.kind.organization_group)
        edit = reverse(
            "agreements:manager-edit-agreement", kwargs={"agreement": agreement.uuid}
        )
        delete = reverse(
            "agreements:manager-delete-agreement", kwargs={"agreement": agreement.uuid}
        )

        self.client.force_login(manager)
        content = self.client.get(agreement.get_absolute_url()).content.decode()
        assert edit in content
        assert delete in content
        assert "Internal" in content

        self.client.force_login(make_admin(agreement.organization))
        content = self.client.get(agreement.get_absolute_url()).content.decode()
        assert edit not in content
        assert "Internal" not in content

    def test_delete_hidden_for_active(self):
        agreement = AgreementFactory(status=Agreement.Status.ACTIVE)
        self.client.force_login(make_manager(agreement.kind.organization_group))
        delete = reverse(
            "agreements:manager-delete-agreement", kwargs={"agreement": agreement.uuid}
        )

        content = self.client.get(agreement.get_absolute_url()).content.decode()

        assert delete not in content

    def test_organization_page_links_manager_create(self):
        organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.client.force_login(make_manager())

        content = self.client.get(organization.get_absolute_url()).content.decode()

        expected = (
            f"{reverse('agreements:manager-new-agreement')}"
            f"?organization={organization.slug}"
        )
        assert expected in content
