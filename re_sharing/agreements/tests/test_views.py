from datetime import date
from decimal import Decimal
from http import HTTPStatus
from unittest.mock import patch

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import Collection
from re_sharing.agreements.models import CollectionRun
from re_sharing.agreements.models import SepaMandate
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import CollectionRunFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.agreements.tests.helpers import make_admin
from re_sharing.agreements.tests.helpers import make_booker
from re_sharing.agreements.tests.helpers import make_manager
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory
from re_sharing.users.tests.factories import UserFactory

SEPA_SETTINGS = {
    "SEPA_CREDITOR_ID": "DE98ZZZ09999999999",
    "SEPA_CREDITOR_NAME": "Example Creditor e.V.",
    "SEPA_CREDITOR_IBAN": "DE02120300000000202051",
    "SEPA_CREDITOR_BIC": "BYLADEM1001",
}


class OrganizationPageTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory(name="Membership")
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.admin = make_admin(self.organization)

    def test_admin_sees_open_kinds(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.organization.get_absolute_url())

        apply_url = reverse(
            "agreements:apply",
            kwargs={"organization": self.organization.slug, "kind": self.kind.slug},
        )
        assert apply_url in response.content.decode()

    def test_hidden_kinds_and_pending_organizations(self):
        MembershipKindFactory(name="Cellar", accepting_applications=False)
        self.organization.status = Organization.Status.PENDING
        self.organization.save()
        self.client.force_login(self.admin)

        response = self.client.get(self.organization.get_absolute_url())

        assert "/apply/" not in response.content.decode()

    def test_booker_sees_agreements_link_but_no_apply(self):
        self.client.force_login(make_booker(self.organization))

        response = self.client.get(self.organization.get_absolute_url())

        content = response.content.decode()
        assert (
            reverse(
                "agreements:organization-agreements",
                kwargs={"organization": self.organization.slug},
            )
            in content
        )
        assert "/apply/" not in content

    def test_manager_organization_list_links_agreements(self):
        AgreementFactory()
        self.client.force_login(make_manager())

        response = self.client.get(reverse("organizations:manager-list-organizations"))

        assert (
            reverse("agreements:manager-list-agreements") in response.content.decode()
        )


class OrganizationAgreementsViewTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory()
        self.organization = self.agreement.organization
        self.url = reverse(
            "agreements:organization-agreements",
            kwargs={"organization": self.organization.slug},
        )

    def test_confirmed_user_sees_agreements(self):
        self.client.force_login(make_booker(self.organization))

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert self.agreement in response.context["agreements"]
        assert response.context["open_kinds"] == []

    def test_admin_of_pending_organization_gets_hint(self):
        self.organization.status = Organization.Status.PENDING
        self.organization.save()
        self.client.force_login(make_admin(self.organization))

        response = self.client.get(self.url)

        assert "must be confirmed" in response.content.decode()

    def test_foreign_user_denied(self):
        self.client.force_login(UserFactory())

        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

    def test_manager_allowed(self):
        self.client.force_login(make_manager())

        assert self.client.get(self.url).status_code == HTTPStatus.OK


class ApplyViewTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory(
            intro_text="<p>Download <a href='/c.pdf'>contract</a></p>"
        )
        self.organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        self.admin = make_admin(self.organization)
        self.url = reverse(
            "agreements:apply",
            kwargs={"organization": self.organization.slug, "kind": self.kind.slug},
        )

    def test_page_shows_intro_with_contract_link(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert "href='/c.pdf'" in response.content.decode()

    def test_submit_application(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.url,
            {
                "start_date": "2027-10-10",
                "amount": "60",
                "contact_person_function": "Chair",
                "signed_on": "2027-10-01",
                "signed_document": pdf_file(),
            },
        )

        agreement = Agreement.objects.get(organization=self.organization)
        self.assertRedirects(response, agreement.get_absolute_url())
        assert agreement.has_complete_signed_document

    def test_invalid_form_rerenders(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url, {"amount": "60"})

        assert response.status_code == HTTPStatus.OK
        assert not Agreement.objects.exists()

    def test_duplicate_shows_error(self):
        AgreementFactory(organization=self.organization, kind=self.kind)
        self.client.force_login(self.admin)

        response = self.client.post(
            self.url,
            {
                "start_date": "2027-10-10",
                "amount": "60",
                "contact_person_function": "Chair",
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].non_field_errors()

    def test_pending_organization_redirected_with_hint(self):
        self.organization.status = Organization.Status.PENDING
        self.organization.save()
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertRedirects(response, self.organization.get_absolute_url())

    def test_booker_and_closed_kind_denied(self):
        self.client.force_login(make_booker(self.organization))
        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

        self.kind.accepting_applications = False
        self.kind.save()
        self.client.force_login(self.admin)
        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN


class AgreementPageTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory(details={"desks": 2, "hours_per_week": 10})
        self.admin = make_admin(self.agreement.organization)
        self.url = self.agreement.get_absolute_url()

    def test_admin_sees_details_upload_and_mandate_link(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        content = response.content.decode()
        assert "Hours per week" in content
        assert (
            reverse(
                "agreements:create-mandate", kwargs={"agreement": self.agreement.uuid}
            )
            in content
        )
        assert (
            reverse(
                "agreements:upload-signed-document",
                kwargs={"agreement": self.agreement.uuid},
            )
            in content
        )
        assert not response.context["is_manager"]

    def test_signed_document_download_link(self):
        agreement = AgreementFactory(with_signed_document=True)
        self.client.force_login(make_booker(agreement.organization))

        response = self.client.get(agreement.get_absolute_url())

        assert agreement.signed_document.url in response.content.decode()

    def test_foreign_user_denied(self):
        self.client.force_login(UserFactory())

        assert self.client.get(self.url).status_code == HTTPStatus.FORBIDDEN

    def test_upload_signed_document(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "agreements:upload-signed-document",
                kwargs={"agreement": self.agreement.uuid},
            ),
            {"signed_on": "2027-02-01", "signed_document": pdf_file()},
        )

        self.assertRedirects(response, self.url)
        self.agreement.refresh_from_db()
        assert self.agreement.has_complete_signed_document

    def test_upload_invalid_shows_errors(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "agreements:upload-signed-document",
                kwargs={"agreement": self.agreement.uuid},
            ),
            {"signed_on": "2027-02-01"},
            follow=True,
        )

        assert list(response.context["messages"])
        self.agreement.refresh_from_db()
        assert not self.agreement.has_complete_signed_document

    def test_upload_by_booker_denied(self):
        self.client.force_login(make_booker(self.agreement.organization))

        response = self.client.post(
            reverse(
                "agreements:upload-signed-document",
                kwargs={"agreement": self.agreement.uuid},
            ),
            {"signed_on": "2027-02-01", "signed_document": pdf_file()},
        )

        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_upload_on_closed_agreement_refused(self):
        self.agreement.status = Agreement.Status.REJECTED
        self.agreement.save()
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "agreements:upload-signed-document",
                kwargs={"agreement": self.agreement.uuid},
            ),
            {"signed_on": "2027-02-01", "signed_document": pdf_file()},
            follow=True,
        )

        assert "closed agreement" in response.content.decode()


