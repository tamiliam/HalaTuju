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
             name_match='', address_match='', member=''):
    """A supporting document with doc-assist + match fields populated. ``member``
    tags a salary-route income doc to a household member."""
    vf = {}
    if student_verdict or fields is not None:
        vf = {'fields': fields or {}, 'warnings': [],
              'student_verdict': student_verdict, 'error': ''}
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, storage_path=f'{app.id}/{doc_type}/{member}x',
        household_member=member,
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


# ── Income (Check-1 item 3: wizard-driven earner identity + relationship) ─────

def _parent_ic(app, name, member='', nric=''):
    """The income earner's IC (parent_ic), OCR'd name on the vision_name column.
    ``member`` tags it to a salary-route household member."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='parent_ic', storage_path=f'{app.id}/parent_ic/{member}x',
        household_member=member, vision_name=name, vision_nric=nric, vision_run_at=timezone.now())


class TestIncome(_Base):
    def _wizard(self, route='', earner='', members=None):
        # Father derivable from the student-IC patronymic 'DIVASHINI A/P MURUGAN' → MURUGAN.
        self.profile.name = 'DIVASHINI A/P MURUGAN'
        self.profile.save()
        self.app.income_route = route
        self.app.income_earner = earner
        self.app.income_working_members = members or []
        self.app.save()

    def test_str_pre_wizard_is_review_not_green(self):
        # Income green now requires the whole cluster (STR + earner IC + relationship), so a
        # bare STR before the wizard is walked is no longer enough on its own.
        _add_doc(self.app, 'str', name_match='found')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('income_earner_undeclared', _codes(f['unresolved']))

    def test_wizard_not_walked_is_review_undeclared(self):
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('income_earner_undeclared', _codes(f['unresolved']))

    def test_str_father_complete_is_verified(self):
        # Whole cluster adds up: current STR whose recipient = the father IC + patronymic.
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'Lulus', 'year': '2026'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('str_verified', _codes(f['evidence']))
        self.assertIn('relationship_confirmed', _codes(f['evidence']))
        self.assertIn('earner_ic_present', _codes(f['evidence']))

    def test_str_stale_year_is_review(self):
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'Lulus', 'year': '2023'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('str_not_current', _codes(f['unresolved']))

    def test_str_recipient_not_earner_is_review(self):
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'SOMEONE ELSE BIN OTHER', 'status': 'Lulus', 'year': '2026'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('str_recipient_mismatch', _codes(f['unresolved']))

    def test_earner_ic_missing_is_gap(self):
        self._wizard(route='str', earner='father')
        _add_doc(self.app, 'str', name_match='found')          # no parent_ic
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('earner_ic_missing', _codes(f['unresolved']))

    def test_father_relationship_mismatch_is_review(self):
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'RAJU A/L SAMY')                   # not the student's father
        _add_doc(self.app, 'str', name_match='found')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('father_patronymic_mismatch', _codes(f['unresolved']))

    def test_mother_route_bc_missing_is_gap(self):
        self._wizard(route='str', earner='mother')
        _parent_ic(self.app, 'KAMALA A/P RAMAN')
        _add_doc(self.app, 'str', name_match='found')           # no birth_certificate
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('birth_cert_missing', _codes(f['unresolved']))

    def test_mother_route_bc_match_is_verified(self):
        self._wizard(route='str', earner='mother')
        _parent_ic(self.app, 'KAMALA A/P RAMAN')
        _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                 fields={'bc_child_name': 'DIVASHINI A/P MURUGAN', 'bc_mother_name': 'KAMALA A/P RAMAN'})
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'status': 'Lulus', 'year': '2026'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('relationship_confirmed', _codes(f['evidence']))

    def test_guardian_letter_missing_is_gap(self):
        self._wizard(route='str', earner='guardian')
        _parent_ic(self.app, 'RAJA A/L KUMAR')
        _add_doc(self.app, 'str', name_match='found')           # no guardianship_letter
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('guardianship_letter_missing', _codes(f['unresolved']))


# ── Income — salary (non-STR) multi-earner route ─────────────────────────────

class TestIncomeSalary(_Base):
    def _wizard(self, members):
        self.profile.name = 'DIVASHINI A/P MURUGAN'   # patronymic → MURUGAN
        self.profile.save()
        self.app.income_route = 'salary'
        self.app.income_working_members = members
        self.app.save()

    def test_no_members_is_review_undeclared(self):
        self._wizard([])
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('income_earner_undeclared', _codes(f['unresolved']))

    def test_father_ic_plus_payslip_is_verified(self):
        # IC present + patronymic match + payslip whose per-capita clears the B40 line
        # (RM2,000 / household 4 = RM500 < RM1,584) → verified.
        self._wizard(['father'])
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='father',
                 fields={'name': 'MURUGAN A/L KESAVAN', 'gross_income': 'RM2,000'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('relationship_confirmed', _codes(f['evidence']))
        self.assertIn('income_proof_present', _codes(f['evidence']))
        self.assertIn('income_per_capita_ok', _codes(f['evidence']))

    def test_sibling_only_with_payslip_is_verified(self):
        # The borrowed-payslip hole is closed: a brother's IC carries the SAME father's
        # name, so a lone working sibling is still machine-verifiable. EPF contribution
        # RM480 ≈ 24% of ~RM2,000 → per-capita RM500 < RM1,584 → verified.
        self._wizard(['brother'])
        _parent_ic(self.app, 'RAJESH A/L MURUGAN', member='brother')
        _add_doc(self.app, 'epf', student_verdict='ok', member='brother',
                 fields={'name': 'RAJESH A/L MURUGAN', 'monthly_contribution': 'RM480'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('relationship_confirmed', _codes(f['evidence']))

    def test_sibling_patronymic_mismatch_is_review(self):
        self._wizard(['sister'])
        _parent_ic(self.app, 'PRIYA A/P STRANGER', member='sister')
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='sister')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('father_patronymic_mismatch', _codes(f['unresolved']))

    def test_ic_present_no_financial_is_recommend_interview(self):
        # Never blocks: IC present, relationship fine, but no payslip/EPF (informal).
        self._wizard(['father'])
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_unverified_needs_interview', _codes(f['unresolved']))

    def test_missing_ic_is_gap(self):
        self._wizard(['father'])
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='father')  # no IC
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('earner_ic_missing', _codes(f['unresolved']))

    def test_mother_member_needs_birth_cert_is_gap(self):
        self._wizard(['mother'])
        _parent_ic(self.app, 'KAMALA A/P RAMAN', member='mother')
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='mother')  # no BC
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('birth_cert_missing', _codes(f['unresolved']))

    def test_multi_member_missing_ic_aggregates_into_one_item(self):
        # Two members both missing an IC → ONE earner_ic_missing item listing both
        # (the resolution layer keys tickets by code — duplicates would collide).
        self._wizard(['father', 'brother'])
        f = _facts(self.app)['income']
        ic_items = [i for i in f['unresolved'] if i['code'] == 'earner_ic_missing']
        self.assertEqual(len(ic_items), 1)
        self.assertEqual(set(ic_items[0]['params']['members']), {'father', 'brother'})

    def test_unknown_patronymic_with_payslip_is_recommend_not_verified(self):
        # A Chinese-style name has no patronymic → relationship 'unknown' → can't assert
        # verified even with a payslip; a human places it.
        self.profile.name = 'TAN WEI MING'
        self.profile.save()
        self.app.income_route = 'salary'
        self.app.income_working_members = ['father']
        self.app.save()
        _parent_ic(self.app, 'TAN AH KOW', member='father')
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='father')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')


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

    def test_offer_notice_without_identity_is_no_identity_not_unreadable(self):
        # Sharvin: a general UTM NOTICE whose body read fine (issuer/institution/
        # programme present) but carries NO candidate name or IC. That's a wrong /
        # placeholder document, not a blurry scan — the officer is told "no identity
        # on it", never the misleading "ask for a clearer copy".
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': '', 'candidate_nric': '',
                         'institution': 'Universiti Teknologi Malaysia',
                         'programme': 'Program Asasi dan Diploma UTM'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('offer_no_identity', _codes(f['unresolved']))
        self.assertNotIn('offer_unreadable', _codes(f['unresolved']))

    def test_offer_blank_everything_is_unreadable(self):
        # Genuinely nothing read (no identity AND no body) → still 'could not be read'.
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': '', 'candidate_nric': '',
                         'institution': '', 'programme': ''})
        f = _facts(self.app)['pathway']
        self.assertIn('offer_unreadable', _codes(f['unresolved']))
        self.assertNotIn('offer_no_identity', _codes(f['unresolved']))

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
        # Income: review — she hasn't walked the income wizard yet (no income_earner),
        # so the engine asks her to (the documents can't be checked until she does).
        self.assertEqual(facts['income']['status'], 'review')
        self.assertIn('income_earner_undeclared', _codes(facts['income']['unresolved']))
        # Pathway: verified — the offer's identity matches and it doesn't clash with
        # any specific declared college/programme (she declared only a pathway type),
        # so the offer settles the pathway with no redundant confirmation nag.
        self.assertEqual(facts['pathway']['status'], 'verified')
        self.assertNotIn('pathway_confirm', _codes(facts['pathway']['unresolved']))

    def test_order_is_fixed(self):
        self.assertEqual([f['fact'] for f in build_verdict(self.app)],
                         ['identity', 'academic', 'pathway', 'income'])


# ── Income — per-member document CLUSTER (Check-1 cluster-aware coach) ────────

class TestIncomeCluster(TestCase):
    """Income is a cluster per person (member IC + their salary slip / EPF). One
    cluster coach is anchored on the member's IC; the proofs are cross-checked against
    it. Real ORM — the cluster reads the application's documents."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='cl', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'cluster-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['father'])

    def _slip(self, member, name, nric='', amount='RM2000'):
        return _add_doc(self.app, 'salary_slip', student_verdict='ok', member=member,
                        fields={'name': name, 'nric': nric, 'gross_income': amount, 'period': 'March 2026'})

    def test_proof_check_matches_member_ic(self):
        from apps.scholarship.income_engine import student_income_proof_check
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father', nric='600101-01-1111')
        slip = self._slip('father', 'MURUGAN A/L KESAVAN', nric='600101-01-1111')
        chk = student_income_proof_check(slip)
        self.assertEqual(chk['name_status'], 'match')
        self.assertEqual(chk['nric_status'], 'match')
        self.assertEqual(chk['amount'], 'RM2000')
        self.assertTrue(chk['ic_present'])

    def test_proof_no_member_ic_yet(self):
        from apps.scholarship.income_engine import student_income_proof_check
        from apps.scholarship.help_engine import verdict_for_document
        slip = self._slip('father', 'MURUGAN A/L KESAVAN')        # no IC for father
        chk = student_income_proof_check(slip)
        self.assertFalse(chk['ic_present'])
        # The proof's coach nudges to add the member's IC (cluster anchor missing).
        self.assertEqual(verdict_for_document(slip), 'income_ic_needed')

    def test_cluster_consistent_is_silent(self):
        from apps.scholarship.income_engine import income_cluster_advice
        ic = _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        self._slip('father', 'MURUGAN A/L KESAVAN')
        self.assertEqual(income_cluster_advice(self.app, 'father'), '')
        from apps.scholarship.help_engine import verdict_for_document
        self.assertEqual(verdict_for_document(ic), '')           # IC anchors, nothing to say

    def test_cluster_relationship_mismatch(self):
        from apps.scholarship.income_engine import income_cluster_advice
        _parent_ic(self.app, 'RAJU A/L STRANGER', member='father')   # not the student's father
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'income_relationship_mismatch')

    def test_cluster_person_mismatch_proof_vs_ic(self):
        from apps.scholarship.income_engine import income_cluster_advice
        from apps.scholarship.help_engine import verdict_for_document
        ic = _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father', nric='600101-01-1111')
        self._slip('father', 'SOMEONE ELSE BIN OTHER', nric='770202-02-2222')
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'income_proof_person_mismatch')
        # The single cluster coach is anchored on the IC and speaks the coherence verdict.
        self.assertEqual(verdict_for_document(ic), 'income_proof_person_mismatch')

    def test_proof_coach_silent_when_ic_present(self):
        # No second Gopal: when the member's IC anchors the cluster, the proof stays quiet.
        from apps.scholarship.help_engine import verdict_for_document
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        slip = self._slip('father', 'MURUGAN A/L KESAVAN')
        self.assertEqual(verdict_for_document(slip), '')


