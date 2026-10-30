"""Source sign-in S4 (2026-10-30): a source WITNESSES the bursary contract from its console.

`GET admin/source/applications/<id>/agreement/` (the full contract, to the witness source only),
`POST …/witness/` (it records its witness), the super's fallback (`AdminBursaryWitnessView`), the
witness emails' button rule (`source_witness.console_link`) and the PDF's witness name.

THE DOORS INTO "WITNESSED" (roadmap, S4): the source's POST, the super's POST, a second POST (either
side, and a stale copy under the lock), an override moved AFTER the source opened the page, a revoked
user, a switched-off source, an agreement the guarantor has not signed, an application whose contract
is no longer live, and agreements switched off. Each is a test below.

`bursary._regenerate_artefact` (the PDF re-render) is patched in the view tests: these agreements
carry no contract template, and the re-render has its own tests (`test_bursary_agreement.py`, and
`TestThePdfNamesTheWitness` here). Everything else after `record_witness` runs for real.
"""
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import bursary, source_console, source_witness
from apps.scholarship.models import BursaryAgreement, ScholarshipApplication
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_cohort, make_org,
    make_programme, make_source,
)
from apps.scholarship.tests.test_source_console import never_keys

APPS = '/api/v1/admin/source/applications/'
OVERVIEW = '/api/v1/admin/source/overview/'


def agreement_url(app):
    return f'{APPS}{app.pk}/agreement/'


def witness_url(app):
    return f'{APPS}{app.pk}/witness/'


def super_witness_url(app):
    return f'/api/v1/admin/scholarship/applications/{app.pk}/bursary-agreement/witness/'


#: Exactly what the agreement GET serves.
AGREEMENT_KEYS = {'status', 'student_signed_at', 'guarantor_signed_at', 'witness_signed_at',
                  'foundation_signed_at', 'witness_is_you', 'can_witness', 'application_id',
                  'student_name', 'pdf_url', 'pdf_expires_in', 'rendered'}

GOOD = {'witness_name': '  Puan Kala Devi ', 'confirm': True}