@override_settings(SEPA_MANDATE_FORM_URL="https://example.com/mandate.pdf")
class MandateViewsTest(TestCase):
    def setUp(self):
        self.agreement = AgreementFactory()
        self.admin = make_admin(self.agreement.organization)
        self.create_url = reverse(
            "agreements:create-mandate", kwargs={"agreement": self.agreement.uuid}
        )

    def test_save_bank_data_without_pdf(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            self.create_url, {"account_holder": "Example e.V.", "iban": VALID_IBAN}
        )

        mandate = SepaMandate.objects.get(agreement=self.agreement)
        self.assertRedirects(response, mandate.get_absolute_url())
        page = self.client.get(mandate.get_absolute_url()).content.decode()
        assert mandate.reference in page
        assert "https://example.com/mandate.pdf" in page
        assert (
            reverse(
                "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
            )
            in page
        )
        assert VALID_IBAN not in page
        assert mandate.masked_iban in page

    def test_create_form_and_invalid_iban(self):
        self.client.force_login(self.admin)
        assert self.client.get(self.create_url).status_code == HTTPStatus.OK

        response = self.client.post(
            self.create_url, {"account_holder": "X", "iban": "DE00370400440532013000"}
        )

        assert "iban" in response.context["form"].errors

    def test_existing_mandate_redirects(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        self.client.force_login(self.admin)

        self.assertRedirects(
            self.client.get(self.create_url), mandate.get_absolute_url()
        )

    def test_closed_agreement_shows_error(self):
        self.agreement.status = Agreement.Status.ENDED
        self.agreement.save()
        self.client.force_login(self.admin)

        response = self.client.post(
            self.create_url, {"account_holder": "Example e.V.", "iban": VALID_IBAN}
        )

        assert response.context["form"].non_field_errors()

    def test_upload_signed_mandate(self):
        mandate = SepaMandateFactory(agreement=self.agreement, signed_document=None)
        self.client.force_login(self.admin)
        url = reverse(
            "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
        )

        self.client.post(url, {"signed_on": "2027-02-01"})
        mandate.refresh_from_db()
        assert not mandate.is_active

        self.client.post(
            url, {"signed_on": "2027-02-01", "signed_document": pdf_file()}
        )
        mandate.refresh_from_db()
        assert mandate.is_active

    def test_upload_on_revoked_mandate_refused(self):
        mandate = SepaMandateFactory(
            agreement=self.agreement, signed_document=None, revoked_on=date(2027, 1, 1)
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "agreements:upload-signed-mandate", kwargs={"mandate": mandate.uuid}
            ),
            {"signed_on": "2027-02-01", "signed_document": pdf_file()},
            follow=True,
        )

        assert "revoked mandate" in response.content.decode()

    def test_signed_mandate_download_only_for_permitted(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        self.client.force_login(self.admin)
        assert (
            mandate.signed_document.url
            in self.client.get(mandate.get_absolute_url()).content.decode()
        )

        self.client.force_login(make_booker(self.agreement.organization))
        assert (
            self.client.get(mandate.get_absolute_url()).status_code
            == HTTPStatus.FORBIDDEN
        )
        self.client.force_login(UserFactory())
        assert (
            self.client.get(mandate.get_absolute_url()).status_code
            == HTTPStatus.FORBIDDEN
        )

    def test_manager_sees_full_iban_and_revokes(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        self.client.force_login(make_manager())

        assert (
            VALID_IBAN in self.client.get(mandate.get_absolute_url()).content.decode()
        )

        self.client.post(
            reverse(
                "agreements:manager-revoke-mandate", kwargs={"mandate": mandate.uuid}
            ),
            {"revoked_on": "2027-04-01"},
        )
        mandate.refresh_from_db()
        assert mandate.revoked_on == date(2027, 4, 1)

        response = self.client.post(
            reverse(
                "agreements:manager-revoke-mandate", kwargs={"mandate": mandate.uuid}
            ),
            {"revoked_on": "2027-04-02"},
            follow=True,
        )
        assert "already revoked" in response.content.decode()

    def test_admin_cannot_revoke(self):
        mandate = SepaMandateFactory(agreement=self.agreement)
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "agreements:manager-revoke-mandate", kwargs={"mandate": mandate.uuid}
            ),
            {"revoked_on": "2027-04-01"},
        )

        assert response.status_code == HTTPStatus.FORBIDDEN


