"""TD-252 (the cron half) — `lapse_expired_offers` has a door and a schedule slot.

The function was written and tested in July and wired to NOTHING, so an award nobody answered
held the sponsor's money for ever. It now runs daily through `CronRunView` (`lapse-expired-offers`
→ the `lapse_expired_offers` command). The function's own rules are pinned in
`test_contract_golive_t1.TestLapseRework` and `test_sponsorship`; this file pins the wiring, the
revert to the pool, and that a paid application is never lapsed through the DOOR either.

⚠ Production on 2026-09-30: 31 armed offers past deadline, ALL with released money — so the job
lapses 0 and flags 31 every day. The refusals therefore log at INFO with ONE summary WARNING per
run, not 31 warnings a day; the returned `flagged` list is unchanged.
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import sponsorship as svc
from apps.scholarship.models import Disbursement, Sponsor, Sponsorship
from apps.scholarship.tests.factories import make_application, unique_suffix
from apps.scholarship.views import CronRunView


def _expired_offer(*, paid=False):
    app = make_application('awarded', award_amount=Decimal('3000'))
    sponsor = Sponsor.objects.create(
        supabase_user_id=unique_suffix('lap-sp-'), name='J', email=f'{unique_suffix("lap")}@x.test',
        phone='0', source='friend', consent_at=timezone.now(), status='approved')
    sp = Sponsorship.objects.create(
        application=app, sponsor=sponsor, amount=Decimal('3000'), status='offered',
        accept_deadline=timezone.now() - timedelta(days=2))
    if paid:
        Disbursement.objects.create(application=app, amount=Decimal('200'), status='released',
                                    sequence=1, released_at=timezone.now())
    return app, sp


class LapseExpiredOffersJobIsWiredTest(TestCase):
    def test_the_job_is_registered_under_its_slug(self):
        self.assertEqual(CronRunView.JOBS.get('lapse-expired-offers'), 'lapse_expired_offers')


class LapseExpiredOffersCommandTest(TestCase):
    def test_the_command_lapses_an_unpaid_offer_and_reverts_it_to_the_pool(self):
        app, sp = _expired_offer()
        out = StringIO()
        call_command('lapse_expired_offers', stdout=out)
        self.assertIn(f'lapse_expired_offers: lapsed=1 [{sp.id}] flagged=0 []', out.getvalue())
        sp.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(sp.status, 'lapsed')
        self.assertEqual(app.status, 'recommended')   # back in the discovery pool

    def test_a_paid_application_is_flagged_never_lapsed(self):
        app, sp = _expired_offer(paid=True)
        out = StringIO()
        call_command('lapse_expired_offers', stdout=out)
        self.assertIn(f'lapsed=0 [] flagged=1 [{app.id}]', out.getvalue())
        sp.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(sp.status, 'offered')
        self.assertEqual(app.status, 'awarded')

    def test_a_standing_set_of_paid_offers_raises_ONE_warning_per_run(self):
        paid = [_expired_offer(paid=True)[0].id for _ in range(3)]
        with self.assertLogs('apps.scholarship.sponsorship', level='INFO') as cm:
            result = svc.lapse_expired_offers()
        self.assertEqual(result['lapsed'], 0)
        self.assertEqual(sorted(result['flagged']), sorted(paid))   # the list is unchanged
        warnings = [r for r in cm.records if r.levelname == 'WARNING']
        self.assertEqual(len(warnings), 1, cm.output)
        self.assertIn('3 expired offer(s) REFUSED', warnings[0].getMessage())
        self.assertEqual(sum(1 for r in cm.records if r.levelname == 'INFO'
                             and 'REFUSED to lapse app' in r.getMessage()), 3)

    def test_an_offer_accepted_mid_sweep_is_left_alone(self):
        """Review F4: the candidate list is read first and lapsed later. An acceptance landing in
        between must win — the row is re-read under a lock and lapsed only if still 'offered'
        with the same deadline."""
        from unittest.mock import patch
        app, sp = _expired_offer()
        real = svc._expired_offers

        def read_then_accept(now):
            rows = real(now)
            Sponsorship.objects.filter(pk=sp.pk).update(status='active')   # the student accepts
            return rows

        with patch.object(svc, '_expired_offers', side_effect=read_then_accept):
            result = svc.lapse_expired_offers()
        self.assertEqual(result, {'lapsed': 0, 'flagged': []})
        sp.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(sp.status, 'active')
        self.assertEqual(app.status, 'awarded')   # not reverted to the pool

    def test_each_lapse_logs_its_ids_and_the_command_prints_them(self):
        app, sp = _expired_offer()
        out = StringIO()
        with self.assertLogs('apps.scholarship.sponsorship', level='INFO') as cm:
            call_command('lapse_expired_offers', stdout=out)
        self.assertIn(f'lapse_expired_offers: LAPSED sponsorship {sp.id} (app {app.id})',
                      '\n'.join(cm.output))
        self.assertIn(f'lapsed=1 {[sp.id]} flagged=0 []', out.getvalue())

    def test_a_second_run_is_a_no_op(self):
        _expired_offer()
        self.assertEqual(svc.lapse_expired_offers()['lapsed'], 1)
        self.assertEqual(svc.lapse_expired_offers(), {'lapsed': 0, 'flagged': []})


@override_settings(ROOT_URLCONF='halatuju.urls', CRON_SECRET='test-cron-secret')
class LapseExpiredOffersThroughTheCronDoorTest(TestCase):
    def test_the_cron_endpoint_runs_it(self):
        app, sp = _expired_offer(paid=True)
        r = self.client.post('/api/v1/internal/cron/lapse-expired-offers/',
                             HTTP_X_CRON_SECRET='test-cron-secret')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()['job'], 'lapse-expired-offers')
        self.assertIn('lapsed=0 [] flagged=1', r.json()['output'])
        sp.refresh_from_db()
        self.assertEqual(sp.status, 'offered')   # through the door too: paid money is never lapsed
