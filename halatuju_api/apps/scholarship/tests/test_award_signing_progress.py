"""Mobile M4 (owner ruling): the award page reads back what the student has ALREADY done towards
signing — the comprehension quiz on THIS template, and a still-valid parent PIN check — so a reload
(an iOS tab kill) does not make her retake the quiz or send the parent a second, paid SMS.

Each flag must be EXACTLY the rule `bursary.sign_agreement` enforces: if the page could skip a step
the server would then refuse, the student would be told "done" and then refused at the signature.
So every case below is asserted twice — the flag, and what signing actually does in that state.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.scholarship.signing_progress import signing_progress
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.tests.test_bursary_agreement import (
    GUARANTOR_NAME, GUARANTOR_NRIC, TEST_JWT_SECRET, _add_parent_ic, _fund, _fundable_app,
    _mock_seams, _token, _verify_guarantor_phone,
)


#: SHARED GOLDEN (TD-463): (monthly amount, payment count, first month, served parts, server English line).
#: The same cases sit in halatuju-web/src/lib/__tests__/a42Language.test.ts.
SCHEDULE_GOLDEN = [
    ('250.00', 12, 7, {'monthly_amount': '250', 'count': 12, 'start_month': 7, 'total': '3000'},
     'RM250 per month × 12 payments, starting July (total RM3000).'),
    ('250.50', 10, 3, {'monthly_amount': '250.50', 'count': 10, 'start_month': 3, 'total': '2505'},
     'RM250.50 per month × 10 payments, starting March (total RM2505).'),
    ('300.00', 8, 0, {'monthly_amount': '300', 'count': 8, 'start_month': 0, 'total': '2400'},
     'RM300 per month × 8 payments (total RM2400).'),
]


def _template(app):
    from apps.scholarship import contract_scope
    return contract_scope.template_for_application(app)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestAwardSigningProgress(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.client = APIClient()
        self.pdf, self.upload, self.dl = _mock_seams()
        for p in (self.pdf, self.upload, self.dl):
            p.start()
            self.addCleanup(p.stop)

    def _offered(self, suffix):
        app = _fundable_app(self.cohort, suffix=suffix)   # quiz passed on the active template
        _add_parent_ic(app)
        _fund(app)
        return app

    def _preview(self, app):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(app.profile.supabase_user_id)}')
        r = self.client.get('/api/v1/scholarship/award/')
        self.assertEqual(r.status_code, 200)
        return r.json()['bursary_preview']

    def _sign_refusal(self, app):
        """The code signing refuses with in this state, or '' when it signs."""
        try:
            svc.respond_to_award(app, action='accept', student_signed_name='Zxq Student',
                                 guarantor_name=GUARANTOR_NAME, guarantor_nric=GUARANTOR_NRIC,
                                 guarantor_relationship='mother')
        except svc.SponsorshipError as e:
            return e.code
        return ''

    # ── The quiz ──────────────────────────────────────────────────────────────

    def test_preview_serves_the_schedule_parts_beside_the_english_line(self):
        """TD-463: the web composes the schedule sentence from these parts in the reader's language;
        the English one-liner stays (it is what the signed agreement freezes)."""
        app = self._offered('sp0')
        prev = self._preview(app)
        parts = prev['payment_schedule_parts']
        self.assertEqual(set(parts), {'monthly_amount', 'count', 'start_month', 'total'})
        self.assertIsInstance(parts['count'], int)
        self.assertIn(f"RM{parts['monthly_amount']} per month", prev['payment_schedule'])
        self.assertIn(f"{parts['count']} payments", prev['payment_schedule'])
        self.assertIn(f"total RM{parts['total']}", prev['payment_schedule'])

    def test_preview_of_a_row_with_no_start_month(self):
        """TD-463 (G13 review): a row naming no first month serves start_month 0, and the English
        line has no starting clause, so the web takes its scheduleLineNoStart template."""
        from apps.scholarship import contracts
        from apps.scholarship.models import PaymentScheduleRow
        app = self._offered('sp0b')
        row = contracts.schedule_row_for(_template(app), app)
        PaymentScheduleRow.objects.filter(pk=row.pk).update(start_month=0)
        prev = self._preview(app)
        self.assertEqual(prev['payment_schedule_parts']['start_month'], 0)
        self.assertNotIn('starting', prev['payment_schedule'])
        self.assertTrue(prev['payment_schedule'].endswith(f"(total RM{prev['payment_schedule_parts']['total']})."))

    def test_parts_and_english_line_match_the_shared_golden(self):
        """TD-463 (G13 review): SHARED GOLDEN, the same cases are asserted in
        halatuju-web/src/lib/__tests__/a42Language.test.ts, where the English catalogue template is
        filled from the parts and must equal this server line, word for word. Change both together."""
        from decimal import Decimal
        from apps.scholarship import bursary
        from apps.scholarship.contracts import schedule_summary_text
        from apps.scholarship.models import PaymentScheduleRow
        for amount, offsets, start, parts, line in SCHEDULE_GOLDEN:
            with self.subTest(line=line):
                row = PaymentScheduleRow(pathway='default', monthly_amount=Decimal(amount),
                                         start_month=start, paid_offsets=list(range(offsets)))
                self.assertEqual(schedule_summary_text(row, 'en'), line)
                with patch('apps.scholarship.contracts.schedule_row_for', return_value=row):
                    self.assertEqual(bursary.payment_schedule_parts(None, None), parts)

    def test_quiz_passed_on_this_template_is_read_back(self):
        app = self._offered('sp1')
        self.assertTrue(self._preview(app)['comprehension_passed'])

    def test_quiz_not_taken_reads_false_and_signing_agrees(self):
        app = self._offered('sp2')
        app.comprehension_template = None
        app.comprehension_passed_at = None
        app.save(update_fields=['comprehension_template', 'comprehension_passed_at'])
        self.assertFalse(self._preview(app)['comprehension_passed'])
        _verify_guarantor_phone(app)
        self.assertEqual(self._sign_refusal(app), 'comprehension_stale')

    def test_quiz_passed_on_an_older_template_reads_false(self):
        """A redeploy between the quiz and the signature: the stamp is for another version."""
        app = self._offered('sp3')
        tpl = _template(app)
        with patch.object(app, 'comprehension_template_id', tpl.id + 999):
            self.assertFalse(signing_progress(app, tpl)['comprehension_passed'])
        self.assertFalse(signing_progress(app, None)['comprehension_passed'])

    # ── The parent PIN ────────────────────────────────────────────────────────

    def test_no_pin_check_reads_false_and_signing_agrees(self):
        app = self._offered('sp4')
        self.assertFalse(self._preview(app)['guarantor_phone_verified'])
        self.assertEqual(self._sign_refusal(app), 'guarantor_phone_unverified')

    def test_fresh_pin_check_on_the_number_on_file_reads_true_and_signs(self):
        app = self._offered('sp5')
        _verify_guarantor_phone(app)
        self.assertTrue(self._preview(app)['guarantor_phone_verified'])
        self.assertEqual(self._sign_refusal(app), '')

    @override_settings(GUARANTOR_PHONE_VERIFY_TTL_SECONDS=1800)
    def test_pin_check_expires_with_the_signing_window(self):
        app = self._offered('sp6')
        _verify_guarantor_phone(app, when=timezone.now() - timedelta(seconds=1801))
        self.assertFalse(self._preview(app)['guarantor_phone_verified'])
        self.assertEqual(self._sign_refusal(app), 'guarantor_phone_unverified')

    def test_pin_check_for_a_number_since_corrected_reads_false(self):
        """Request #26: an admin corrected the parent's number after the PIN went out."""
        app = self._offered('sp7')
        _verify_guarantor_phone(app)
        app.profile.guardians = [{'name': GUARANTOR_NAME, 'phone': '019-8887777'}]
        app.profile.save(update_fields=['guardians'])
        self.assertFalse(self._preview(app)['guarantor_phone_verified'])
        self.assertEqual(self._sign_refusal(app), 'guarantor_phone_changed')

    def test_no_number_on_file_reads_false(self):
        app = self._offered('sp8')
        _verify_guarantor_phone(app)
        app.profile.guardians = []
        app.profile.save(update_fields=['guardians'])
        self.assertFalse(self._preview(app)['guarantor_phone_verified'])

    def test_the_flags_carry_no_number_and_no_timestamp(self):
        """Read-only booleans: the page never learns the parent's number or when the PIN was checked."""
        app = self._offered('sp9')
        _verify_guarantor_phone(app)
        flags = signing_progress(app, _template(app))
        self.assertEqual(set(flags), {'comprehension_passed', 'guarantor_phone_verified'})
        self.assertTrue(all(isinstance(v, bool) for v in flags.values()))