@patch("re_sharing.resources.services_permanent_code.send_permanent_code_created_email")
class ManagerAgreementViewsTest(TestCase):
    def setUp(self):
        self.kind = MembershipKindFactory()
        self.agreement = AgreementFactory(
            kind=self.kind, with_signed_document=True, start_date=date(2027, 10, 10)
        )
        SepaMandateFactory(agreement=self.agreement)
        self.manager = make_manager(self.kind.organization_group)
        self.client.force_login(self.manager)

    def _post(self, name, data=None, **kwargs):
        return self.client.post(
            reverse(name, kwargs={"agreement": self.agreement.uuid}),
            data or {},
            follow=True,
            **kwargs,
        )

    def test_list_filters_and_count(self, mock_code_email):
        other = AgreementFactory(kind=self.kind, status=Agreement.Status.ACTIVE)
        out_of_scope = AgreementFactory()

        response = self.client.get(
            reverse("agreements:manager-list-agreements"), {"status": "1"}
        )

        agreements = list(response.context["agreements"])
        assert agreements == [self.agreement]
        assert other not in agreements
        assert out_of_scope not in agreements
        assert response.context["submitted_count"] == 1

        response = self.client.get(
            reverse("agreements:manager-list-agreements"), {"kind": self.kind.slug}
        )
        assert set(response.context["agreements"]) == {self.agreement, other}

    def test_detail_shows_decision_form(self, mock_code_email):
        response = self.client.get(self.agreement.get_absolute_url())

        assert response.context["is_manager"]
        assert (
            reverse(
                "agreements:manager-approve-agreement",
                kwargs={"agreement": self.agreement.uuid},
            )
            in response.content.decode()
        )

    def test_approve(self, mock_code_email):
        self._post("agreements:manager-approve-agreement", {"decided_at": "2027-10-12"})

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ACTIVE
        assert self.agreement.decided_at == date(2027, 10, 12)

    def test_approve_without_date(self, mock_code_email):
        response = self._post("agreements:manager-approve-agreement")

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.SUBMITTED
        assert list(response.context["messages"])

    def test_approve_refused_shows_message(self, mock_code_email):
        self.agreement.mandates_of_agreement.all().delete()

        response = self._post(
            "agreements:manager-approve-agreement", {"decided_at": "2027-10-12"}
        )

        assert "SEPA mandate is missing" in response.content.decode()

    def test_reject(self, mock_code_email):
        self._post("agreements:manager-reject-agreement", {"decided_at": "2027-10-12"})

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.REJECTED

    def test_end(self, mock_code_email):
        self.agreement.status = Agreement.Status.ACTIVE
        self.agreement.save()

        self._post("agreements:manager-end-agreement", {"end_date": "2027-12-31"})

        self.agreement.refresh_from_db()
        assert self.agreement.status == Agreement.Status.ENDED
        assert self.agreement.end_date == date(2027, 12, 31)

    def test_end_submitted_refused(self, mock_code_email):
        response = self._post("agreements:manager-end-agreement")

        assert "Only active agreements" in response.content.decode()

    def test_out_of_scope_manager_denied(self, mock_code_email):
        self.client.force_login(make_manager(OrganizationGroupFactory()))

        assert self.client.get(self.agreement.get_absolute_url()).status_code == (
            HTTPStatus.FORBIDDEN
        )
        response = self.client.post(
            reverse(
                "agreements:manager-approve-agreement",
                kwargs={"agreement": self.agreement.uuid},
            ),
            {"decided_at": "2027-10-12"},
        )
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_non_manager_denied(self, mock_code_email):
        self.client.force_login(make_admin(self.agreement.organization))

        for name in ["manager-list-agreements", "manager-collections", "manager-runs"]:
            assert self.client.get(reverse(f"agreements:{name}")).status_code == (
                HTTPStatus.FORBIDDEN
            )


