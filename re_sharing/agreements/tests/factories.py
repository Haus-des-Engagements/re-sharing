from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from factory import Faker
from factory import LazyAttribute
from factory import Sequence
from factory import SubFactory
from factory import post_generation
from factory.django import DjangoModelFactory

from re_sharing.agreements.models import Agreement
from re_sharing.agreements.models import AgreementKind
from re_sharing.agreements.models import Collection
from re_sharing.agreements.models import CollectionRun
from re_sharing.agreements.models import SepaMandate
from re_sharing.organizations.models import Organization
from re_sharing.organizations.tests.factories import OrganizationFactory
from re_sharing.organizations.tests.factories import OrganizationGroupFactory

VALID_IBAN = "DE89370400440532013000"
PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def pdf_file(name="signed.pdf"):
    return SimpleUploadedFile(name, PDF_BYTES, content_type="application/pdf")


class AgreementKindFactory(DjangoModelFactory):
    name = Sequence(lambda n: f"Kind {n}")
    form_type = AgreementKind.FormType.COWORKING
    organization_group = SubFactory(OrganizationGroupFactory)
    billing_interval = AgreementKind.BillingInterval.MONTHLY
    notification_mode = AgreementKind.NotificationMode.EACH_COLLECTION
    collection_day = 5
    collection_month = None
    intro_text = "<p>Please download the contract.</p>"

    class Meta:
        model = AgreementKind
        skip_postgeneration_save = True

    @post_generation
    def accesses(self, create, extracted, **kwargs):
        if create and extracted:
            self.accesses.set(extracted)


class MembershipKindFactory(AgreementKindFactory):
    form_type = AgreementKind.FormType.MEMBERSHIP
    billing_interval = AgreementKind.BillingInterval.YEARLY
    notification_mode = AgreementKind.NotificationMode.ONCE_AT_APPROVAL
    collection_day = 15
    collection_month = 3


class AgreementFactory(DjangoModelFactory):
    organization = SubFactory(OrganizationFactory, status=Organization.Status.CONFIRMED)
    kind = SubFactory(AgreementKindFactory)
    status = Agreement.Status.SUBMITTED
    amount = Decimal("120.00")
    start_date = date(2027, 3, 1)
    contact_person_function = "Chair"
    details = LazyAttribute(lambda _: {})

    class Meta:
        model = Agreement
        skip_postgeneration_save = True

    @post_generation
    def with_signed_document(self, create, extracted, **kwargs):
        if create and extracted:
            self.signed_document = pdf_file()
            self.signed_on = self.start_date
            self.save()


class SepaMandateFactory(DjangoModelFactory):
    agreement = SubFactory(AgreementFactory)
    reference = Sequence(lambda n: f"RS-{n:06d}-1")
    account_holder = Faker("company", locale="de_DE")
    iban = VALID_IBAN
    bic = "COBADEFFXXX"
    bank_name = "Example Bank"
    signed_on = date(2027, 2, 1)
    signed_document = LazyAttribute(lambda _: pdf_file("mandate.pdf"))

    class Meta:
        model = SepaMandate


class CollectionRunFactory(DjangoModelFactory):
    collection_date = date(2027, 3, 5)

    class Meta:
        model = CollectionRun


class CollectionFactory(DjangoModelFactory):
    agreement = SubFactory(AgreementFactory, status=Agreement.Status.ACTIVE)
    kind = Collection.Kind.FEE
    period_start = date(2027, 3, 1)
    period_end = date(2027, 3, 31)
    due_date = date(2027, 3, 5)
    amount = Decimal("120.00")
    mandate = LazyAttribute(lambda o: SepaMandateFactory(agreement=o.agreement))
    status = Collection.Status.PLANNED
    reference = Sequence(lambda n: f"RS-C-{n:06d}")

    class Meta:
        model = Collection
