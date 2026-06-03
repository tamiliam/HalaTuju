"""Tests for the deterministic Verification Verdict engine (Sprint 1).

Real-ORM fixtures (not SimpleNamespace) so every attribute the engine reads
resolves to a real value — lesson #55. One+ case per fact status, the two
design rules that bite (name-truncation auto-resolve; STR-gated income), plus a
full Theresa-shaped integration check.
"""
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, FundingNeed, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.verdict_engine import build_verdict


def _facts(app):
    """{fact_name: fact_dict} for easy assertions."""
    return {f['fact']: f for f in build_verdict(app)}


def _codes(items):
    return [i['code'] for i in items]


class _Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'verdict-{self.id()}',
            name='THERESA ARUL MARY A/P A.PHILIPS',
            nric='080115-05-0132',
            preferred_state='Melaka',
            household_income=1800,
            household_size=4,
            receives_str=False,
            receives_jkm=False,
        )
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            chosen_pathway='Matriculation',
        )


def _add_ic(app, *, nric='', name='', address='', error='', run=True):
    return ApplicantDocument.objects.create(
        application=app, doc_type='ic', storage_path=f'{app.id}/ic/x',
        vision_nric=nric, vision_name=name, vision_address=address,
        vision_run_at=timezone.now() if run else None, vision_error=error,
    )


def _add_doc(app, doc_type, *, student_verdict='', fields=None,
             name_match='', address_match=''):
    """A supporting document with doc-assist + match fields populated."""
    vf = {}
    if student_verdict or fields is not None:
        vf = {'fields': fields or {}, 'warnings': [],
              'student_verdict': student_verdict, 'error': ''}
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/{doc_type}/x',
        vision_fields=vf, vision_name_match=name_match,
        vision_address_match=address_match, vision_run_at=timezone.now(),
    )


# ── Identity ─────────────────────────────────────────────────────────────────

class TestIdentity(_Base):
    def test_missing_ic_is_gap(self):
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('ic_missing', _codes(f['unresolved']))

    def test_nric_and_name_match_is_verified(self):
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name)
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'verified')
        self.assertEqual(f['unresolved'], [])
        self.assertIn('nric_match', _codes(f['evidence']))
        self.assertIn('name_match', _codes(f['evidence']))

    def test_name_truncation_auto_resolves_to_verified(self):
        # The key rule: OCR read only line 1 of the name (patronymic on line 2
        # dropped). The typed name is a SUPERSET → resolved, NOT a mismatch.
        _add_ic(self.app, nric=self.profile.nric, name='THERESA ARUL MARY A/P')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'verified')
        self.assertEqual(f['unresolved'], [])
        self.assertIn('name_resolved_truncation', _codes(f['evidence']))

    def test_nric_mismatch_is_review_never_fail(self):
        _add_ic(self.app, nric='710829-02-5709', name=self.profile.name)
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'review')
        self.assertIn('nric_mismatch', _codes(f['unresolved']))

    def test_disjoint_name_is_review(self):
        _add_ic(self.app, nric=self.profile.nric, name='AHMAD BIN ALI')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'review')
        self.assertIn('name_mismatch', _codes(f['unresolved']))

    def test_unreadable_ic_is_gap(self):
        _add_ic(self.app, nric='', name='', error='empty image')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('ic_unreadable', _codes(f['unresolved']))

    def test_service_down_is_review_not_gap(self):
        _add_ic(self.app, nric='', name='', error='Vision API quota exceeded')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'review')
        self.assertIn('ic_service_down', _codes(f['unresolved']))

    def test_major_address_divergence_escalates(self):
        # Different STATE on the IC → coherence flag.
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='NO 12 JALAN ABC, 08000 SUNGAI PETANI, KEDAH')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'review')
        self.assertIn('address_state_mismatch', _codes(f['unresolved']))

    def test_substate_postcode_drift_is_noise(self):
        # Same state (Melaka), different postcode/town → NOT flagged.
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='TB 456 JALAN KEJORA 4, 76460 ALOR GAJAH, MELAKA')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'verified')
        self.assertEqual(f['unresolved'], [])


# ── Academic ─────────────────────────────────────────────────────────────────

class TestAcademic(_Base):
    def test_missing_slip_is_gap(self):
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('results_slip_missing', _codes(f['unresolved']))

    def test_slip_present_is_review_with_grades_pending(self):
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')  # grades not yet cross-checked (S2)
        self.assertIn('results_slip_name_ok', _codes(f['evidence']))
        self.assertIn('grades_unverified', _codes(f['unresolved']))

    def test_slip_name_mismatch_flags(self):
        _add_doc(self.app, 'results_slip', student_verdict='name_mismatch')
        f = _facts(self.app)['academic']
        self.assertIn('results_slip_name_mismatch', _codes(f['unresolved']))


