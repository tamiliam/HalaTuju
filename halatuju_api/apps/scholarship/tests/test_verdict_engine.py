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

    def test_address_state_divergence_does_not_downgrade_identity(self):
        # A different STATE on the IC must NOT make identity amber. The MyKad's
        # registered address is the least-current address on file (relocation; the IC
        # isn't reissued) and is not an identity key — name + NRIC are. The divergence
        # stays a pre-interview flag ("ask which is current"), not a verdict caveat, so
        # identity reads green — matching the Documents panel + the student's IC card.
        _add_ic(self.app, nric=self.profile.nric, name=self.profile.name,
                address='NO 12 JALAN ABC, 08000 SUNGAI PETANI, KEDAH')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'verified')
        self.assertEqual(f['unresolved'], [])
        self.assertNotIn('address_state_mismatch', _codes(f['unresolved']))

    def test_substate_postcode_drift_is_noise(self):
        # Same state (Melaka), different postcode/town → still verified (never flagged).
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

    def test_slip_name_mismatch_is_probable_via_red_chip(self):
        # Owner 2026-07-07 red-chip ladder: a slip in a different name is a RED Name chip (−1), no
        # longer a hard gap — a lone mismatch on a genuine slip lands Probable ('review'). (Still an
        # application_completeness submission blocker — a separate gate.)
        _add_doc(self.app, 'results_slip', student_verdict='name_mismatch')
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')
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

    def test_hash71_band_confirmed_mismatch_gets_confident_copy(self):
        # #71 (owner 2026-07-08): slip reads A + 'Cemerlang Tinggi' (letter+band agree, and A-
        # could not degrade INTO 'cemerlang tinggi'), student typed A- -> the verdict emits the
        # CONFIDENT academic_grade_band_mismatch copy ("the typed grade is wrong"), not the
        # "check by eye" academic_grade_uncertain. Band stays review (Probable).
        self.profile.grades = {'b_tamil': 'A-'}
        self.profile.save()
        _add_doc(self.app, 'results_slip', student_verdict='ok', name_match='found',
                 fields={'results': [{'subject': 'Bahasa Tamil', 'grade': 'A',
                                      'band': 'Cemerlang Tinggi'}]})
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')
        codes = _codes(f['unresolved'])
        self.assertIn('academic_grade_band_mismatch', codes)
        self.assertNotIn('academic_grade_uncertain', codes)

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

    def test_str_pre_wizard_is_gap_not_green(self):
        # Income green needs the whole cluster (STR + earner IC + relationship); a bare STR
        # before the wizard is walked is "no income info yet" → red (can't verify).
        _add_doc(self.app, 'str', name_match='found')
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('income_earner_undeclared', _codes(f['unresolved']))

    def test_wizard_not_walked_is_gap_undeclared(self):
        # Nothing provided (no route/earner) → red, like a missing IC / slip / offer.
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
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

    def test_str_salinan_without_approval_is_unsure_not_verified(self):
        # A SALINAN / application record: recipient + current year read, but NO approval status
        # ('Lulus'/'Diluluskan') and no payment. Approval can't be confirmed → unreadable → the
        # band matrix puts it at Unsure (recommend/amber), NOT verified and NOT a blue review.
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'year': '2026'})   # no status
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('str_not_current', _codes(f['unresolved']))
        self.assertNotIn('str_verified', _codes(f['evidence']))

    def test_str_stale_year_is_unsure(self):
        # Lulus but a PRIOR-year date (stale): Status green, Current amber → Unsure (recommend),
        # not a blue review off the verified earner IC (str-proof-spec.md band matrix).
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'Lulus', 'year': '2023'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('str_not_current', _codes(f['unresolved']))

    def test_misread_status_no_longer_rescued_by_amount(self):
        # Owner 2026-07-07: the paid-AMOUNT rescue is retired. #23's misread "Lulus"→"STR" status,
        # even with an amount on the page, no longer greens — approval needs a readable "Lulus"
        # (a genuine STR shows it), so a misread status reads 'unreadable' → Unsure (amber), which
        # the student/officer settles with a clean re-read, never off a number.
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'STR',
                         'source_type': 'semakan_status', 'amount': 'RM850'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')                 # amber / Unsure
        self.assertIn('str_not_current', _codes(f['unresolved']))  # unreadable — needs a clean re-read

    def test_str_wrong_type_no_salary_is_unsure_not_double_flagged_genuine(self):
        # A genuine payslip / SARA letter in the STR slot (source_type='unknown') → wrong_type. With
        # NO salary docs to assess, the failed STR → Unsure (recommend/amber). The income fact raises
        # str_not_current(wrong_type) but NOT document_not_genuine — wrong KIND, not a forgery (#13/SARA).
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        d = _add_doc(self.app, 'str', student_verdict='ok',
                     fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'approved',
                             'source_type': 'unknown'})
        d.vision_fields['authenticity'] = {'status': 'suspect', 'reason': 'no STR signatures'}
        d.save(update_fields=['vision_fields'])
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        codes = _codes(f['unresolved'])
        self.assertIn('str_not_current', codes)
        self.assertNotIn('document_not_genuine', codes)

    def _str_route_with_ceiling(self, size):
        # STR route, father earner (IC present + patronymic match via _wizard's name), cohort gross
        # ceiling set, household size given — the setup the salary fall-through reads.
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        self.cohort.income_ceiling = 5860
        self.cohort.save()
        self.profile.household_size = size
        self.profile.save()

    def test_wrong_type_str_falls_through_to_salary_unsure(self):
        # #13: a payslip in the STR slot (wrong_type) → assess salary. Annualised ~RM7,064 (YTD ÷ 12)
        # for household 5 sits near the line (thin breach-room) → Unsure (recommend), NOT a blue read
        # off the verified earner IC. The verdict still says "not an STR" too.
        self._str_route_with_ceiling(5)
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'approved', 'source_type': 'unknown'})
        _add_doc(self.app, 'salary_slip', member='father',
                 fields={'gross_income': 'RM3,800', 'gross_income_ytd': 'RM84,774.59'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')                 # amber / Unsure
        codes = _codes(f['unresolved'])
        self.assertIn('str_not_current', codes)
        self.assertIn('income_salary_unsure', codes)

    def test_wrong_type_str_falls_through_to_salary_probable(self):
        # SARA-like: a pension RM687.50 in the STR slot (wrong_type) → assess salary. Far under the
        # line for a large household (big breach-room) → Probable (review + green salary evidence).
        self._str_route_with_ceiling(6)
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'approved', 'source_type': 'unknown'})
        _add_doc(self.app, 'salary_slip', member='father', fields={'gross_income': 'RM687.50'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('income_salary_probable', _codes(f['evidence']))

    def test_wrong_type_str_salary_over_b40_fails(self):
        # STR fails → salary route → the salary clearly exceeds the B40 line → income fact FAILS
        # (gap / RED). Advisory only (officer still places the verdict), but the tile is red.
        self._str_route_with_ceiling(3)
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'MURUGAN A/L KESAVAN', 'status': 'approved', 'source_type': 'unknown'})
        _add_doc(self.app, 'salary_slip', member='father', fields={'gross_income': 'RM12,000'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')                       # red / Fail
        codes = _codes(f['unresolved'])
        self.assertIn('income_above_b40_line', codes)
        self.assertIn('str_not_current', codes)

    def test_str_recipient_not_earner_is_recommend_amber(self):
        # V5 (#10): a POSITIVE recipient mismatch bands Unsure (amber) per spec §8 — never a
        # blue 'review' read off the verified earner-IC green (the STR provably belongs to
        # someone else, so nothing about THIS household's income is probable).
        self._wizard(route='str', earner='father')
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN')
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'SOMEONE ELSE BIN OTHER', 'status': 'Lulus', 'year': '2026'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
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
        # A clean CURRENT STR whose recipient IS the earner, so the STR itself doesn't drive the
        # band — the only concern is the father patronymic mismatch → review.
        _add_doc(self.app, 'str', student_verdict='ok', name_match='found',
                 fields={'recipient_name': 'RAJU A/L SAMY', 'status': 'Lulus',
                         'year': '2026', 'source_type': 'letter'})
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

    def test_mother_route_wrong_type_bc_is_gap_with_reupload_ticket(self):
        # #27 (owner 2026-07-08): a genuine CURRENT STR matching the mother's IC, but the doc in
        # the birth-certificate slot is NOT a birth certificate (genuineness not_birth_certificate,
        # child/father fields empty). The mother↔student link is unprovable → gap with the SPECIFIC
        # birth_cert_not_genuine re-upload ticket (resolution-mapped, student-facing), and the
        # generic officer-only document_not_genuine caveat is suppressed (no double flag).
        self._wizard(route='str', earner='mother')
        _parent_ic(self.app, 'KAMALA A/P RAMAN', nric='860419-43-5610')
        d = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                     fields={'bc_child_name': '', 'bc_mother_name': 'KAMALA A/P RAMAN',
                             'bc_mother_nric': '860419-43-5610'})
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'not_birth_certificate',
                                                              'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'recipient_nric': '860419-43-5610',
                         'status': 'Lulus', 'year': '2026', 'source_type': 'letter'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        codes = _codes(f['unresolved'])
        self.assertIn('birth_cert_not_genuine', codes)
        self.assertNotIn('document_not_genuine', codes)

    def test_wrong_type_bc_fields_never_confirm_relationship(self):
        # Guard: even if the wrong-type doc's extracted fields look COMPLETE and matching (child =
        # student, mother = earner IC), they prove nothing — the fields are blanked, so neither the
        # STR precedence nor the route logic can green off a document that isn't a birth certificate.
        self._wizard(route='str', earner='mother')
        _parent_ic(self.app, 'KAMALA A/P RAMAN')
        d = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                     fields={'bc_child_name': 'DIVASHINI A/P MURUGAN',
                             'bc_mother_name': 'KAMALA A/P RAMAN'})
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'not_birth_certificate',
                                                              'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        _add_doc(self.app, 'str', student_verdict='ok',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'status': 'Lulus', 'year': '2026'})
        f = _facts(self.app)['income']
        self.assertNotEqual(f['status'], 'verified')
        self.assertIn('birth_cert_not_genuine', _codes(f['unresolved']))

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

    def test_no_members_is_gap_undeclared(self):
        # Salary route with no member declared → no income info → red (see STR route).
        self._wizard([])
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
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

    def _undeclared(self):
        # A student who declared NOTHING about a pathway (the #127 all-blank case).
        self.app.chosen_pathway = ''
        self.app.intended_pathway = ''
        self.app.pre_u_track = ''
        self.app.chosen_programme = {}
        self.app.save()

    def _genuine_offer(self, **overrides):
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, **overrides))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'genuine', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        return d

    def test_undeclared_ambiguous_offer_directs_to_profile_and_is_probable(self):
        # Owner 2026-07-15 (#127): a genuine PISMP offer but NO declared pathway → not silently
        # Certain. PISMP names no aliran on the letter → ambiguous → send the student to the profile
        # to pick their course (pathway_undeclared), and the band sits at Probable ('review').
        self._undeclared()
        self._genuine_offer(programme='Ijazah Sarjana Muda Perguruan (PISMP)',
                            institution='IPG Kampus Temenggong Ibrahim')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')                       # Probable, NOT verified
        self.assertIn('pathway_undeclared', _codes(f['unresolved']))
        self.assertNotIn('pathway_confirm', _codes(f['unresolved']))

    def test_undeclared_resolvable_offer_asks_confirm_and_is_probable(self):
        # A pre-U (STPM) offer whose stream parses + NO declaration → the one-tap "is this where
        # you're going?" confirm (not the profile redirect); still Probable until confirmed.
        self._undeclared()
        self._genuine_offer(programme='Tingkatan Enam (Sains Sosial)', institution='SMK Contoh')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('pathway_confirm', _codes(f['unresolved']))
        self.assertNotIn('pathway_undeclared', _codes(f['unresolved']))

    def test_undeclared_but_fake_offer_not_asked(self):
        # A FAKE offer with no declaration is NOT asked "is this where you're going?" — it's already
        # flagged by genuineness; only a GENUINE official offer is a real pathway to confirm (#12/#109).
        self._undeclared()
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, programme='Program Asasi UTM', institution='UTM SPACE'))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'not_offer_letter', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        codes = _codes(_facts(self.app)['pathway']['unresolved'])
        self.assertNotIn('pathway_undeclared', codes)
        self.assertNotIn('pathway_confirm', codes)

    def test_offer_is_resolvable_pismp_vs_preu(self):
        from apps.scholarship.offer_pathway import offer_is_resolvable
        self.assertTrue(offer_is_resolvable('Tingkatan Enam (Sains Sosial)', 'SMK X'))
        self.assertFalse(offer_is_resolvable('Ijazah Sarjana Muda Perguruan (PISMP)', 'IPG Kampus Y'))

    def test_undeclared_suspect_offer_is_asked(self):
        # Owner 2026-07-18: a SUSPECT (scored, not fake) offer still gets a hearing — a suspect PISMP
        # offer with no declaration → the profile picker (pathway_undeclared), same as a genuine one.
        self._undeclared()
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, programme='Ijazah Sarjana Muda Perguruan (PISMP)',
                                 institution='IPG Kampus Temenggong Ibrahim'))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'suspect', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        self.assertIn('pathway_undeclared', _codes(_facts(self.app)['pathway']['unresolved']))

    def test_undeclared_unknown_offer_not_asked(self):
        # An UNSCORED offer (no authenticity → unknown) gets NO hearing — we don't ask which pathway
        # until the offer's genuineness is actually scored (owner 2026-07-18).
        self._undeclared()
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields=dict(self._OWN_OFFER, programme='Tingkatan Enam (Sains Sosial)', institution='SMK X'))
        codes = _codes(_facts(self.app)['pathway']['unresolved'])
        self.assertNotIn('pathway_undeclared', codes)
        self.assertNotIn('pathway_confirm', codes)

    def test_not_confirmed_type_switch_asks_switch_not_generic_confirm(self):
        # Owner 2026-07-18: a TYPE switch fires regardless of confirmed-state. Declared STPM, a genuine
        # Matriculation offer (different family), NOT yet confirmed → pathway_type_switch, and the
        # generic pathway_confirm is suppressed (if/elif → at most one).
        self.app.chosen_pathway = 'stpm'
        self.app.pre_u_institution = 'SMK X'
        self.app.save()
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, programme='Program Matrikulasi',
                                 institution='Kolej Matrikulasi Melaka'))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'genuine', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        codes = _codes(_facts(self.app)['pathway']['unresolved'])
        self.assertIn('pathway_type_switch', codes)
        self.assertNotIn('pathway_confirm', codes)

    def _offer(self, auth_status):
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        d.vision_fields = dict(d.vision_fields,
                               authenticity={'status': auth_status, 'reason': 'x',
                                             'probability': 0.4, 'model_version': '1.1'})
        d.save(update_fields=['vision_fields'])
        return d

    def test_suspect_offer_is_unsure_step_plus_pathway_chip(self):
        # Owner 2026-07-08 (#131, refining the locked #31): a non-genuine document establishes NO
        # pathway, so the Pathway VARIABLE is red even when the programme text matches — it stacks
        # with the step. suspect(−1) + pathway-not-established(−1) = −2 → 'recommend' (🟡 Unsure).
        self._offer('suspect')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('document_not_genuine', _codes(f['unresolved']))

    def test_fake_offer_is_fail_step_plus_pathway_chip(self):
        # The #84 arithmetic (owner 2026-07-08): fake(−2) + pathway-not-established(−1) = −3 →
        # 🔴 Fail, with the confident 'offer_not_official' caveat (an award CONFIDENT_DISQUALIFIER).
        self._offer('not_offer_letter')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('offer_not_official', _codes(f['unresolved']))

    def test_genuine_official_offer_still_verifies(self):
        self._offer('genuine')
        self.assertEqual(_facts(self.app)['pathway']['status'], 'verified')

    _WRONG_OFFER = {'candidate_name': 'SOMEONE ELSE BIN OTHER', 'candidate_nric': '990101-01-1234',
                    'institution': 'KOLEJ X', 'programme': 'DIPLOMA Y'}

    def test_fake_offer_wrong_person_is_fail_hash12(self):
        # The #12 worked example (owner-verified): a fake offer (p<0.35 → not_offer_letter, step −2)
        # whose Name + IC also mismatch (2 red chips) → −2 + −2 = −4 → floored 🔴 Fail.
        d = _add_doc(self.app, 'offer_letter', student_verdict='name_mismatch', fields=self._WRONG_OFFER)
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'not_offer_letter', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        self.assertEqual(_facts(self.app)['pathway']['status'], 'gap')

    def test_genuine_offer_wrong_person_is_unsure_two_chips(self):
        # A GENUINE wrong-person offer (Name + IC both mismatch = 2 red chips, step 0) → −2 → 🟡
        # Unsure (amber, family slip-up), NOT red. A LONE name/IC slip would be −1 (Probable).
        d = _add_doc(self.app, 'offer_letter', student_verdict='name_mismatch', fields=self._WRONG_OFFER)
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'genuine', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('offer_name_mismatch', _codes(f['unresolved']))


    def test_offer_missing_ic_field_is_red_chip_probable(self):
        # Owner 2026-07-07: a required IDENTITY field the offer doesn't show (candidate_nric empty on
        # an extracted offer → student_offer_check 'unreadable') is a RED IC chip, matching the cockpit
        # (factStatus reds 'unreadable'). A lone missing IC on a genuine offer → −1 → 🔵 Probable, NOT
        # Certain (the tile now agrees with the red IC chip the reviewer sees).
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, candidate_nric=''))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'genuine', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        self.assertEqual(_facts(self.app)['pathway']['status'], 'review')

    def test_offer_missing_ic_plus_pathway_mismatch_plus_suspect_is_fail_hash64(self):
        # The #64 worked example: a suspect offer (step −1) whose candidate IC is missing (−1 red chip)
        # AND whose place clashes with the declaration (−1 red Pathway chip) = −3 → 🔴 Fail.
        # (After the owner re-runs the offer under 1.4.0 → fake, step −2 → −4, still Fail.)
        self.app.chosen_pathway = 'asasi'          # same family as the Foundation offer (within-type clash)
        self.app.pre_u_institution = 'SMK Mentakab'; self.app.save()
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=dict(self._OWN_OFFER, candidate_nric='',
                                 institution='i-CATS UNIVERSITY COLLEGE', programme='FOUNDATION IN MANAGEMENT'))
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'suspect', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('pathway_confirm', _codes(f['unresolved']))

    def test_offer_matching_declared_is_verified_no_nag(self):
        # Declared institution matches the offer (naming quirk) → verified, no query.
        self.app.pre_u_institution = 'KM Melaka'
        self.app.save()
        _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=self._OWN_OFFER)
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'verified')
        self.assertNotIn('pathway_confirm', _codes(f['unresolved']))

    def test_offer_clashing_with_declared_asks_to_confirm(self):
        # Declared the SAME pathway type (STPM) but a genuinely different SCHOOL → the offer clashes on
        # institution (a within-family Case-3 clash) → the student confirms which is final, so 'review'.
        self.app.chosen_pathway = 'stpm'           # same family as the Tingkatan Enam offer
        self.app.pre_u_institution = 'SMK Mentakab'
        self.app.save()
        clash = dict(self._OWN_OFFER, institution='SMK Temerloh', programme='Tingkatan Enam')
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok', fields=clash)
        d.vision_fields = dict(d.vision_fields, authenticity={'status': 'genuine', 'reason': 'x'})
        d.save(update_fields=['vision_fields'])
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

    def test_offer_lone_name_mismatch_is_probable(self):
        # Owner 2026-07-07 red-chip ladder: a LONE Name mismatch on a genuine-scoring offer (IC
        # matches) is 1 red chip → −1 → 'review' (🔵 Probable), not the old fixed 'recommend'.
        _add_doc(self.app, 'offer_letter', student_verdict='name_mismatch',
                 fields={'candidate_name': 'SOMEONE ELSE', 'candidate_nric': '080115-05-0132'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('offer_name_mismatch', _codes(f['unresolved']))

    def test_offer_lone_ic_mismatch_is_probable(self):
        # A LONE IC mismatch (name matches) is likewise 1 red chip → −1 → 'review' (🔵 Probable).
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                         'candidate_nric': '999999-99-9999'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'review')
        self.assertIn('offer_name_mismatch', _codes(f['unresolved']))

    def test_offer_notice_without_identity_is_no_identity_unsure(self):
        # Sharvin: a general UTM NOTICE whose body read fine (issuer/institution/programme present) but
        # carries NO candidate name or IC. Both required identity fields are missing → 2 red chips →
        # 🟡 Unsure (owner 2026-07-07: a placeholder without identity can't confirm the pathway). The
        # officer is still told "no identity on it" (offer_no_identity), never "ask for a clearer copy".
        _add_doc(self.app, 'offer_letter', student_verdict='ok',
                 fields={'candidate_name': '', 'candidate_nric': '',
                         'institution': 'Universiti Teknologi Malaysia',
                         'programme': 'Program Asasi dan Diploma UTM'})
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'recommend')
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
        # A shouty offer programme ("PROGRAM MATRIKULASI") is re-cased to Title Case so it never
        # reaches the sponsor pool shouting; the institution is written as-is (its own canon path).
        self.assertEqual(self.app.chosen_programme.get('course_name'), 'Program Matrikulasi')
        self.assertEqual(self.app.chosen_programme.get('institution'), 'KOLEJ MATRIKULASI MELAKA')
        self.assertEqual(self.app.chosen_programme.get('source'), 'offer_letter_confirmed')
        # The verdict now reads verified.
        self.assertEqual(_facts(self.app)['pathway']['status'], 'verified')

    def test_confirm_pathway_no_offer_is_noop(self):
        from apps.scholarship import services
        self.assertFalse(services.confirm_pathway(self.app))
        self.app.refresh_from_db()
        self.assertIsNone(self.app.pathway_confirmed_at)

    def test_no_offer_is_gap_offer_required(self):
        # Offer letter is compulsory — no offer → red (can't verify / blocked); the
        # declared pathway rides along as context.
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('offer_letter_missing', _codes(f['unresolved']))
        self.assertIn('pathway_declared', _codes(f['evidence']))

    def test_no_offer_undeclared_is_gap(self):
        self.app.chosen_pathway = ''
        self.app.intended_pathway = ''
        self.app.save()
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('offer_letter_missing', _codes(f['unresolved']))


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
        # Income: gap (red) — she hasn't walked the income wizard yet (no income_earner),
        # so there's no income information to check at all (consistent with a missing
        # IC / slip / offer: nothing provided → can't verify).
        self.assertEqual(facts['income']['status'], 'gap')
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
        # Salary slip data points: gross amount + period.
        self.assertIn({'key': 'amount', 'value': 'RM2000'}, chk['points'])
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

    def test_cluster_nudges_add_ic_when_proof_but_no_ic(self):
        # The single cluster coach now speaks even before the IC: a payslip with no IC for
        # that member → "add the IC" (this nudge moved off the payslip row into the cluster).
        from apps.scholarship.income_engine import income_cluster_advice
        self._slip('father', 'MURUGAN A/L KESAVAN')        # proof, no father IC
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'income_ic_needed')

    def test_cluster_silent_when_nothing_uploaded(self):
        from apps.scholarship.income_engine import income_cluster_advice
        self.assertEqual(income_cluster_advice(self.app, 'father'), '')

    def test_cluster_nudges_salary_slip_when_ic_in_but_no_slip(self):
        # Salary route: IC matches but the salary slip (the income proof) isn't up → nudge it
        # as the next step (was silent for a father, who needs no relationship doc).
        from apps.scholarship.income_engine import income_cluster_advice
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'income_proof_needed')

    def test_cluster_salary_slip_comes_before_the_birth_certificate(self):
        # Mother on the salary route: IC matches; with neither the salary slip nor the BC up,
        # the SALARY SLIP is nudged first (the income proof), not the birth certificate.
        from apps.scholarship.income_engine import income_cluster_advice
        self.app.income_working_members = ['mother']
        self.app.save()
        _parent_ic(self.app, 'KAMALA A/P RAMAN', member='mother', nric='770101-01-2222')
        self.assertEqual(income_cluster_advice(self.app, 'mother'), 'income_proof_needed')


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

    def _str(self, *, year='2026', status='diluluskan'):
        return _add_doc(self.app, 'str', student_verdict='ok', member='',
                        fields={'recipient_name': 'MURUGAN A/L KESAVAN',
                                'recipient_nric': '600101-01-1111',
                                'status': status, 'year': year, 'amount': 'RM500'})

    def test_str_stale_voiced_in_cluster_without_ic(self):
        # STR currency now lives in the single cluster voice — even before the IC arrives.
        from apps.scholarship.income_engine import income_cluster_advice
        self._str(year='2024')                                  # older than cohort 2026 → stale
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'str_not_current')

    def test_str_stale_voiced_in_cluster_with_ic(self):
        from apps.scholarship.income_engine import income_cluster_advice
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='', nric='600101-01-1111')
        self._str(year='2024')
        self.assertEqual(income_cluster_advice(self.app, 'father'), 'str_not_current')

    def test_str_current_cluster_is_silent(self):
        # Father needs NO relationship doc (patronymic) — once the IC matches the STR, silent.
        from apps.scholarship.income_engine import income_cluster_advice
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='', nric='600101-01-1111')
        self._str(year='2026')
        self.assertEqual(income_cluster_advice(self.app, 'father'), '')

    def test_ic_proof_match_surfaced_for_student(self):
        # The earner IC now reports whether it MATCHES the income proof (the STR) — the
        # student-facing "Matches the STR document" check.
        from apps.scholarship.income_engine import student_income_ic_check
        ic = _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='', nric='600101-01-1111')
        self._str(year='2026')                              # recipient MURUGAN, nric 600101-01-1111
        chk = student_income_ic_check(ic)
        self.assertEqual(chk['proof_kind'], 'str')
        self.assertEqual(chk['proof_name_status'], 'match')
        self.assertEqual(chk['proof_nric_status'], 'match')

    def test_mother_rel_doc_needed_when_ic_in_but_no_bc(self):
        # Mother earner: IC in + matches the STR, but the birth certificate (the link to the
        # student) is still missing → Gopal nudges for it (the last required step).
        from apps.scholarship.income_engine import income_cluster_advice
        self.app.income_earner = 'mother'
        self.app.save()
        _parent_ic(self.app, 'KAMALA A/P RAMAN', member='', nric='770101-01-2222')
        _add_doc(self.app, 'str', student_verdict='ok', member='',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'recipient_nric': '770101-01-2222',
                         'status': 'diluluskan', 'year': '2026', 'amount': 'RM500'})
        self.assertEqual(income_cluster_advice(self.app, 'mother'), 'income_rel_doc_needed')

    def test_mother_silent_once_bc_uploaded(self):
        from apps.scholarship.income_engine import income_cluster_advice
        self.app.income_earner = 'mother'
        self.app.save()
        _parent_ic(self.app, 'KAMALA A/P RAMAN', member='', nric='770101-01-2222')
        _add_doc(self.app, 'str', student_verdict='ok', member='',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'recipient_nric': '770101-01-2222',
                         'status': 'diluluskan', 'year': '2026'})
        _add_doc(self.app, 'birth_certificate', student_verdict='ok', member='',
                 fields={'bc_child_name': 'DIVASHINI A/P MURUGAN', 'bc_mother_name': 'KAMALA A/P RAMAN'})
        self.assertEqual(income_cluster_advice(self.app, 'mother'), '')

    def test_mother_rel_doc_unreadable_when_bc_uploaded_but_unread(self):
        # BC processed but no names read (unclear, or an IC sent as a birth cert): not a name
        # CLASH and not MISSING, so Gopal must still speak (was silent before). The BC is a
        # field-extraction doc, so its "processed" stamp is vision_fields_run_at, NOT
        # vision_run_at (which only the IC path sets) — mirror that exactly here.
        from apps.scholarship.income_engine import income_cluster_advice
        self.app.income_earner = 'mother'
        self.app.save()
        _parent_ic(self.app, 'KAMALA A/P RAMAN', member='', nric='770101-01-2222')
        _add_doc(self.app, 'str', student_verdict='ok', member='',
                 fields={'recipient_name': 'KAMALA A/P RAMAN', 'recipient_nric': '770101-01-2222',
                         'status': 'diluluskan', 'year': '2026'})
        bc = _add_doc(self.app, 'birth_certificate', student_verdict='unreadable', member='',
                      fields={'bc_child_name': '', 'bc_mother_name': ''})
        bc.vision_run_at = None                      # a birth cert NEVER gets the IC-path stamp
        bc.vision_fields_run_at = timezone.now()     # field extraction ran (and read nothing)
        bc.save(update_fields=['vision_run_at', 'vision_fields_run_at'])
        self.assertEqual(income_cluster_advice(self.app, 'mother'),
                         'income_rel_doc_unreadable')


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

    def test_above_ceiling_is_gap_red(self):
        # V5 (#10): over-the-line = RED on both routes (spec §8 rule 1) — the salary route now
        # bands the same household economics the same colour as the STR fall-through. Advisory
        # only; the officer still places the final verdict.
        self.profile.household_size = 2
        self.profile.save()
        self._father(gross='RM9,900.04')   # 9900 / 2 = 4950 >= 1584
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
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


