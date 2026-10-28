from http import HTTPStatus

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import AgreementKindField
from re_sharing.agreements.models import SepaMandate
from re_sharing.agreements.tests.factories import VALID_IBAN
from re_sharing.agreements.tests.factories import AgreementFactory
from re_sharing.agreements.tests.factories import AgreementKindFieldFactory
from re_sharing.agreements.tests.factories import CollectionFactory
from re_sharing.agreements.tests.factories import MembershipKindFactory
from re_sharing.agreements.tests.factories import SepaMandateFactory
from re_sharing.agreements.tests.factories import pdf_file
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.resources.models import PermanentCode
from re_sharing.users.tests.factories import UserFactory


class AgreementAdminTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.staff)

    def test_creating_active_agreement_with_mandate_has_no_side_effects(self):
        kind = MembershipKindFactory()
        organization = OrganizationFactory(status=Organization.Status.CONFIRMED)
        organization.organization_groups.add(kind.organization_group)
        groups_before = set(organization.organization_groups.all())

        response = self.client.post(
            reverse("admin:agreements_agreement_add"),
            {
                "organization": organization.id,
                "kind": kind.id,
                "status": Agreement.Status.ACTIVE,
                "amount": "60.00",
                "start_date": "2024-01-01",
                "contact_person_function": "Chair",
                "details": "{}",
                "signed_document": pdf_file(),
                "signed_on": "2023-12-01",
                "mandates_of_agreement-TOTAL_FORMS": "1",
                "mandates_of_agreement-INITIAL_FORMS": "0",
                "mandates_of_agreement-0-reference": "PAPER-0042",
                "mandates_of_agreement-0-account_holder": "Example e.V.",
                "mandates_of_agreement-0-iban": "DE89 3704 0044 0532 0130 00",
                "mandates_of_agreement-0-signed_on": "2023-12-01",
                "mandates_of_agreement-0-signed_document": pdf_file("m.pdf"),
                "collections_of_agreement-TOTAL_FORMS": "0",
                "collections_of_agreement-INITIAL_FORMS": "0",
            },
        )

        assert response.status_code == HTTPStatus.FOUND, response.content
        agreement = Agreement.objects.get(organization=organization)
        mandate = SepaMandate.objects.get(agreement=agreement)
        assert agreement.status == Agreement.Status.ACTIVE
        assert mandate.reference == "PAPER-0042"
        assert mandate.iban == VALID_IBAN
        assert mandate.is_active
        assert len(mail.outbox) == 0
        assert set(organization.organization_groups.all()) == groups_before
        assert not PermanentCode.objects.filter(organization=organization).exists()

    def test_duplicate_mandate_reference_rejected(self):
        existing = SepaMandateFactory(reference="PAPER-1")
        agreement = AgreementFactory()

        response = self.client.post(
            reverse("admin:agreements_sepamandate_add"),
            {
                "agreement": agreement.id,
                "reference": existing.reference,
                "account_holder": "X",
                "iban": VALID_IBAN,
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert "reference" in response.context["adminform"].form.errors

    def test_invalid_iban_rejected(self):
        agreement = AgreementFactory()

        response = self.client.post(
            reverse("admin:agreements_sepamandate_add"),
            {
                "agreement": agreement.id,
                "reference": "PAPER-2",
                "account_holder": "X",
                "iban": "DE00370400440532013000",
            },
        )

        assert "iban" in response.context["adminform"].form.errors

    def test_lists_render(self):
        SepaMandateFactory()
        for name in [
            "agreement",
            "agreementkind",
            "sepamandate",
            "collection",
            "collectionrun",
            "unmatchedreturn",
            "syncstate",
        ]:
            response = self.client.get(reverse(f"admin:agreements_{name}_changelist"))
            assert response.status_code == HTTPStatus.OK, name

    def test_mandate_list_masks_iban(self):
        SepaMandateFactory(iban=VALID_IBAN)

        response = self.client.get(reverse("admin:agreements_sepamandate_changelist"))

        assert VALID_IBAN not in response.content.decode()

    def test_change_page_shows_group_presence(self):
        agreement = AgreementFactory()

        response = self.client.get(
            reverse("admin:agreements_agreement_change", args=[agreement.id])
        )

        assert response.status_code == HTTPStatus.OK


class AgreementKindFieldAdminTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.staff)
        self.kind = MembershipKindFactory()
        self.url = reverse("admin:agreements_agreementkind_change", args=[self.kind.id])

    def _post(self, rows):
        data = {
            "name": self.kind.name,
            "slug": self.kind.slug,
            "organization_group": self.kind.organization_group_id,
            "billing_interval": self.kind.billing_interval,
            "notification_mode": self.kind.notification_mode,
            "collection_day": self.kind.collection_day,
            "collection_month": self.kind.collection_month,
            "intro_text": "",
            "is_active": "on",
            "accepting_applications": "on",
            "fields_of_kind-TOTAL_FORMS": len(rows),
            "fields_of_kind-INITIAL_FORMS": sum(1 for row in rows if "id" in row),
            "fields_of_kind-MIN_NUM_FORMS": 0,
            "fields_of_kind-MAX_NUM_FORMS": 1000,
        }
        for index, row in enumerate(rows):
            for name, value in row.items():
                data[f"fields_of_kind-{index}-{name}"] = value
        return self.client.post(self.url, data)

    def test_add_field_inline(self):
        response = self._post(
            [
                {
                    "order": 1,
                    "key": "room",
                    "label": "Room",
                    "field_type": AgreementKindField.FieldType.TEXT,
                    "required": "on",
                    "is_active": "on",
                }
            ]
        )

        assert response.status_code == HTTPStatus.FOUND, response.content
        assert self.kind.fields_of_kind.get().key == "room"

    def _existing_row(self, field, **overrides):
        row = {
            "id": field.id,
            "kind": self.kind.id,
            "order": field.order,
            "key": "changed",
            "label": field.label,
            "field_type": field.field_type,
            "required": "on",
            "is_active": "on",
        }
        row.update(overrides)
        return row

    def test_key_read_only_on_existing_field(self):
        field = AgreementKindFieldFactory(kind=self.kind, key="room")

        response = self._post([self._existing_row(field, label="Office")])

        assert response.status_code == HTTPStatus.FOUND, response.content
        field.refresh_from_db()
        assert (field.key, field.label) == ("room", "Office")

    def test_answered_field_cannot_be_deleted(self):
        field = AgreementKindFieldFactory(kind=self.kind, key="room", label="Room")
        AgreementFactory(kind=self.kind, details={"room": "2.01"})

        response = self._post([self._existing_row(field, DELETE="on")])

        assert response.status_code == HTTPStatus.OK
        assert "has answers and cannot be deleted" in response.content.decode()
        assert AgreementKindField.objects.filter(id=field.id).exists()

    def test_unanswered_field_can_be_deleted(self):
        field = AgreementKindFieldFactory(kind=self.kind, key="room")
        AgreementFactory(kind=self.kind, details={"other": "x"})

        response = self._post([self._existing_row(field, DELETE="on")])

        assert response.status_code == HTTPStatus.FOUND, response.content
        assert not AgreementKindField.objects.filter(id=field.id).exists()


class AdminDeleteRulesTest(TestCase):
    def setUp(self):
        self.staff = UserFactory(is_staff=True, is_superuser=True)
        self.client.force_login(self.staff)

    def test_kind_in_use_cannot_be_deleted(self):
        kind = MembershipKindFactory()
        unused = MembershipKindFactory()
        AgreementFactory(kind=kind)

        in_use = self.client.get(
            reverse("admin:agreements_agreementkind_delete", args=[kind.id])
        )
        free = self.client.get(
            reverse("admin:agreements_agreementkind_delete", args=[unused.id])
        )

        assert in_use.status_code == HTTPStatus.FORBIDDEN
        assert free.status_code == HTTPStatus.OK

    def test_only_untouched_submitted_agreements_can_be_deleted(self):
        submitted = AgreementFactory()
        active = AgreementFactory(status=Agreement.Status.ACTIVE)
        with_collection = CollectionFactory(
            agreement=AgreementFactory(status=Agreement.Status.SUBMITTED)
        ).agreement

        def status(agreement):
            url = reverse("admin:agreements_agreement_delete", args=[agreement.id])
            return self.client.get(url).status_code

        assert status(submitted) == HTTPStatus.OK
        assert status(active) == HTTPStatus.FORBIDDEN
        assert status(with_collection) == HTTPStatus.FORBIDDEN