class TestAcademicGrades(_Base):
    """S2: grade extraction → completeness + accuracy."""

    def _slip(self, results):
        return _add_doc(self.app, 'results_slip', student_verdict='ok',
                        name_match='found', fields={'results': results})

    def test_complete_and_accurate_is_verified(self):
        self.profile.grades = {'bm': 'A-', 'eng': 'A+'}
        self.profile.save()
        self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                    {'subject': 'Bahasa Inggeris', 'grade': 'A+'}])
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('grades_verified', _codes(f['evidence']))

    def test_missing_subjects_is_review(self):
        self.profile.grades = {'bm': 'A-'}
        self.profile.save()
        self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                    {'subject': 'Pendidikan Moral', 'grade': 'A'}])
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')
        self.assertIn('academic_missing_subjects', _codes(f['unresolved']))

    def test_grade_mismatch_is_review(self):
        self.profile.grades = {'bm': 'A-', 'math': 'B+'}
        self.profile.save()
        self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                    {'subject': 'Matematik', 'grade': 'A'}])
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')
        self.assertIn('academic_grade_mismatch', _codes(f['unresolved']))

    def test_clean_slip_with_not_found_name_match_is_not_unreadable(self):
        # Regression (Sharvani): a perfectly-read slip (sv='ok') whose supporting-doc
        # vision_name_match happens to be 'not_found' must NOT be flagged "could not be
        # read". The slip's OWN sv-authoritative name check governs → verified.
        self.profile.grades = {'bm': 'A-', 'eng': 'A+'}
        self.profile.save()
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='not_found',
                 fields={'results': [{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                                     {'subject': 'Bahasa Inggeris', 'grade': 'A+'}]})
        f = _facts(self.app)['academic']
        self.assertNotIn('results_slip_unreadable', _codes(f['unresolved']))
        self.assertIn('results_slip_name_ok', _codes(f['evidence']))
        self.assertEqual(f['status'], 'verified')

    def test_not_found_name_with_missing_subject_is_review_not_unreadable(self):
        # Sharvani exactly: clean read + one subject not entered → review with the
        # missing-subjects nudge ONLY; never the contradictory "could not be read".
        self.profile.grades = {'bm': 'A-'}
        self.profile.save()
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='not_found',
                 fields={'results': [{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                                     {'subject': 'Matematik Tambahan', 'grade': 'G'}]})
        f = _facts(self.app)['academic']
        codes = _codes(f['unresolved'])
        self.assertNotIn('results_slip_unreadable', codes)
        self.assertIn('academic_missing_subjects', codes)
        self.assertIn('results_slip_name_ok', _codes(f['evidence']))
        self.assertEqual(f['status'], 'review')


# ── Income ───────────────────────────────────────────────────────────────────

class TestIncome(_Base):
    def test_verified_str_document_is_green(self):
        _add_doc(self.app, 'str', name_match='found')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('str_verified', _codes(f['evidence']))

    def test_str_present_but_unmatched_is_review(self):
        _add_doc(self.app, 'str', name_match='not_found')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('str_present_unverified', _codes(f['unresolved']))

    def test_claimed_str_no_doc_with_epf_is_recommend(self):
        self.profile.receives_str = True
        self.profile.save()
        _add_doc(self.app, 'epf', student_verdict='ok')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('str_claimed_no_doc', _codes(f['unresolved']))
        self.assertIn('income_proof_epf', _codes(f['evidence']))

    def test_no_income_proof_is_gap(self):
        self.profile.receives_str = True
        self.profile.save()
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('income_proof_missing', _codes(f['unresolved']))

    def test_salary_only_no_str_claim_is_recommend(self):
        _add_doc(self.app, 'salary_slip', student_verdict='ok')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_proof_salary', _codes(f['evidence']))
        self.assertNotIn('str_claimed_no_doc', _codes(f['unresolved']))


# ── Pathway ──────────────────────────────────────────────────────────────────