class _Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org()
        cohort = make_cohort(programme=make_programme(organisation=cls.org))
        cls.source = make_source(organisation=cls.org, contact_email='kala@src.test',
                                 contact_person='Puan Kala')
        cls.other = make_source(organisation=cls.org, contact_email='other@src.test')
        cls.user = make_admin('source_partner', owning_org=cls.org, source=cls.source,
                              name='Kala Devi', first_seen_at=timezone.now())
        signed = timezone.now() - timedelta(days=5)

        def app(stage='awarded', *, source=None, agreement='binds', **kw):
            a = make_application(stage, cohort=cohort, source=source or cls.source, **kw)
            if agreement is None:
                return a
            fields = {'student_signed_at': signed}
            if agreement in ('binds', 'countersigned'):
                fields['guarantor_signed_at'] = signed
            if agreement == 'countersigned':
                fields['foundation_signed_at'] = signed
            BursaryAgreement.objects.create(
                application=a, version='2026-v1', student_signed_name='Stu', guarantor_name='Guar',
                pdf_storage_path=f'{cls.org.pk}/{a.pk}/bursary_agreement.pdf', **fields)
            return a

        cls.ready = app()                                         # waits for OUR witness
        cls.unsigned = app(agreement='student')                   # the guarantor has not signed
        cls.no_agreement = app(agreement=None)
        cls.witness_only = app(source=cls.other, witness_org=cls.source)   # C14: ours by override
        cls.elsewhere = app(witness_org=cls.other)                # our student, ANOTHER's witness
        cls.countersigned = app('active', agreement='countersigned')   # the Foundation signed first
        cls.dead = app('closed')                                  # the contract is no longer live

    def setUp(self):
        self.client = authed_client(self.user)
        render = patch('apps.scholarship.bursary._regenerate_artefact')
        render.start()
        self.addCleanup(render.stop)
        mail.outbox = []

    def agreement(self, app):
        return BursaryAgreement.objects.get(application=app)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheAgreement(_Fixture):
    def test_the_witness_source_reads_the_contract(self):
        resp = self.client.get(agreement_url(self.ready))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(set(body), AGREEMENT_KEYS)
        self.assertEqual((body['status'], body['witness_is_you'], body['can_witness'],
                          body['pdf_url'], body['pdf_expires_in'], body['rendered'],
                          body['application_id']),
                         ('binds', True, True, None, 300, False, self.ready.pk))
        # The PDF link is the ONE key past the console's never-list, by the owner's ruling.
        self.assertEqual(never_keys(body), ['.pdf_url', '.pdf_expires_in'])

    def test_the_pdf_link_is_minted_only_on_a_click_for_five_minutes(self):
        with patch('apps.scholarship.storage.create_signed_download_url',
                   return_value='https://signed.example/x.pdf') as sign:
            self.assertIsNone(self.client.get(agreement_url(self.ready)).json()['pdf_url'])
            sign.assert_not_called()
            body = self.client.get(agreement_url(self.ready), {'link': '1'}).json()
        self.assertEqual(body['pdf_url'], 'https://signed.example/x.pdf')
        sign.assert_called_once_with(f'{self.org.pk}/{self.ready.pk}/bursary_agreement.pdf',
                                     expires_in=300)

    def test_a_case_witnessed_by_override_is_readable(self):
        resp = self.client.get(agreement_url(self.witness_only))
        self.assertEqual((resp.status_code, resp.json()['can_witness']), (200, True))

    def test_before_the_witness_step_or_not_the_witness_it_is_404(self):
        for app in (self.unsigned, self.no_agreement, self.elsewhere):
            self.assertEqual(self.client.get(agreement_url(app)).status_code, 404, app.pk)

    def test_after_witnessing_it_stays_readable(self):
        self.client.post(witness_url(self.ready), GOOD, format='json')
        body = self.client.get(agreement_url(self.ready)).json()
        self.assertEqual((body['can_witness'], body['witness_is_you']), (False, True))
        self.assertIsNotNone(body['witness_signed_at'])

    def test_a_dead_contract_nobody_witnessed_is_404(self):
        # Review L1: before a witness, the contract is shown only while it is live (`can_witness`).
        self.assertEqual(self.client.get(agreement_url(self.dead)).status_code, 404)

    def test_agreements_off_is_404(self):
        with self.settings(BURSARY_AGREEMENT_ENABLED=False):
            self.assertEqual(self.client.get(agreement_url(self.ready)).status_code, 404)

    def test_another_source_and_staff(self):
        other = authed_client(make_admin('source_partner', owning_org=self.org, source=self.other))
        # The applicant's OWN source that is not the witness: its student, but not its contract.
        self.assertEqual(other.get(agreement_url(self.witness_only)).status_code, 404)
        self.assertEqual(other.get(agreement_url(self.ready)).status_code, 404)
        # …and the case it witnesses by override IS its to read (our student, its contract).
        self.assertEqual(other.get(agreement_url(self.elsewhere)).status_code, 200)
        for staff in (make_admin('super', super_admin=True),
                      make_admin('org_admin', owning_org=self.org)):
            self.assertEqual(authed_client(staff).get(agreement_url(self.ready)).status_code, 403)

    def test_reading_has_no_side_effects(self):
        before = self.agreement(self.ready).updated_at
        self.client.get(agreement_url(self.ready), {'link': '1'})
        self.assertEqual(self.agreement(self.ready).updated_at, before)
        self.assertEqual(mail.outbox, [])


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheSourceWitnesses(_Fixture):
    def test_it_records_the_typed_name_the_user_the_ip_and_the_chain_runs(self):
        with patch.object(bursary, '_notify_foundation_countersign_pending') as nudge:
            resp = self.client.post(witness_url(self.ready), GOOD, format='json',
                                    REMOTE_ADDR='203.0.113.9')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.json()), AGREEMENT_KEYS)
        self.assertEqual(resp.json()['can_witness'], False)
        ag = self.agreement(self.ready)
        self.assertEqual((ag.witness_name, ag.witness_signed_by, ag.witness_org_id,
                          ag.witness_admin_id, ag.witness_ip),
                         ('Puan Kala Devi', 'Kala Devi', self.source.pk, self.user.pk,
                          '203.0.113.9'))
        self.assertIsNotNone(ag.witness_signed_at)
        nudge.assert_called_once()          # the Foundation is next — unchanged

    def test_when_the_foundation_signed_first_the_witness_executes_and_distributes(self):
        with patch.object(bursary, 'distribute_executed_agreement') as distribute:
            resp = self.client.post(witness_url(self.countersigned), GOOD, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'executed')
        distribute.assert_called_once()

    def test_a_second_post_is_409_and_records_nothing_more(self):
        with patch.object(bursary, '_notify_foundation_countersign_pending') as nudge:
            self.assertEqual(self.client.post(witness_url(self.ready), GOOD,
                                              format='json').status_code, 200)
            first = self.agreement(self.ready)
            resp = self.client.post(witness_url(self.ready),
                                    {'witness_name': 'Someone Else', 'confirm': True},
                                    format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'already_witnessed'))
        again = self.agreement(self.ready)
        self.assertEqual((again.witness_name, again.witness_signed_at),
                         (first.witness_name, first.witness_signed_at))
        nudge.assert_called_once()

    def test_the_lock_refuses_a_stale_copy(self):
        """Two clicks at once: both views read "not witnessed"; the second must still lose. Its copy
        is stale, so `record_once` must re-read under the row lock, never trust the caller's."""
        stale = self.agreement(self.ready)
        source_witness.record_once(self.agreement(self.ready), org=self.source, by_name='A',
                                   witness_name='First')
        with self.assertRaises(source_witness.AlreadyWitnessed):
            source_witness.record_once(stale, org=self.source, by_name='B', witness_name='Second')
        self.assertEqual(self.agreement(self.ready).witness_name, 'First')

    def test_the_body_refusals(self):
        cases = (({}, 'confirm_required'),
                 ({'witness_name': 'Kala', 'confirm': 'true'}, 'confirm_required'),
                 ({'witness_name': 'Kala', 'confirm': 1}, 'confirm_required'),
                 ({'witness_name': 'Kala'}, 'confirm_required'),
                 ({'witness_name': '   ', 'confirm': True}, 'name_required'),
                 ({'witness_name': 42, 'confirm': True}, 'bad_request'),      # review L3
                 ({'witness_name': 'K' * 201, 'confirm': True}, 'name_too_long'))
        for body, code in cases:
            resp = self.client.post(witness_url(self.ready), body, format='json')
            self.assertEqual((resp.status_code, resp.json()['code']), (400, code), body)
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)
        # The column's width is allowed.
        resp = self.client.post(witness_url(self.ready),
                                {'witness_name': 'K' * 200, 'confirm': True}, format='json')
        self.assertEqual(resp.status_code, 200)

    def test_not_ready_and_not_live(self):
        for app in (self.unsigned, self.no_agreement):
            resp = self.client.post(witness_url(app), GOOD, format='json')
            self.assertEqual((resp.status_code, resp.json()['code']), (400, 'not_ready'), app.pk)
        resp = self.client.post(witness_url(self.dead), GOOD, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'contract_not_live'))
        for app in (self.unsigned, self.dead):
            self.assertIsNone(self.agreement(app).witness_signed_at)

    def test_not_the_witness_is_404(self):
        resp = self.client.post(witness_url(self.elsewhere), GOOD, format='json')
        self.assertEqual(resp.status_code, 404)
        self.assertIsNone(self.agreement(self.elsewhere).witness_signed_at)

    def test_an_override_moved_after_the_page_opened_takes_the_case_away(self):
        self.assertEqual(self.client.get(agreement_url(self.ready)).status_code, 200)
        ScholarshipApplication.objects.filter(pk=self.ready.pk).update(witness_org=self.other)
        self.assertEqual(self.client.post(witness_url(self.ready), GOOD,
                                          format='json').status_code, 404)
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)
        # And the witness-only case: moved away, it leaves this source's scope altogether.
        ScholarshipApplication.objects.filter(pk=self.witness_only.pk).update(witness_org=None)
        self.assertEqual(self.client.post(witness_url(self.witness_only), GOOD,
                                          format='json').status_code, 404)

    def test_a_revoked_user_or_a_switched_off_source_is_refused(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertEqual(self.client.post(witness_url(self.ready), GOOD,
                                          format='json').status_code, 403)
        self.user.is_active = True
        self.user.save(update_fields=['is_active'])
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        resp = self.client.post(witness_url(self.ready), GOOD, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (403, 'source_unavailable'))
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)

    def test_agreements_off_is_404(self):
        with self.settings(BURSARY_AGREEMENT_ENABLED=False):
            self.assertEqual(self.client.post(witness_url(self.ready), GOOD,
                                              format='json').status_code, 404)
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)

    def test_staff_may_not_use_the_source_door(self):
        for staff in (make_admin('super', super_admin=True),
                      make_admin('org_admin', owning_org=self.org)):
            self.assertEqual(authed_client(staff).post(witness_url(self.ready), GOOD,
                                                       format='json').status_code, 403)
        self.assertIsNone(self.agreement(self.ready).witness_signed_at)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestTheSuperFallback(_Fixture):
    def setUp(self):
        super().setUp()
        self.super = authed_client(make_admin('super', super_admin=True))

    def test_a_super_still_records_even_when_the_source_can_sign_in(self):
        self.assertTrue(source_witness.has_console(self.source))
        resp = self.super.post(super_witness_url(self.ready), {'witness_name': 'Encik Raj'},
                               format='json')
        self.assertEqual(resp.status_code, 200)
        ag = self.agreement(self.ready)
        self.assertEqual((ag.witness_name, ag.witness_admin_id, ag.witness_ip),
                         ('Encik Raj', None, None))
        # …and then the source's own door is closed.
        resp = self.client.post(witness_url(self.ready), GOOD, format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'already_witnessed'))

    def test_a_super_cannot_record_over_a_source(self):
        self.client.post(witness_url(self.ready), GOOD, format='json')
        resp = self.super.post(super_witness_url(self.ready), {'witness_name': 'Encik Raj'},
                               format='json')
        self.assertEqual((resp.status_code, resp.json()['code']), (409, 'already_witnessed'))
        ag = self.agreement(self.ready)
        self.assertEqual((ag.witness_name, ag.witness_admin_id), ('Puan Kala Devi', self.user.pk))

    def test_a_super_cannot_record_twice(self):
        self.super.post(super_witness_url(self.ready), {'witness_name': 'One'}, format='json')
        resp = self.super.post(super_witness_url(self.ready), {'witness_name': 'Two'},
                               format='json')
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.agreement(self.ready).witness_name, 'One')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestOnePredicate(_Fixture):
    """The Overview's `witness_waiting`, the detail's `contract.can_witness` and the agreement's
    `can_witness` are ONE predicate (`source_console.can_witness`) and agree on every case."""

    def test_they_agree_on_every_case(self):
        waiting = {row['application_id']
                   for row in self.client.get(OVERVIEW).json()['witness_waiting']}
        self.assertEqual(waiting, {self.ready.pk, self.witness_only.pk, self.countersigned.pk})
        for app in (self.ready, self.unsigned, self.no_agreement, self.witness_only,
                    self.elsewhere, self.countersigned, self.dead):
            detail = self.client.get(f'{APPS}{app.pk}/').json()
            contract = detail['contract']
            self.assertEqual(bool(contract and contract['can_witness']), app.pk in waiting, app.pk)
            got = self.client.get(agreement_url(app))
            if got.status_code == 200:
                self.assertEqual(got.json()['can_witness'], app.pk in waiting, app.pk)
            else:
                self.assertNotIn(app.pk, waiting)

    def test_witnessing_takes_it_off_the_overview(self):
        self.client.post(witness_url(self.ready), GOOD, format='json')
        waiting = {row['application_id']
                   for row in self.client.get(OVERVIEW).json()['witness_waiting']}
        self.assertNotIn(self.ready.pk, waiting)