class TestIncomeClusterStr(TestCase):
    """STR route: income proofs are UNTAGGED (single earner = income_earner). The same
    cluster checks must verify them against the untagged earner IC, never the student —
    otherwise the STR salary slip shows the wrong 'edit your profile name' coach."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='cs', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'clusterstr-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132')
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='str', income_earner='father')

    def test_str_proof_checks_against_untagged_earner_ic(self):
        from apps.scholarship.income_engine import student_income_proof_check
        from apps.scholarship.help_engine import verdict_for_document
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='', nric='600101-01-1111')  # untagged
        slip = _add_doc(self.app, 'salary_slip', student_verdict='ok', member='',       # untagged
                        fields={'name': 'MURUGAN A/L KESAVAN', 'nric': '600101-01-1111',
                                'gross_income': 'RM2000', 'period': 'May 2026'})
        chk = student_income_proof_check(slip)
        self.assertIsNotNone(chk)                       # NOT None for an STR-route slip
        self.assertEqual(chk['member'], 'father')       # resolved from income_earner
        self.assertEqual(chk['name_status'], 'match')
        self.assertTrue(chk['ic_present'])
        # The coach is anchored on the earner IC, so the slip itself stays quiet (NOT the
        # generic student-name "edit your profile" message).
        self.assertEqual(verdict_for_document(slip), '')

    def test_str_proof_person_mismatch_voiced_on_ic(self):
        from apps.scholarship.income_engine import income_cluster_advice
        from apps.scholarship.help_engine import verdict_for_document
        ic = _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='', nric='600101-01-1111')
        _add_doc(self.app, 'salary_slip', student_verdict='ok', member='',
                 fields={'name': 'SUBACHANNA A/P AHCHINNA', 'nric': '810404-02-5330',
                         'gross_income': 'RM9900', 'period': 'May 2026'})
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'income_proof_person_mismatch')
        self.assertEqual(verdict_for_document(ic), 'income_proof_person_mismatch')

    def test_str_proof_no_ic_yet_nudges(self):
        from apps.scholarship.help_engine import verdict_for_document
        slip = _add_doc(self.app, 'salary_slip', student_verdict='ok', member='',
                        fields={'name': 'MURUGAN A/L KESAVAN'})
        self.assertEqual(verdict_for_document(slip), 'income_ic_needed')


class TestIncomePerCapita(TestCase):
    """Salary route I4: sum the earners' pay from the documents → per-capita vs the cohort
    ceiling. Green only when it clears the B40 line AND the cluster adds up; above the line
    (or uncomputable) → recommend + interview, never blocked."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='pc', name='B40', year=2026,
                                                      per_capita_ceiling=1584)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'percap-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['father'])

    def _father(self, gross=None, epf_contrib=None):
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        if gross is not None:
            _add_doc(self.app, 'salary_slip', student_verdict='ok', member='father',
                     fields={'name': 'MURUGAN A/L KESAVAN', 'gross_income': gross, 'period': 'May 2026'})
        if epf_contrib is not None:
            _add_doc(self.app, 'epf', student_verdict='ok', member='father',
                     fields={'name': 'MURUGAN A/L KESAVAN', 'monthly_contribution': epf_contrib})

    def test_below_ceiling_is_verified(self):
        self._father(gross='RM2,000')      # 2000 / 4 = 500 < 1584
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('income_per_capita_ok', _codes(f['evidence']))

    def test_above_ceiling_is_recommend_interview(self):
        self.profile.household_size = 2
        self.profile.save()
        self._father(gross='RM9,900.04')   # 9900 / 2 = 4950 >= 1584
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_above_b40_line', _codes(f['unresolved']))

    def test_epf_contribution_estimates_salary(self):
        # EPF monthly contribution RM480 ≈ 24% of salary → ~RM2000 → per-capita 500 < 1584.
        self._father(epf_contrib='RM480')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')

    def test_unreadable_amount_falls_to_interview(self):
        self._father(gross='see attached')   # no parseable figure
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_unverified_needs_interview', _codes(f['unresolved']))
