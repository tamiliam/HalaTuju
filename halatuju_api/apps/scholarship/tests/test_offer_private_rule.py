"""IPTS offers (owner 2026-11-18, `offer_private`): an offer from a private college / university or a
public university's private wing turns Pathway red with `pathway_offer_private`, a confident
disqualifier. Flag only (no submit block, the amount unchanged); reviewers only (no student ticket).
A public place is never flagged for a gap in our lists, and a letter we cannot classify is unchanged.
Every letter here is invented.
"""
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.courses.models import Institution
from apps.scholarship import award, offer_private
from apps.scholarship.genuineness.offer_issuers import private_college_reason
from apps.scholarship.genuineness.offer_rulings import ruled_offer
from apps.scholarship.genuineness.results_doc import MODEL_VERSION, baseline_genuineness
from apps.scholarship.models import ApplicantDocument, ScholarshipCohort
from apps.scholarship.resolution import CODE_TO_TICKET
from apps.scholarship.services.consent_blockers import consent_blockers
from apps.scholarship.tests.factories import make_application, make_student
from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION, build_verdict

CODE = 'pathway_offer_private'
S6_REASON = ('[S6 ruling: private_offer] private college / university (IPTS): company on the letterhead - '
             'not a supported public offer (owner rulings 2 + 7)')
COLLEGE_REASON = ('private college / university (IPTS) - not a supported public issuer (nearest pattern '
                  'polytechnic, p=0.50)')
ARM_REASON = ('private / continuing-education arm (SPACE / Pendidikan Berterusan / Saluran Terbuka (SATU) / '
              'Sdn Bhd) — an IPTS option, not a supported public offer')


def _r(p=0.5, family='polytechnic'):
    return {'probability': p, 'type': family, 'present': [], 'missing': [], 'scores': {}}


class TheReasonOpeningsAreUnchanged(SimpleTestCase):
    """Step 1 drift pin: the three IPTS reasons are BUILT from the shared openings, byte for byte as before
    (a change here changes saved output and needs a MODEL_VERSION bump)."""

    def test_the_saved_reasons_are_byte_identical(self):
        kptm = 'KOLEJ POLY-TECH MARA\nMilik Majlis Amanah Rakyat\nTAWARAN KEMASUKAN\n'
        self.assertEqual(private_college_reason(kptm, _r()), COLLEGE_REASON)
        space = 'UNIVERSITI TEKNOLOGI MALAYSIA\nPENDIDIKAN BERTERUSAN (SPACE)\nTAWARAN KEMASUKAN\n'
        self.assertEqual(baseline_genuineness(space, _r(family='ua_offer'), 'offer_letter')['reason'], ARM_REASON)
        out = ruled_offer('ABC TRAINING SDN BHD\nIKBN PEKAN\nSURAT TAWARAN\n', _r(0.4), 'suspect', 'r', MODEL_VERSION)
        self.assertEqual(out['reason'], S6_REASON)

    def test_each_saved_reason_opens_with_an_opening(self):
        self.assertEqual(offer_private.IPTS_REASON_OPENINGS, (
            '[S6 ruling: private_offer] ', 'private college / university (IPTS)', 'private / continuing-education arm'))
        for reason in (S6_REASON, COLLEGE_REASON, ARM_REASON):
            self.assertTrue(reason.startswith(offer_private.IPTS_REASON_OPENINGS), reason)

    def test_no_model_version_bump(self):
        self.assertEqual(MODEL_VERSION, '1.29.0')

    def test_engine_version_floor(self):
        self.assertGreaterEqual(VERDICT_ENGINE_VERSION, '2026-11-18.2')


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='ipts', name='B40', year=2026)

    def _app(self, suffix):
        student = make_student(supabase_user_id=f'ipts-{suffix}', name='Anbu A/L Raj',
                               household_income=1500, household_size=5)
        return make_application('profile_complete', cohort=self.cohort, student=student, chosen_pathway='poly',
                                father_occupation='gov', mother_occupation='homemaker')

    def _offer(self, app, *, institution='', issuer='', programme='Diploma Sains Komputer', reason=None,
               status='not_offer_letter', read=True):
        vf = {'fields': {'programme': programme, 'institution': institution, 'issuer': issuer,
                         'candidate_name': 'Anbu A/L Raj'}, 'student_verdict': 'ok'} if read else {}
        if reason is not None:
            vf['authenticity'] = {'status': status, 'reason': reason, 'doc_seen': 'polytechnic', 'probability': 0.5}
        return ApplicantDocument.objects.create(application=app, doc_type='offer_letter', storage_path='x/offer',
                                                vision_fields=vf)

    def _pathway(self, app):
        return next(f for f in build_verdict(app) if f['fact'] == 'pathway')

    def _item(self, app):
        return next((i for i in self._pathway(app)['unresolved'] if i['code'] == CODE), None)


