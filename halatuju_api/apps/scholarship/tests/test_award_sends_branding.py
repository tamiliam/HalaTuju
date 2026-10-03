"""TD-169 review F3 (2026-10-03): every PRODUCTION caller of the two guide-carrying sends passes
the owning tenant's branding — not only the send functions themselves.

The org-2 leak test (`test_email_branding.py`) proves a send renders the brand it is GIVEN. It
cannot see a caller that gives none, and all four production callers gave none: the award release
cron, the award-email command, the execution-time Vircle setup and the Vircle-email command. Each
is driven here with the send patched at the name the caller reads, and the branding it passed is
asked its programme name. A BrightPath control proves the platform still resolves to itself.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import bursary
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import Donation, Sponsorship
from apps.scholarship.tests.factories import (make_application, make_cohort, make_org,
                                              make_programme)
from apps.scholarship.tests.test_sponsorship import _fundable_app, _sponsor

TENANT = 'Inspire Grant'


def _tenant_cohort():
    org = make_org(code='td169-inspire', programme_name_en=TENANT)
    return make_cohort(programme=make_programme(organisation=org))


def _brand_name(send_mock):
    assert send_mock.called, 'the send was never reached'
    return send_mock.call_args.kwargs['branding'].programme_name('en')


class AwardSendsTest(TestCase):
    def _held_award(self, cohort, age_hours=25):
        s = _sponsor(uid='td169-sponsor')
        Donation.objects.create(sponsor=s, amount=Decimal('5000'), programme=cohort.programme)
        app = _fundable_app(cohort, suffix='td169', award=Decimal('2000'))
        sp = svc.fund_student(s, app)
        Sponsorship.objects.filter(id=sp.id).update(
            offered_at=timezone.now() - timedelta(hours=age_hours))
        return app

    def test_the_release_cron_sends_in_the_tenants_brand(self):
        self._held_award(_tenant_cohort())
        with mock.patch('apps.scholarship.sponsorship.send_award_offer_email',
                        return_value=True) as send:
            svc.release_award_offer_emails()
        self.assertEqual(_brand_name(send), TENANT)

    def test_the_award_email_command_sends_in_the_tenants_brand(self):
        app = self._held_award(_tenant_cohort())
        target = ('apps.scholarship.management.commands.send_award_offer_emails.'
                  'send_award_offer_email')
        with override_settings(AWARD_EMAIL_APP_IDS=str(app.id)), \
                mock.patch(target, return_value=False) as send:
            call_command('send_award_offer_emails')
        self.assertEqual(_brand_name(send), TENANT)


class VircleSendsTest(TestCase):
    def test_execution_time_setup_sends_in_the_tenants_brand(self):
        app = make_application('awarded', cohort=_tenant_cohort())
        with mock.patch('apps.scholarship.emails.send_vircle_install_email',
                        return_value=False) as send:
            bursary.send_vircle_setup_at_execution(app)
        self.assertEqual(_brand_name(send), TENANT)

    def test_the_vircle_email_command_sends_in_the_tenants_brand(self):
        app = make_application('awarded', cohort=_tenant_cohort(), notify_email='s@x.test')
        target = ('apps.scholarship.management.commands.send_vircle_install_emails.'
                  'send_vircle_install_email')
        with override_settings(VIRCLE_EMAIL_APP_IDS=str(app.id)), \
                mock.patch(target, return_value=False) as send:
            call_command('send_vircle_install_emails')
        self.assertEqual(_brand_name(send), TENANT)

    def test_brightpath_still_resolves_to_the_platform(self):
        from apps.scholarship.branding import platform
        from apps.courses.models import PartnerOrganisation
        org = PartnerOrganisation.objects.get(code='brightpath')   # seeded by a migration
        app = make_application('awarded', cohort=make_cohort(programme=make_programme(organisation=org)))
        with mock.patch('apps.scholarship.emails.send_vircle_install_email',
                        return_value=False) as send:
            bursary.send_vircle_setup_at_execution(app)
        self.assertIs(send.call_args.kwargs['branding'], platform())