class TestIncomeDeclared(TestCase):
    """Phase 2A — a working member DECLARES an informal wage (no payslip). Accepted on a
    valid STR (the means-test) or a supporting doc → feeds per-capita; otherwise the income
    fact is Unsure (recommend) with a firm 'proof required' item + an Action-Centre request."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='dc', name='B40', year=2026,
                                                      per_capita_ceiling=1584)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'decl-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['father'],
            income_declared={'father': 1500})
        # A confirmed father earner (IC + patronymic) so the cluster otherwise adds up.
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')

    def _str(self):   # a valid (approved, dateless → unconfirmed) STR document
        _add_doc(self.app, 'str', fields={'status': 'Lulus', 'source_type': ''})

    def test_unproven_declared_is_recommend_with_evidence_ask(self):
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_declared_needs_evidence', _codes(f['unresolved']))

    def test_valid_str_accepts_declared_into_per_capita(self):
        self._str()                              # 1500 / 4 = 375 < 1584
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('income_declared_accepted_str', _codes(f['evidence']))
        self.assertIn('income_per_capita_ok', _codes(f['evidence']))

    def test_support_doc_accepts_declared_when_no_str(self):
        # V1 (#2): a support doc backs the declared income only when it READ (student_verdict='ok').
        _add_doc(self.app, 'income_support_doc', member='father',
                 student_verdict='ok', fields={'name': 'ABU', 'amount': 'RM1,200'})
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('income_declared_accepted_evidenced', _codes(f['evidence']))

    def test_blank_support_doc_does_not_accept_declared(self):
        # V1 (#2): a blank support doc (student_verdict='wrong_doc') leaves the declared income
        # UNPROVEN — the income fact must not read 'verified' off an unread image.
        _add_doc(self.app, 'income_support_doc', member='father',
                 student_verdict='wrong_doc', fields={})
        f = _facts(self.app)['income']
        self.assertNotIn('income_declared_accepted_evidenced', _codes(f['evidence']))

    def test_declared_over_line_is_gap_red(self):
        # A declared figure accepted by STR but over the line → gap/RED (V5 #10: over = red on
        # both routes; advisory — the tile is red but nothing auto-rejects).
        self.profile.household_size = 1
        self.profile.save()
        self.app.income_declared = {'father': 5000}   # 5000 / 1 = 5000 >= 1584
        self.app.save()
        self._str()
        f = _facts(self.app)['income']
        self.assertEqual(f['status'], 'gap')
        self.assertIn('income_above_b40_line', _codes(f['unresolved']))


class TestSalaryRouteStrSettle(TestCase):
    """P3 (str-proof-spec.md §8): a valid, non-breached STR settles B40 on the SALARY route too — the
    STR is the household's own means-test, so a family pushed onto the salary route (a working member
    alongside the STR) is no longer falsely 'unsure' when the salary headroom can't compute. #45
    (current STR → Certain), #63 (unconfirmed STR → Probable). Invalid / stranger / unrelated STRs
    still fall through to the salary assessment (V5 preserved)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='p3', name='B40', year=2026,
                                                      per_capita_ceiling=1584)

    def _app(self, *, name='DIVASHINI A/P MURUGAN', **kw):
        profile = StudentProfile.objects.create(
            supabase_user_id=f'p3-{self.id()}', name=name, nric='080115-05-0132', household_size=4)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted', **kw)

    def test_current_str_recipient_confirmed_settles_green(self):
        # #45: the father IS the STR recipient (current STR) but drives e-hailing with no payslip;
        # the salary headroom can't compute → pre-P3 this fell to 'unsure'. Now Certain (green).
        app = self._app(name='YUKANESWARY A/P SARAVANAN', income_route='salary', income_earner='mother',
                        income_working_members=['father', 'mother'])
        _parent_ic(app, 'SARAVANAN A/L CHANTHIRAN', member='father')   # patronymic → father confirmed
        _parent_ic(app, 'REMAVATHY A/P SELVARAJOO', member='mother')
        _add_doc(app, 'birth_certificate', student_verdict='ok',
                 fields={'bc_child_name': 'YUKANESWARY A/P SARAVANAN',
                         'bc_mother_name': 'REMAVATHY A/P SELVARAJOO'})
        _add_doc(app, 'str', student_verdict='ok', member='father',
                 fields={'recipient_name': 'SARAVANAN A/L CHANTHIRAN', 'status': 'Lulus', 'year': '2026'})
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('str_verified', _codes(f['evidence']))

    def test_unconfirmed_str_recipient_confirmed_is_probable_blue(self):
        # #63: mother's Lulus STR with no date (unconfirmed) whose recipient is the confirmed mother →
        # Probable (blue), not a false 'unsure'.
        app = self._app(name='JAYASHREE A/P RAVI', income_route='salary',
                        income_working_members=['mother'])
        _parent_ic(app, 'SELVI A/P VELLAYAN', member='mother')
        _add_doc(app, 'birth_certificate', student_verdict='ok',
                 fields={'bc_child_name': 'JAYASHREE A/P RAVI', 'bc_mother_name': 'SELVI A/P VELLAYAN'})
        _add_doc(app, 'str', student_verdict='ok', member='mother',
                 fields={'recipient_name': 'SELVI A/P VELLAYAN', 'status': 'Lulus'})   # no year → unconfirmed
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'review')
        self.assertIn('str_verified', _codes(f['evidence']))
        self.assertIn('str_not_current', _codes(f['unresolved']))

    def test_stranger_str_does_not_settle(self):
        # Fraud guard: an approved current STR whose recipient matches NO household member's IC proves
        # nothing about this family → falls through to the salary assessment (not greened).
        app = self._app(name='YUKANESWARY A/P SARAVANAN', income_route='salary',
                        income_working_members=['father'])
        _parent_ic(app, 'SARAVANAN A/L CHANTHIRAN', member='father')
        _add_doc(app, 'str', student_verdict='ok', member='father',
                 fields={'recipient_name': 'SOMEONE ELSE BINTI NOBODY', 'status': 'Lulus', 'year': '2026'})
        f = _facts(app)['income']
        self.assertNotEqual(f['status'], 'verified')
        self.assertNotIn('str_verified', _codes(f['evidence']))

    def test_wrong_type_str_still_falls_through(self):
        # V5 preserved: a non-STR in the STR slot (wrong_type) never settles B40 on the salary route.
        app = self._app(name='YUKANESWARY A/P SARAVANAN', income_route='salary',
                        income_working_members=['father'])
        _parent_ic(app, 'SARAVANAN A/L CHANTHIRAN', member='father')
        _add_doc(app, 'str', student_verdict='ok', member='father',
                 fields={'recipient_name': 'SARAVANAN A/L CHANTHIRAN', 'status': 'approved',
                         'source_type': 'unknown'})
        f = _facts(app)['income']
        self.assertNotEqual(f['status'], 'verified')

    def test_current_str_recipient_unrelated_does_not_green(self):
        # Recipient matches a member's IC, but that member's relationship to the student isn't
        # confirmed (a mononym / non-patronymic name, no BC link) → the STR alone doesn't settle B40.
        app = self._app(name='AH HOCK', income_route='salary', income_working_members=['father'])
        _parent_ic(app, 'TAN AH KOW', member='father')       # no patronymic link to the student
        _add_doc(app, 'str', student_verdict='ok', member='father',
                 fields={'recipient_name': 'TAN AH KOW', 'status': 'Lulus', 'year': '2026'})
        f = _facts(app)['income']
        self.assertNotEqual(f['status'], 'verified')
        self.assertNotIn('str_verified', _codes(f['evidence']))

    def test_45_str_names_father_but_prints_mother_nric_settles(self):
        # #45 EXACT (owner 2026-07-07): a genuine Lulus STR letter NAMES the father but prints the
        # MOTHER's IC number (a household benefit covering both spouses). Exhaustive household match
        # hits the father by NAME (and the mother by NRIC) → a genuine household STR → settles B40
        # GREEN, route-/tag-agnostic (declared earner 'mother', STR mistagged 'mother', route salary).
        app = self._app(name='YUKANESWARY A/P SARAVANAN', income_route='salary', income_earner='mother',
                        income_working_members=['father', 'mother'])
        _parent_ic(app, 'SARAVANAN A/L CHANTHIRAN', member='father', nric='760429-10-5289')
        _parent_ic(app, 'REMAVATHY A/P SELVARAJOO', member='mother', nric='880328-43-5234')
        _add_doc(app, 'birth_certificate', student_verdict='ok',
                 fields={'bc_child_name': 'YUKANESWARY A/P SARAVANAN',
                         'bc_mother_name': 'REMAVATHY A/P SELVARAJOO'})
        _add_doc(app, 'str', student_verdict='ok', member='mother',      # mistagged; name is the father's
                 fields={'recipient_name': 'SARAVANAN A/L CHANTHIRAN',
                         'recipient_nric': '880328-43-5234',             # ← the MOTHER's IC number
                         'status': 'Lulus', 'year': '2026'})
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('str_verified', _codes(f['evidence']))

    def test_str_nric_match_alone_settles(self):
        # Either-match on ONE field: the recipient NAME is an OCR garble that hits no IC, but the
        # recipient NRIC matches the father's IC → still a household STR → settles.
        app = self._app(name='YUKANESWARY A/P SARAVANAN', income_route='str', income_earner='father')
        _parent_ic(app, 'SARAVANAN A/L CHANTHIRAN', member='father', nric='760429-10-5289')
        _add_doc(app, 'str', student_verdict='ok', member='father',
                 fields={'recipient_name': 'UNREADABLE GARBLE XYZ', 'recipient_nric': '760429-10-5289',
                         'status': 'Lulus', 'year': '2026'})
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('str_verified', _codes(f['evidence']))