class EachSignalFires(_Base):
    def test_the_name_signal_on_a_named_private_body(self):
        app = self._app('kptm')
        self._offer(app, institution='Kolej Poly-Tech MARA Kuala Lumpur')
        self.assertEqual(self._pathway(app)['status'], 'gap')
        self.assertEqual(self._item(app)['params'],
                         {'institution': 'Kolej Poly-Tech MARA Kuala Lumpur', 'signal': 'name'})

    def test_the_name_signal_on_the_issuer_and_the_programme(self):
        for k, (inst, iss, prog) in enumerate((('', 'UMS PPPL', 'Diploma Pengurusan'),
                                               ('Kolej Contoh', '', 'Diploma Perniagaan (Saluran Terbuka)'))):
            with self.subTest(iss or prog):
                app = self._app(f'n{k}')
                self._offer(app, institution=inst, issuer=iss, programme=prog)
                self.assertEqual(self._item(app)['params']['signal'], 'name')

    def test_utm_space_still_flags_though_it_names_a_public_university(self):
        app = self._app('space')
        self._offer(app, institution='Universiti Teknologi Malaysia',
                    issuer='SEKOLAH PENDIDIKAN PROFESIONAL DAN PENDIDIKAN BERTERUSAN (SPACE)')
        self.assertEqual(self._item(app)['params']['signal'], 'name')
        app2 = self._app('space2')
        self._offer(app2, institution='UTM SPACE', reason=ARM_REASON)
        self.assertEqual(self._item(app2)['params'], {'institution': 'UTM SPACE', 'signal': 'name'})

    def test_the_reason_signal_on_each_opening(self):
        for k, reason in enumerate((S6_REASON, COLLEGE_REASON, ARM_REASON)):
            with self.subTest(reason[:30]):
                app = self._app(f'r{k}')
                self._offer(app, institution='Kolej Teknikal Cemerlang', reason=reason)
                self.assertEqual(self._item(app)['params'],
                                 {'institution': 'Kolej Teknikal Cemerlang', 'signal': 'reason'})

    def test_a_suspect_letter_now_reads_gap(self):
        app = self._app('suspect')
        self._offer(app, institution='Kolej Teknikal Cemerlang', reason=COLLEGE_REASON, status='suspect')
        self.assertEqual(self._pathway(app)['status'], 'gap')
        self.assertIsNotNone(self._item(app))


class APublicPlaceIsNeverFlaggedByTheReason(_Base):
    def test_a_public_list_name_blocks_the_reason_signal(self):
        for k, inst in enumerate(('Universiti Teknologi Malaysia', 'UiTM Shah Alam', 'Politeknik Ungku Omar',
                                  'Institut Kemahiran Belia Negara Pekan')):
            with self.subTest(inst):
                app = self._app(f'p{k}')
                self._offer(app, institution=inst, reason=S6_REASON)
                self.assertIsNone(self._item(app))

    def test_a_public_catalogue_name_blocks_the_reason_signal(self):
        app = self._app('cat-without')
        self._offer(app, institution='Institut Latihan Contoh Bestari', reason=COLLEGE_REASON)
        self.assertIsNotNone(self._item(app))       # named on no list: the reason flags it
        Institution.objects.create(institution_id='ipts-ilcb', institution_name='Institut Latihan Contoh Bestari',
                                   type='ILP', state='Selangor')
        app2 = self._app('cat-with')
        self._offer(app2, institution='Institut Latihan Contoh Bestari', reason=COLLEGE_REASON)
        self.assertIsNone(self._item(app2))         # in the public catalogue: never flagged by the reason

    def test_a_letter_we_cannot_classify_keeps_todays_behaviour(self):
        app = self._app('blank')
        self._offer(app, institution='', issuer='', reason=COLLEGE_REASON)
        self.assertIsNone(self._item(app))

    def test_a_public_letter_without_a_reason_is_unchanged(self):
        app = self._app('public')
        self._offer(app, institution='Politeknik Ungku Omar', reason='', status='genuine')
        self.assertIsNone(self._item(app))