@override_settings(BURSARY_AGREEMENT_ENABLED=True, FRONTEND_URL='https://halatuju.test')
class TestTheWitnessEmails(_Fixture):
    """The button rule: a witness email sends the source to its console only when somebody there
    can sign in (`source_witness.has_console`); otherwise it asks them to reply, as before."""

    def setUp(self):
        super().setUp()
        self.link = f'https://halatuju.test/admin/scholarship/{self.ready.pk}'

    def _witness_mail(self):
        msgs = [m for m in mail.outbox if m.to == ['kala@src.test']]
        self.assertEqual(len(msgs), 1)
        msg = msgs[0]
        return msg.body, msg.alternatives[0][0]

    def test_the_first_ask_has_the_button_when_the_source_can_sign_in(self):
        bursary.notify_after_guarantor_signed(self.ready)
        text, html = self._witness_mail()
        self.assertIn(self.link, text)
        self.assertIn('Sign in to HalaTuju', text)
        self.assertIn('Open the agreement', html)
        self.assertIn(self.link, html)
        self.assertNotIn('reply to this email', text.lower())

    def test_no_signed_in_user_keeps_the_reply_wording(self):
        self.user.first_seen_at = None
        self.user.save(update_fields=['first_seen_at'])
        bursary.notify_after_guarantor_signed(self.ready)
        text, html = self._witness_mail()
        self.assertIn('reply to this email', text.lower())
        self.assertNotIn('/admin/scholarship', text + html)

    def test_a_switched_off_source_or_a_revoked_user_gets_no_button(self):
        self.source.is_active = False
        self.source.save(update_fields=['is_active'])
        self.assertFalse(source_witness.has_console(self.source))
        self.source.is_active = True
        self.source.save(update_fields=['is_active'])
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        self.assertFalse(source_witness.has_console(self.source))
        bursary.notify_after_guarantor_signed(self.ready)
        text, _html = self._witness_mail()
        self.assertNotIn('/admin/scholarship', text)

    def test_the_reminder_follows_the_same_rule(self):
        out = bursary.send_signing_reminders()
        self.assertGreaterEqual(out['witness'], 1)
        msgs = [m for m in mail.outbox if m.to == ['kala@src.test']
                and self.link in m.body]
        self.assertEqual(len(msgs), 1)

    def test_the_executed_copy_links_the_source_only_when_it_can_sign_in(self):
        ag = self.agreement(self.countersigned)
        link = f'https://halatuju.test/admin/scholarship/{self.countersigned.pk}'
        with patch('apps.scholarship.storage.download_object', return_value=b'%PDF'), \
                patch('apps.scholarship.sheets.write_contract_pdf', return_value=''):
            bursary.distribute_executed_agreement(ag)
            copy = [m for m in mail.outbox if m.to == ['kala@src.test']]
            self.assertEqual(len(copy), 1)
            self.assertIn(link, copy[0].body)
            # Nobody at the source can sign in: the copy goes, without the link.
            self.user.first_seen_at = None
            self.user.save(update_fields=['first_seen_at'])
            mail.outbox = []
            BursaryAgreement.objects.filter(pk=ag.pk).update(executed_pdf_emailed_at=None)
            bursary.distribute_executed_agreement(self.agreement(self.countersigned))
        copy = [m for m in mail.outbox if m.to == ['kala@src.test']]
        self.assertEqual(len(copy), 1)
        self.assertNotIn('/admin/scholarship', copy[0].body)