class TestPathway(_Base):
    # An offer whose Name + IC match the applicant's profile.
    _OWN_OFFER = {'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                  'candidate_nric': '080115-05-0132',
                  'institution': 'KOLEJ MATRIKULASI MELAKA',
                  'programme': 'PROGRAM MATRIKULASI'}

    def test_offer_with_no_declared_clash_is_verified(self):
        # The app declares only a pathway TYPE ('Matriculation'), no specific
        # college/programme to clash with → the offer settles the pathway directly.
        # No redundant "is this your pathway?" nag (the old always-ask is gone).
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'verified')
        self.assertNotIn('pathway_confirm', _codes(f['unresolved']))
        self.assertIn('offer_programme', _codes(f['evidence']))

    def test_offer_matching_declared_is_verified_no_nag(self):
        # Declared institution matches the offer (naming quirk) → verified, no query.
        self.app.pre_u_institution = 'KM Melaka'
        self.app.save()
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'verified')
        self.assertNotIn('pathway_confirm', _codes(f['unresolved']))

    def test_offer_clashing_with_declared_asks_to_confirm(self):
        # Declared a genuinely different school → the offer clashes → the student is
        # asked to confirm which is final (Check-2 backstop), so the fact is 'review'.
        self.app.pre_u_institution = 'SMK Mentakab'
        self.app.save()
        clash = dict(self._OWN_OFFER, institution='SMK Temerloh',
                     programme='Tingkatan Enam')
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=clash)
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('pathway_confirm', _codes(f['unresolved']))

    def test_confirmed_offer_is_verified(self):
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        self.app.pathway_confirmed_at = timezone.now()
        self.app.save()
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('pathway_confirmed', _codes(f['evidence']))
        self.assertEqual(f['unresolved'], [])

    def test_offer_name_mismatch_is_review(self):
        _add_doc(self.app, 'offer_letter', student_verdict='name_mismatch',
                 fields={'candidate_name': 'SOMEONE ELSE', 'candidate_nric': '080115-05-0132'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('offer_name_mismatch', _codes(f['unresolved']))

    def test_offer_ic_mismatch_is_review(self):
        # IC is the strong identity check — a wrong NRIC flags even if the name is close.
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                         'candidate_nric': '999999-99-9999'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('offer_name_mismatch', _codes(f['unresolved']))

    def test_confirm_pathway_writes_chosen_programme_then_verified(self):
        from apps.scholarship import services
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        self.assertTrue(services.confirm_pathway(self.app))
        self.app.refresh_from_db()
        self.assertIsNotNone(self.app.pathway_confirmed_at)
        self.assertEqual(self.app.chosen_programme.get('course_name'), 'PROGRAM MATRIKULASI')
        self.assertEqual(self.app.chosen_programme.get('institution'), 'KOLEJ MATRIKULASI MELAKA')
        self.assertEqual(self.app.chosen_programme.get('source'), 'offer_letter_confirmed')
        # The verdict now reads verified.
        self.assertEqual(_facts(self.app)['pathway']['status'], 'verified')

    def test_confirm_pathway_no_offer_is_noop(self):
        from apps.scholarship import services
        self.assertFalse(services.confirm_pathway(self.app))
        self.app.refresh_from_db()
        self.assertIsNone(self.app.pathway_confirmed_at)

    def test_no_offer_but_declared_is_review(self):
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('pathway_declared', _codes(f['evidence']))

    def test_no_offer_undeclared_is_review_flagged(self):
        self.app.chosen_pathway = ''
        self.app.intended_pathway = ''
        self.app.save()
        f = _facts(self.app)['pathway']
        self.assertIn('pathway_undeclared', _codes(f['unresolved']))


# ── Integration: the Theresa case ────────────────────────────────────────────

class TestTheresaIntegration(_Base):
    def test_full_verdict_shape(self):
        # IC: NRIC matches, name truncated by OCR (line-2 patronymic dropped).
        _add_ic(self.app, nric=self.profile.nric, name='THERESA ARUL MARY A/P',
                address='TB 456 JALAN KEJORA 4, 76460 ALOR GAJAH, MELAKA')
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found')
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                         'candidate_nric': '080115-05-0132',
                         'institution': 'KOLEJ MATRIKULASI MELAKA',
                         'programme': 'PROGRAM MATRIKULASI'})
        _add_doc(self.app, 'epf', student_verdict='ok')
        _add_doc(self.app, 'water_bill', student_verdict='name_mismatch')
        _add_doc(self.app, 'electricity_bill', student_verdict='name_mismatch')
        # Claims STR but never uploaded the letter.
        self.profile.receives_str = True
        self.profile.save()

        facts = _facts(self.app)
        # Identity: verified, name truncation resolved, no unresolved.
        self.assertEqual(facts['identity']['status'], 'verified')
        self.assertEqual(facts['identity']['unresolved'], [])
        self.assertIn('name_resolved_truncation', _codes(facts['identity']['evidence']))
        # Academic: review (grades pending S2).
        self.assertEqual(facts['academic']['status'], 'review')
        # Income: recommend (no verified STR), STR-claim flagged.
        self.assertEqual(facts['income']['status'], 'recommend')
        self.assertIn('str_claimed_no_doc', _codes(facts['income']['unresolved']))
        # Pathway: verified — the offer's identity matches and it doesn't clash with
        # any specific declared college/programme (she declared only a pathway type),
        # so the offer settles the pathway with no redundant confirmation nag.
        self.assertEqual(facts['pathway']['status'], 'verified')
        self.assertNotIn('pathway_confirm', _codes(facts['pathway']['unresolved']))

    def test_order_is_fixed(self):
        self.assertEqual([f['fact'] for f in build_verdict(self.app)],
                         ['identity', 'academic', 'pathway', 'income'])