class ThePublicVetoKnowsMoreNames(_Base):
    """Review fix 2026-11-19: IIUM's English name, the catalogue aliases, the wingless public types and
    the English university names all veto the reason signal (never the name signal)."""

    def test_iiums_english_letter_with_a_sdn_bhd_fee_line_is_not_flagged(self):
        from apps.scholarship.genuineness import signature_genuineness
        from apps.scholarship.tests.test_req66_iium_english_offer import IIUM_SDN_BHD
        reason = signature_genuineness(IIUM_SDN_BHD, doc_type='offer_letter')['reason']
        self.assertTrue(reason.startswith(offer_private.IPTS_REASON_OPENINGS), reason)   # the private-wing reason
        for k, (inst, iss) in enumerate((('International Islamic University Malaysia', ''),
                                         ('', 'International Islamic University Malaysia (IIUM)'))):
            with self.subTest(inst or iss):
                app = self._app(f'iium{k}')
                self._offer(app, institution=inst, issuer=iss, programme='Bachelor of Contoh Studies (Honours)',
                            reason=reason)
                self.assertIsNone(self._item(app))

    def test_a_catalogue_alias_vetoes(self):
        app = self._app('ump')
        self._offer(app, institution='Universiti Malaysia Pahang Al-Sultan Abdullah', reason=COLLEGE_REASON)
        self.assertIsNone(self._item(app))

    def test_each_wingless_public_type_vetoes_without_a_catalogue_campus(self):
        for k, inst in enumerate(('Kolej Komuniti Contoh Jaya', 'Kolej Matrikulasi Contoh', 'Kolej Vokasional Contoh',
                                  'Institut Pendidikan Guru Kampus Contoh', 'IPG Kampus Contoh', 'Politeknik Contoh',
                                  'Contoh Polytechnic', 'Contoh Community College')):
            with self.subTest(inst):
                app = self._app(f'type{k}')
                self._offer(app, institution=inst, reason=COLLEGE_REASON)
                self.assertIsNone(self._item(app))

    def test_english_university_names_veto(self):
        for k, inst in enumerate(('University of Malaya', 'University Putra Malaysia',
                                  'National University of Malaysia', 'University of Science Malaysia')):
            with self.subTest(inst):
                app = self._app(f'en{k}')
                self._offer(app, institution=inst, reason=ARM_REASON)
                self.assertIsNone(self._item(app))

    def test_a_private_college_still_flags_by_its_reason(self):
        app = self._app('still')
        self._offer(app, institution='Contoh University College', reason=COLLEGE_REASON)
        self.assertEqual(self._item(app)['params']['signal'], 'reason')


class SpaceOnlyOnThePlace(_Base):
    def test_a_space_programme_at_a_public_university_is_not_flagged(self):
        app = self._app('space-prog')
        self._offer(app, institution='Universiti Kebangsaan Malaysia', programme='Bachelor of Space Science')
        self.assertIsNone(self._item(app))
        self.assertFalse(offer_private.names_private_body('Space Science', 'Kolej Contoh', ''))

    def test_space_on_the_institution_or_issuer_still_flags(self):
        self.assertTrue(offer_private.names_private_body('Diploma Perniagaan', 'UTM SPACE', ''))
        self.assertTrue(offer_private.names_private_body('Diploma Perniagaan', '', 'UTMSPACE / SPACE'))

    def test_the_wing_phrases_still_read_on_the_programme(self):
        self.assertTrue(offer_private.names_private_body('Diploma Perniagaan (Pendidikan Berterusan)', '', ''))


class OnlyTheLatestLetterCounts(_Base):
    """A re-upload supersedes the old letter (one live letter per slot); only the live one is read."""

    def _replace(self, old, app, **kw):
        old.superseded_at = timezone.now()
        old.save(update_fields=['superseded_at'])
        return self._offer(app, **kw)

    def test_a_later_public_letter_clears_the_flag(self):
        app = self._app('later-public')
        first = self._offer(app, institution='Kolej Poly-Tech MARA')
        self.assertIsNotNone(self._item(app))
        self._replace(first, app, institution='Politeknik Ungku Omar')
        self.assertIsNone(self._item(app))

    def test_a_later_ipts_letter_raises_it(self):
        app = self._app('later-ipts')
        first = self._offer(app, institution='Politeknik Ungku Omar')
        self.assertIsNone(self._item(app))
        self._replace(first, app, institution='Kolej Poly-Tech MARA')
        self.assertIsNotNone(self._item(app))