class TestThePdfNamesTheWitness(TestCase):
    """The PDF's witness block names the WITNESS — the typed name, else its organisation — and never
    `witness_signed_by`, the officer who recorded it (the Contract tab's rule, decisions.md)."""

    def _render(self, witness):
        from apps.scholarship.tests.contract_helpers import seed_draft
        template = seed_draft('2026-pdf-witness')
        app = make_application('awarded', cohort=make_cohort(
            programme=make_programme(organisation=template.organisation)))
        p = {'award_amount': 3000, 'payment_schedule': 'x', 'institution_name': 'U',
             'course_name': 'N', 'commencement_date': None, 'progress_standard': 'Pass',
             'foundation_signatory_name': 'F', 'foundation_signatory_title': 't',
             'foundation_signatory_nric': ''}
        return bursary.render_agreement_html(
            app, p, student={'name': 'S', 'nric': 'x', 'signed_at': None},
            guarantor={'name': 'G', 'nric': 'y', 'relationship': 'father', 'signed_at': None},
            foundation={'name': 'F', 'title': 't', 'nric': '', 'signed_at': None},
            witness=witness, template=template)

    def test_a_source_recorded_witness_shows_the_typed_name(self):
        html = self._render({'name': 'Puan Kala Devi', 'by': 'Kala (source user)',
                             'org': 'Persatuan Kala', 'signed_at': timezone.now()})
        self.assertIn('Name: Puan Kala Devi', html)
        self.assertNotIn('Kala (source user)', html)

    def test_a_super_recorded_witness_never_shows_the_officer(self):
        html = self._render({'name': '', 'by': 'Officer Siva', 'org': 'Persatuan Kala',
                             'signed_at': timezone.now()})
        self.assertNotIn('Officer Siva', html)
        self.assertIn('Name: Persatuan Kala', html)

    def test_an_unsigned_witness_block_is_blank(self):
        html = self._render({'by': '', 'org': '', 'signed_at': None})
        self.assertIn('Name: &mdash;', html)

    def test_the_re_render_passes_the_typed_name(self):
        org = make_org()
        app = make_application('awarded', cohort=make_cohort(
            programme=make_programme(organisation=org)))
        ag = BursaryAgreement.objects.create(application=app, version='v1',
                                             student_signed_at=timezone.now(),
                                             guarantor_signed_at=timezone.now(),
                                             pdf_storage_path=f'{org.pk}/{app.pk}/a.pdf')
        with patch.object(bursary, 'render_agreement_html', return_value='<html/>') as render, \
                patch.object(bursary, 'generate_pdf', return_value=b'%PDF'), \
                patch('apps.scholarship.storage.upload_object'), \
                patch.object(bursary, '_notify_foundation_countersign_pending'):
            bursary.record_witness(ag, org=make_source(organisation=org), by_name='Officer',
                                   witness_name='Puan Kala Devi')
        witness = render.call_args.kwargs['witness']
        self.assertEqual((witness['name'], witness['by']), ('Puan Kala Devi', 'Officer'))


class TestSourceConsoleConstants(TestCase):
    def test_the_witness_statuses_are_real_statuses(self):
        statuses = {code for code, _label in ScholarshipApplication.STATUS_CHOICES}
        self.assertEqual(set(source_console.WITNESS_STATUSES) - statuses, set())

    def test_the_name_limit_is_the_columns(self):
        from apps.scholarship.views_admin.source_console import WITNESS_NAME_MAX
        self.assertEqual(WITNESS_NAME_MAX,
                         BursaryAgreement._meta.get_field('witness_name').max_length)