class TestUnemploymentEvidence(TestCase):
    """Phase 2B — an EPF (all-zeros employer) corroborating an unemployed member surfaces as
    soft income evidence (unemployment_epf_corroborated), on both routes; never a gate."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='ue2', name='B40', year=2026,
                                                      per_capita_ceiling=1584)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'unemp-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=4)
        # Salary route, mother works; father is unemployed with an all-zeros EPF.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['mother'],
            father_occupation='unemployed')
        _add_doc(self.app, 'epf', member='father', fields={'employer_number': '000000000'})

    def test_corroborated_evidence_present(self):
        f = _facts(self.app)['income']
        self.assertIn('unemployment_epf_corroborated', _codes(f['evidence']))

    def test_absent_without_epf(self):
        self.app.documents.filter(doc_type='epf').delete()
        f = _facts(self.app)['income']
        self.assertNotIn('unemployment_epf_corroborated', _codes(f['evidence']))


class TestHouseholdSizeConfirm(TestCase):
    """Phase 2C (P4) — when the people described outnumber the stated household size, a soft
    reviewer 'confirm household size' evidence item appears (over-count only; never a gate)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='hs', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'hs-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=2)
        # Described = student + father + mother = 3, but household_size entered as 2 → over-count.
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['father'],
            father_occupation='gov', mother_occupation='homemaker')

    def test_overcount_flag_in_income_evidence(self):
        f = _facts(self.app)['income']
        self.assertIn('household_size_confirm', _codes(f['evidence']))

    def test_no_flag_when_size_consistent(self):
        self.profile.household_size = 4
        self.profile.save()
        f = _facts(self.app)['income']
        self.assertNotIn('household_size_confirm', _codes(f['evidence']))