@override_settings(**SEPA_SETTINGS)
class ManagerCollectionViewsTest(TestCase):
    def setUp(self):
        self.manager = make_manager()
        self.client.force_login(self.manager)

    def test_collections_overview_with_attention_list(self):
        returned = CollectionFactory(status=Collection.Status.RETURNED)
        planned = CollectionFactory()
        CollectionRunFactory()

        response = self.client.get(reverse("agreements:manager-collections"))

        assert returned in response.context["attention"]
        assert planned not in response.context["attention"]
        assert response.context["runs_not_uploaded"].count() == 1
        assert (
            reverse(
                "agreements:manager-collection-invoice",
                kwargs={"collection": returned.uuid},
            )
            in response.content.decode()
        )

        filtered = self.client.get(
            reverse("agreements:manager-collections"),
            {
                "status": Collection.Status.PLANNED,
                "kind": "fee",
                "agreement_kind": planned.agreement.kind.slug,
            },
        )
        assert list(filtered.context["collections"]) == [planned]

    def test_mark_paid_and_cancel(self):
        refund = CollectionFactory(kind=Collection.Kind.DEPOSIT_REFUND, mandate=None)
        planned = CollectionFactory()

        self.client.post(
            reverse(
                "agreements:manager-collection-paid", kwargs={"collection": refund.uuid}
            ),
            {"note": "by hand"},
        )
        self.client.post(
            reverse(
                "agreements:manager-collection-cancel",
                kwargs={"collection": planned.uuid},
            ),
            {"note": "waived"},
        )
        response = self.client.post(
            reverse(
                "agreements:manager-collection-cancel",
                kwargs={"collection": refund.uuid},
            ),
            {"note": "again"},
            follow=True,
        )

        refund.refresh_from_db()
        planned.refresh_from_db()
        assert refund.status == Collection.Status.PAID
        assert planned.status == Collection.Status.CANCELLED
        assert "already settled" in response.content.decode()

    def test_invoice_return(self):
        returned = CollectionFactory(status=Collection.Status.RETURNED)

        with patch(
            "re_sharing.agreements.services_collections.buchhaltungsbutler.create_einvoice",
            return_value={"success": True, "invoicenumber": "RE-5"},
        ):
            self.client.post(
                reverse(
                    "agreements:manager-collection-invoice",
                    kwargs={"collection": returned.uuid},
                )
            )

        returned.refresh_from_db()
        assert returned.invoice_number == "RE-5"

    def test_build_upload_and_delete_runs(self):
        CollectionFactory(status=Collection.Status.NOTIFIED, due_date=date(2027, 3, 5))
        url = reverse("agreements:manager-runs")

        assert self.client.get(url).status_code == HTTPStatus.OK
        response = self.client.post(url, {"collection_date": "2027-01-01"}, follow=True)
        assert "No notified collections" in response.content.decode()

        self.client.post(url, {"collection_date": "2027-03-05"})
        run = CollectionRun.objects.get()
        page = self.client.get(url).content.decode()
        assert run.xml_file.url in page

        self.client.post(
            reverse("agreements:manager-run-uploaded", kwargs={"run": run.uuid})
        )
        run.refresh_from_db()
        assert run.uploaded_at is not None

        response = self.client.post(
            reverse("agreements:manager-run-delete", kwargs={"run": run.uuid}),
            follow=True,
        )
        assert "cannot be deleted" in response.content.decode()

    def test_delete_run_before_upload(self):
        collection = CollectionFactory(status=Collection.Status.SUBMITTED)
        run = CollectionRunFactory(total_amount=Decimal(120), count=1)
        collection.run = run
        collection.save()

        self.client.post(
            reverse("agreements:manager-run-delete", kwargs={"run": run.uuid})
        )

        collection.refresh_from_db()
        assert collection.status == Collection.Status.NOTIFIED
        assert not CollectionRun.objects.exists()