class AlongsideTheOtherPathwayRules(_Base):
    def _codes(self, app):
        return [i['code'] for i in self._pathway(app)['unresolved']]

    def test_funded_or_abroad_and_ipts_both_show_in_a_stable_order(self):
        app = self._app('adp')
        app.chosen_programme = {'course_name': 'American Degree Program', 'institution': 'Kolej Poly-Tech MARA'}
        app.save(update_fields=['chosen_programme'])
        self._offer(app, institution='Kolej Poly-Tech MARA')
        codes = self._codes(app)
        self.assertEqual(self._pathway(app)['status'], 'gap')
        self.assertLess(codes.index('pathway_funded_or_abroad'), codes.index(CODE))
        self.assertEqual(codes, self._codes(app))
        self.assertEqual(award.verdict_disqualifier(build_verdict(app)), 'pathway_funded_or_abroad')

    def test_ipts_and_a_start_year_outside_the_intake_both_show(self):
        cohort = ScholarshipCohort.objects.create(code='ipts-sy', name='Degree', year=2026,
                                                  allowed_start_years=[2025, 2026])
        app = self._app('sy')
        app.cohort = cohort
        app.save(update_fields=['cohort'])
        doc = self._offer(app, institution='Kolej Poly-Tech MARA')
        doc.vision_fields['fields'].update({'intake': '2024', 'reporting_date': '10 JUN 2024'})
        doc.save(update_fields=['vision_fields'])
        codes = self._codes(app)
        self.assertLess(codes.index(CODE), codes.index('pathway_start_year_outside'))
        self.assertEqual(self._pathway(app)['status'], 'gap')


class NoLineWithoutARead(_Base):
    def test_an_unread_letter_gives_no_line(self):
        app = self._app('unread')
        self._offer(app, read=False)
        self.assertIsNone(self._item(app))

    def test_the_read_deferred_guard_is_what_stops_a_letter_with_fields(self):
        """The letter carries private fields; only the guard's answer differs between the two runs."""
        app = self._app('deferred')
        self._offer(app, institution='Kolej Poly-Tech MARA', reason=COLLEGE_REASON)
        self.assertIsNotNone(self._item(app))
        with mock.patch('apps.scholarship.read_errors.read_deferred', return_value=True):
            self.assertIsNone(offer_private.private_offer_signal(
                ApplicantDocument.objects.filter(application=app).latest('id')))

    def test_no_letter_gives_no_line(self):
        app = self._app('none')
        self.assertIsNone(self._item(app))
        self.assertIsNone(offer_private.private_offer_signal(None))


class FlagOnlyReviewersOnly(_Base):
    def test_the_disqualifier_leads_with_the_new_code(self):
        self.assertIn(CODE, award.CONFIDENT_DISQUALIFIERS)
        app = self._app('dq')
        self._offer(app, institution='UniKL MIIT', reason=S6_REASON)     # also a not_offer_letter fail
        self.assertEqual(award.verdict_disqualifier(build_verdict(app)), CODE)

    def test_the_amount_is_unchanged(self):
        app, twin = self._app('amt'), self._app('amt-twin')
        self._offer(app, institution='Kolej Poly-Tech MARA')
        self._offer(twin, institution='Politeknik Ungku Omar')
        self.assertIsNotNone(self._item(app))
        self.assertEqual(award.proposed_award_amount(app), award.proposed_award_amount(twin))

    def test_consent_blockers_are_unchanged(self):
        app = self._app('consent')
        self._offer(app, institution='Kolej Poly-Tech MARA', reason=COLLEGE_REASON, status='suspect')
        self.assertIsNotNone(self._item(app))
        with_rule = consent_blockers(app)
        with mock.patch.object(offer_private, 'private_offer_signal', return_value=None):
            self.assertIsNone(self._item(app))
            self.assertEqual(consent_blockers(app), with_rule)
        self.assertNotIn(CODE, with_rule)

    def test_no_student_ticket(self):
        self.assertNotIn(CODE, CODE_TO_TICKET)
