"""Shared builders for the contract-module tests (not collected by pytest —
no ``test_`` prefix). Seed a BrightPath draft from the committed fixture, and
promote it to a deployable state with test-only counterparty + attestation."""
import datetime
import os

from django.core.management import call_command

from apps.courses.models import PartnerOrganisation
from apps.scholarship import contracts
from apps.scholarship.models import Programme

FIXTURE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'fixtures', 'brightpath_contract_v1.json',
)


def brightpath_org():
    # Seeded by migration 0098 into every test DB.
    return PartnerOrganisation.objects.get(code='brightpath')


def flagship():
    """The flagship gift — seeded by migration 0119 into every test DB. Since TD-229 a template
    is written for ONE gift, and the BrightPath fixture is the flagship's."""
    return Programme.objects.get(code='brightpath-flagship')


def seed_draft(version='2026-v1', programme='brightpath-flagship'):
    """Seed a DRAFT template from the committed fixture via the seed command, for the gift
    ``programme`` (a code; the flagship by default)."""
    call_command('seed_contract_template', org='brightpath', programme=programme,
                 template_version=version, fixture=FIXTURE, verbosity=0)
    return contracts.ContractTemplate.objects.get(
        organisation=brightpath_org(), version=version)


def make_deployable(version='2026-v1', programme='brightpath-flagship'):
    """A draft that passes validate_for_deployment: fixture + test-only
    counterparty NRIC (never committed) + a recorded vetting attestation."""
    template = seed_draft(version, programme)
    contracts.update_config(
        template,
        counterparty_name='Test Signatory',
        counterparty_nric='000000-00-0000',   # test-only, never in the fixture
    )
    contracts.record_vetting(
        template,
        vetted_by_name='Test Lawyer',
        vetted_on=datetime.date(2026, 7, 1),
        attested_by_email='admin@example.com',
    )
    return template