class TestUtilityAndEpf(TestCase):
    """EPF shows the MONTHLY contribution (not the lifetime balance) as the income figure;
    utility bills are an address check + a soft per-capita / hardship signal."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='ue', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'ue-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['father'])

    def test_epf_points_use_monthly_contribution_not_balance(self):
        from apps.scholarship.income_engine import student_income_proof_check
        _parent_ic(self.app, 'MURUGAN A/L KESAVAN', member='father')
        epf = _add_doc(self.app, 'epf', student_verdict='ok', member='father',
                       fields={'name': 'MURUGAN A/L KESAVAN', 'monthly_contribution': 'RM480',
                               'latest_balance': 'RM1,150,410.53', 'year': '2026'})
        pts = {p['key']: p['value'] for p in student_income_proof_check(epf)['points']}
        # The contribution figure (avg over the months; falls back to the single month for
        # older records) is shown — never the lifetime balance as monthly income.
        self.assertEqual(pts['avgContribution'], 'RM480')
        self.assertEqual(pts['totalAccumulated'], 'RM1,150,410.53')
        self.assertEqual(pts['statementDate'], '2026')   # falls back to the year

    def test_epf_no_current_contribution_gives_no_income_estimate(self):
        # The RM1.15M sample: CARUMAN SEMASA "Tiada Transaksi" → empty monthly_contribution
        # → no income estimate (NOT the balance).
        from apps.scholarship.income_engine import earner_monthly_income
        _add_doc(self.app, 'epf', student_verdict='ok', member='father',
                 fields={'name': 'MURUGAN A/L KESAVAN', 'latest_balance': 'RM1,150,410.53'})
        amt, src = earner_monthly_income(self.app, 'father')
        self.assertIsNone(amt)
        self.assertEqual(src, 'unknown')

    def test_utility_per_capita_b40_and_high(self):
        from apps.scholarship.income_engine import utility_per_capita
        _add_doc(self.app, 'water_bill', student_verdict='ok', fields={'amount': 'RM30'})
        _add_doc(self.app, 'electricity_bill', student_verdict='ok', fields={'amount': 'RM50'})
        # (30 + 50) / 4 = 20 < 25 → b40
        self.assertEqual(utility_per_capita(self.app)['signal'], 'b40')
        # Now a high-consumption household (size 2): 80 / 2 = 40 → not < 25, not > 40 = neutral;
        # bump electricity so per-capita clears 40.
        self.profile.household_size = 1
        self.profile.save()
        self.assertEqual(utility_per_capita(self.app)['signal'], 'high')  # 80 / 1 = 80 > 40

    def test_utility_hardship_on_arrears(self):
        from apps.scholarship.income_engine import utility_hardship
        self.assertFalse(utility_hardship(self.app))
        _add_doc(self.app, 'electricity_bill', student_verdict='ok',
                 fields={'amount': 'RM50', 'unpaid_balance': 'RM350'})
        self.assertTrue(utility_hardship(self.app))

    def test_utility_context_surfaces_on_income_tile(self):
        # The soft utility signal rides on the income verdict's evidence (officer context).
        _add_doc(self.app, 'water_bill', student_verdict='ok', fields={'amount': 'RM20'})
        _add_doc(self.app, 'electricity_bill', student_verdict='ok',
                 fields={'amount': 'RM40', 'unpaid_balance': 'RM500'})
        ev = _codes(_facts(self.app)['income']['evidence'])
        self.assertIn('utility_percapita_b40', ev)   # (20+40)/4 = 15 < 25
        self.assertIn('utility_hardship', ev)


class TestRelationshipChecklists(TestCase):
    """Birth certificate + guardianship letter surface a per-row checklist (child/mother/
    father, guardian/ward) verified against the relevant IC — the relationship-proof docs
    that were previously unsurfaced."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='rel', name='B40', year=2026)

    def setUp(self):
        self.profile = StudentProfile.objects.create(
            supabase_user_id=f'rel-{self.id()}', name='ATHIAN SANKAR A/L ELANJELIAN',
            nric='090822-02-0919', household_size=4)
        self.app = ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=self.profile, status='shortlisted',
            income_route='salary', income_working_members=['mother'])

    def test_bc_check_child_mother_father(self):
        from apps.scholarship.income_engine import student_bc_check
        _parent_ic(self.app, 'VANITHA A/P MOHAN', member='mother', nric='760820-02-5230')
        bc = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                      fields={'bc_child_name': 'ATHIAN SANKAR A/L ELANJELIAN',
                              'bc_mother_name': 'VANITHA A/P MOHAN', 'bc_mother_nric': '760820-02-5230',
                              'bc_father_name': 'ELANJELIAN A/L VENUGOPAL'})
        chk = student_bc_check(bc)
        self.assertEqual(chk['child_status'], 'match')      # child = the student
        self.assertEqual(chk['mother_status'], 'match')     # mother name+NRIC = the mother IC
        # father vs the student's patronymic (A/L ELANJELIAN → ELANJELIAN)
        self.assertEqual(chk['father_status'], 'match')

    def test_bc_mother_mismatch(self):
        from apps.scholarship.income_engine import student_bc_check
        _parent_ic(self.app, 'VANITHA A/P MOHAN', member='mother', nric='760820-02-5230')
        bc = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                      fields={'bc_child_name': 'ATHIAN SANKAR A/L ELANJELIAN',
                              'bc_mother_name': 'STRANGER WOMAN', 'bc_mother_nric': '111111-11-1111'})
        self.assertEqual(student_bc_check(bc)['mother_status'], 'mismatch')

    def test_bc_mother_name_match_one_digit_misread_is_check_near(self):
        # POVIENTHIRAN case: the BC mother NAME matches the verified mother IC, but the AI
        # misread ONE digit of her NRIC off the green JPN security paper (76-08 → 76-09).
        # Proven by the name + the verified IC → amber 'check_near' ("differs by one digit"),
        # NOT a red 'mismatch'.
        from apps.scholarship.income_engine import student_bc_check
        _parent_ic(self.app, 'MAGESWARY A/P RAJAGOPAL', member='mother', nric='760824-10-5692')
        bc = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                      fields={'bc_child_name': 'ATHIAN SANKAR A/L ELANJELIAN',
                              'bc_mother_name': 'MAGESWARY A/P RAJAGOPAL',
                              'bc_mother_nric': '760924-10-5692'})  # AI misread: 08 → 09
        self.assertEqual(student_bc_check(bc)['mother_status'], 'check_near')

    def test_bc_mother_name_match_far_nric_is_plain_check(self):
        # Same name, but the NRIC differs by more than one digit → the plainer amber 'check'
        # (still never a red 'mismatch', because the name vouches for the link).
        from apps.scholarship.income_engine import student_bc_check
        _parent_ic(self.app, 'MAGESWARY A/P RAJAGOPAL', member='mother', nric='760824-10-5692')
        bc = _add_doc(self.app, 'birth_certificate', student_verdict='ok',
                      fields={'bc_child_name': 'ATHIAN SANKAR A/L ELANJELIAN',
                              'bc_mother_name': 'MAGESWARY A/P RAJAGOPAL',
                              'bc_mother_nric': '880123-10-1234'})  # wholly different number
        self.assertEqual(student_bc_check(bc)['mother_status'], 'check')

    def test_guardianship_check(self):
        from apps.scholarship.income_engine import student_guardianship_check
        self.app.income_working_members = ['guardian']
        self.app.save()
        _parent_ic(self.app, 'RAJA A/L KUMAR', member='guardian', nric='650505-05-5555')
        g = _add_doc(self.app, 'guardianship_letter', student_verdict='ok',
                     fields={'guardian_name': 'RAJA A/L KUMAR', 'guardian_nric': '650505-05-5555',
                             'ward_name': 'ATHIAN SANKAR A/L ELANJELIAN', 'doc_kind': 'court_order'})
        chk = student_guardianship_check(g)
        self.assertEqual(chk['guardian_status'], 'match')   # guardian name+NRIC = the guardian IC
        self.assertEqual(chk['ward_status'], 'match')       # ward = the student
        self.assertEqual(chk['doc_kind'], 'court_order')


class TestCodeHealthS4IncomeConsistency(TestCase):
    """Code-health S4 regressions: #14 (the salary route uses the SAME two-test B40
    ceiling as the STR fall-through — gross ceiling primary, per-capita a safety net,
    boundary inclusive) and #20 (an unproven declared income forces amber even when an
    unrelated review item exists — 'review' is blue and blue must never hide it)."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(
            code='s4c', name='B40', year=2026, per_capita_ceiling=1584, income_ceiling=5860)

    def _app(self, size, working=('father',), declared=None):
        profile = StudentProfile.objects.create(
            supabase_user_id=f's4-{self.id()}', name='DIVASHINI A/P MURUGAN',
            nric='080115-05-0132', household_size=size)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=profile, status='shortlisted',
            income_route='salary', income_working_members=list(working),
            income_declared=declared or {})

    def _father(self, app, gross):
        _parent_ic(app, 'MURUGAN A/L KESAVAN', member='father')
        _add_doc(app, 'salary_slip', student_verdict='ok', member='father',
                 fields={'name': 'MURUGAN A/L KESAVAN', 'gross_income': gross, 'period': 'May 2026'})

    def test_gross_ceiling_rescues_high_per_capita_small_household(self):
        # #14: household of 3, gross RM5,400 → per-capita RM1,800 (> 1,584) but gross
        # ≤ RM5,860 — B40 HOLDS under spec §7's two-test rule. The old per-capita-only
        # test called this "over the B40 line" while the STR fall-through said B40 holds.
        app = self._app(size=3)
        self._father(app, 'RM5,400')
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('income_per_capita_ok', _codes(f['evidence']))

    def test_exactly_at_ceiling_is_not_over(self):
        # #14 boundary: per-capita exactly RM1,584 (gross 6,336 > 5,860 so the safety net
        # binds) — breach_room == 0 → still B40 (the old strict < called it over).
        app = self._app(size=4)
        self._father(app, 'RM6,336')
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'verified')

    def test_clearly_over_both_ceilings_is_gap_red(self):
        app = self._app(size=2)
        self._father(app, 'RM9,900')       # pc 4,950; gross 9,900 > 5,860 → over
        f = _facts(app)['income']
        self.assertEqual(f['status'], 'gap')                      # V5 #10: red on both routes
        self.assertIn('income_above_b40_line', _codes(f['unresolved']))

    def test_unproven_declared_forces_amber_over_unrelated_review(self):
        # #20: father confirmed with a declared-unproven income; a working BROTHER's IC
        # carries a clashing patronymic → an unrelated 'review' item exists (no gap — a
        # sibling needs no rel doc). The old ordering returned blue 'review' and hid
        # income_declared_needs_evidence behind it.
        app = self._app(size=4, working=('father', 'brother'), declared={'father': 1500})
        _parent_ic(app, 'MURUGAN A/L KESAVAN', member='father')
        _parent_ic(app, 'RAJU A/L SAMY', member='brother')
        f = _facts(app)['income']
        self.assertIn('father_patronymic_mismatch', _codes(f['unresolved']))  # the review item
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('income_declared_needs_evidence', _codes(f['unresolved']))


class TestGenuinenessLadder(_Base):
    """Owner 2026-07-07 - the genuineness score-band + red-chip ladder for identity / academic /
    pathway: band = max(base, genuineness_step + red_chip_count), floored at Fail. genuineness_step
    by score (genuine 0 / suspect 1 / fake 2); each RED content variable is another -1. A genuine doc
    with clean content is untouched."""

    def _auth(self, doc, status):
        doc.vision_fields = dict(doc.vision_fields or {},
                                 authenticity={'status': status, 'reason': 'x'})
        doc.save(update_fields=['vision_fields'])

    # -- Identity --
    def test_identity_suspect_ic_is_probable(self):
        self._auth(_add_ic(self.app, nric=self.profile.nric, name=self.profile.name), 'suspect')
        f = _facts(self.app)['identity']
        self.assertEqual(f['status'], 'review')            # verified -1 (Probable with the id greens)
        self.assertIn('ic_low_confidence', _codes(f['unresolved']))

    def test_identity_not_ic_is_unsure(self):
        self._auth(_add_ic(self.app, nric=self.profile.nric, name=self.profile.name), 'not_ic')
        self.assertEqual(_facts(self.app)['identity']['status'], 'recommend')   # verified -2

    def test_identity_genuine_ic_unchanged(self):
        self._auth(_add_ic(self.app, nric=self.profile.nric, name=self.profile.name), 'genuine')
        self.assertEqual(_facts(self.app)['identity']['status'], 'verified')

    # -- Academic --
    def _slip(self, results, verdict='ok', name='found'):
        return _add_doc(self.app, 'results_slip', student_verdict=verdict, name_match=name,
                        fields={'results': results})

    def test_academic_suspect_slip_is_probable(self):
        self.profile.grades = {'bm': 'A-'}; self.profile.save()
        self._auth(self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'}]), 'suspect')
        f = _facts(self.app)['academic']
        self.assertEqual(f['status'], 'review')            # verified -1
        self.assertIn('document_not_genuine', _codes(f['unresolved']))

    def test_academic_wrong_type_slip_is_unsure(self):
        self.profile.grades = {'bm': 'A-'}; self.profile.save()
        self._auth(self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'}]), 'not_results_slip')
        self.assertEqual(_facts(self.app)['academic']['status'], 'recommend')   # verified -2

    def test_academic_suspect_plus_grade_mismatch_is_unsure(self):
        # suspect (step 1) + a confirmed Results grade mismatch (1 red chip) = -2 -> Unsure.
        self.profile.grades = {'bm': 'A-', 'math': 'B+'}; self.profile.save()
        self._auth(self._slip([{'subject': 'Bahasa Melayu', 'grade': 'A-'},
                               {'subject': 'Matematik', 'grade': 'A'}]), 'suspect')
        self.assertEqual(_facts(self.app)['academic']['status'], 'recommend')

    def test_academic_suspect_name_mismatch_is_unsure(self):
        # Owner 2026-07-07: a wrong-name slip is a RED Name chip (-1), no longer a hard stop; with a
        # suspect genuineness (-1) it lands 🟡 Unsure (not Fail). Softened by design (rare / OCR misread).
        self._auth(_add_doc(self.app, 'results_slip', student_verdict='name_mismatch'), 'suspect')
        self.assertEqual(_facts(self.app)['academic']['status'], 'recommend')

    # -- worked examples + chip stacking --
    def test_identity_name_and_nric_both_mismatch_is_unsure(self):
        # Two red chips (Name + NRIC) on a genuine IC = -2 -> Unsure (a student's own IC misread on
        # both is rare; owner accepted). A LONE mismatch would be -1 (Probable).
        self._auth(_add_ic(self.app, nric='999999-99-9999', name='SOMEONE ELSE'), 'genuine')
        self.assertEqual(_facts(self.app)['identity']['status'], 'recommend')

    # ── Reporting-date BONUS (owner 2026-07-08) ──
    _BONUS_FIELDS = {'reporting_date': '9 Jun 2026', 'reporting_date_label': 'Tarikh Mendaftar',
                     'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                     'candidate_nric': '080115-05-0132',
                     'institution': 'UNIVERSITI PENDIDIKAN SULTAN IDRIS', 'programme': 'Diploma X'}

    def _bonus_offer(self, status, fields=None):
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields=fields or dict(self._BONUS_FIELDS))
        d.vision_fields = dict(d.vision_fields, authenticity={
            'status': status, 'reason': 'x', 'doc_seen': 'ua_offer',
            'present': ['public university (UA) name']})
        d.save(update_fields=['vision_fields'])
        return d

    def test_suspect_offer_with_validated_summons_is_certain(self):
        # A cropped/thin OFFICIAL letter carrying a validated registration summons: the bonus
        # lifts the effective step to 0 AND clears the pathway-not-established chip → 🟢 Certain.
        # The truthful caveat + the amber Official chip + Check-2 all stay (band-only lift).
        self.app.chosen_pathway = 'diploma'        # same family as the UA Diploma offer (no switch)
        self.app.save()
        self._bonus_offer('suspect')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'verified')
        self.assertIn('offer_reporting_official', _codes(f['evidence']))
        self.assertIn('document_not_genuine', _codes(f['unresolved']))

    def test_fake_offer_with_summons_lifts_one_band_only(self):
        # fake + bonus → effective step 1; the pathway chip still fires (still not official)
        # → 1 + 1 = 🟡 Unsure (never green). The confident offer_not_official caveat stays.
        self._bonus_offer('not_offer_letter')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('offer_not_official', _codes(f['unresolved']))

    def test_bonus_never_offsets_identity_chips(self):
        # Guard rail: the bonus is genuineness evidence, NOT identity evidence — a wrong-person
        # letter with a beautiful Tarikh Mendaftar keeps its Name+IC chips: suspect→0 effective,
        # +2 identity chips → 🟡 Unsure (not lifted to Probable/Certain).
        self._bonus_offer('suspect', fields=dict(self._BONUS_FIELDS,
                          candidate_name='SOMEONE ELSE BIN OTHER', candidate_nric='990101-01-1234'))
        self.assertEqual(_facts(self.app)['pathway']['status'], 'recommend')

    def test_private_letter_gets_no_bonus(self):
        # #93 UniMAIWP: a date + label but NO public-issuer signature on the page → no bonus;
        # fake(−2) + pathway chip(−1) = 🔴 Fail unchanged.
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields={'reporting_date': '19 September 2026', 'reporting_date_label': 'Tarikh',
                             'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                             'candidate_nric': '080115-05-0132',
                             'institution': 'UNIVERSITI ANTARABANGSA MAIWP', 'programme': 'Foundation'})
        d.vision_fields = dict(d.vision_fields, authenticity={
            'status': 'not_offer_letter', 'reason': 'x', 'doc_seen': 'ua_offer',
            'present': ['Program / Kod Program']})
        d.save(update_fields=['vision_fields'])
        self.assertEqual(_facts(self.app)['pathway']['status'], 'gap')

    def test_pathway_hash31_pemakluman_pathway_mismatch_is_unsure(self):
        # The #31 worked example: a pemakluman scores 'suspect' (p~0.40, step -1); Name + IC green,
        # but the offer names a different place than declared (1 red Pathway chip, -1) = -2 -> Unsure.
        self.app.chosen_pathway = 'stpm'           # same family as the Tingkatan Enam offer (place clash)
        self.app.pre_u_institution = 'SMK Mentakab'; self.app.save()
        d = _add_doc(self.app, 'offer_letter', student_verdict='ok',
                     fields={'candidate_name': 'THERESA ARUL MARY A/P A.PHILIPS',
                             'candidate_nric': '080115-05-0132',
                             'institution': 'SMK Temerloh', 'programme': 'Tingkatan Enam'})
        self._auth(d, 'suspect')
        f = _facts(self.app)['pathway']
        self.assertEqual(f['status'], 'recommend')
        self.assertIn('pathway_confirm', _codes(f['unresolved']))
