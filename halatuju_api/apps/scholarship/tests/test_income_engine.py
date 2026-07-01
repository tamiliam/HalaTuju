"""Income Check-1 (item 3) — pure engine: patronymic parse, relationship checks,
and the document requirement matrix. No DB, no live calls."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.income_engine import (
    father_name_from_ic, father_relationship, father_via_bc, father_link,
    mother_relationship, guardian_relationship, relationship_doc_for, income_requirements,
    working_members, effective_working_members, salary_member_blocks, member_relationship_status,
    student_income_ic_check, _str_currency,
)
from apps.scholarship.vision import relationship_name_match, name_match


class TestStrCurrency(SimpleTestCase):
    # Structured STR currency states (docs/scholarship/str-proof-spec.md): the format gate runs
    # first (not-a-recognised-STR → wrong_type), then status/date decide the rest.

    # ── wrong_type: NOT a genuine STR proof at all (→ RED, falls through to salary) ──
    def test_unknown_source_is_wrong_type(self):
        # A salary slip / SARA letter / SALINAN in the STR slot is classified source_type='unknown'
        # → wrong_type, EVEN if the AI read an "approved" word off it (#13 payslip, #63 SARA).
        self.assertEqual(_str_currency('approved', '2026', 2026, 'unknown'), 'wrong_type')
        self.assertEqual(_str_currency('', '', 2026, 'unknown'), 'wrong_type')

    # ── rejected: a recognised format showing Ditolak / Tidak Layak (→ RED) ──
    def test_rejected_status(self):
        self.assertEqual(_str_currency('permohonan ditolak', '2026', 2026, 'semakan_status'), 'rejected')

    def test_tidak_layak_is_rejected_not_approved(self):
        # 'layak' is an approval word, but 'tidak layak' (not eligible) is a REJECTION — the
        # rejection check runs first, so this must be 'rejected', never 'current'.
        self.assertEqual(_str_currency('Tidak Layak', '2026', 2026, 'semakan_status'), 'rejected')

    def test_rejected_beats_wrong_type(self):
        # A clear negative status wins even on an 'unknown' source.
        self.assertEqual(_str_currency('Ditolak', '', 2026, 'unknown'), 'rejected')

    # ── unreadable: a recognised format but NO readable approval status (cropped) → AMBER ──
    def test_recognised_no_status_is_unreadable(self):
        self.assertEqual(_str_currency('', '', 2026, 'semakan_status'), 'unreadable')
        self.assertEqual(_str_currency('', '2026', 2026, 'dashboard'), 'unreadable')

    def test_sara_layak_is_not_str_approval(self):
        # SARA 'Layak' is NOT an STR approval word; on a recognised format with only 'Layak' read,
        # the approval status didn't read → unreadable (a recognised STR slot, no STR approval).
        self.assertEqual(_str_currency('Layak', '2026', 2026, 'semakan_status'), 'unreadable')

    # ── unconfirmed: recognised + approved + NO date → BLUE (probably current) ──
    def test_approved_no_date_is_unconfirmed(self):
        # A dateless approved STR (dashboard / collapsed Semakan) can no longer be GREEN — a
        # year-old screenshot also reads "Lulus", so without a date we can't confirm the cycle.
        self.assertEqual(_str_currency('diluluskan', '', 2026, 'semakan_status'), 'unconfirmed')
        self.assertEqual(_str_currency('Lulus', '', 2026, 'dashboard'), 'unconfirmed')
        self.assertEqual(_str_currency('Lulus', '', 2026), 'unconfirmed')  # blank source falls through

    # ── current: recognised + approved + DATED current → GREEN ──
    def test_approved_dated_current_is_current(self):
        self.assertEqual(_str_currency('diluluskan', '2026', 2026, 'letter'), 'current')
        self.assertEqual(_str_currency('Lulus', '2026', 2026, 'semakan_status'), 'current')

    def test_legacy_blank_source_with_date_is_current(self):
        # Docs extracted before source_type existed (null/'') are tolerated — a dated approval
        # falls through to current rather than being forced to wrong_type.
        self.assertEqual(_str_currency('Lulus', '2026', 2026, ''), 'current')

    # ── stale: approved but a readable PRIOR-year date → AMBER ──
    def test_older_year_is_stale(self):
        self.assertEqual(_str_currency('diluluskan', '2024', 2026, 'letter'), 'stale')

    def test_approved_prior_year_still_stale(self):
        self.assertEqual(_str_currency('diluluskan', '2025', 2026, 'letter'), 'stale')

    # ── payment guard: a positive PAID amount corroborates approval (extra, not primary) ──
    def test_paid_amount_rescues_misread_status(self):
        # #23: the model misread "Lulus" as the label "STR"; the RM850 it DID read proves approval
        # (you're not paid STR money unless Lulus). No date → unconfirmed (BLUE), not unreadable.
        self.assertEqual(_str_currency('STR', '', 2026, 'semakan_status', 'RM850'), 'unconfirmed')
        # …and with a current date it's current (GREEN).
        self.assertEqual(_str_currency('STR', '2026', 2026, 'dashboard', 'RM1,200.00'), 'current')

    def test_lulus_alone_is_enough_zero_payment_never_downgrades(self):
        # Approval is proven by "Lulus" on its own — a genuine STR printed early can show RM0 paid.
        self.assertEqual(_str_currency('Lulus', '', 2026, 'dashboard', 'RM0'), 'unconfirmed')
        self.assertEqual(_str_currency('Lulus', '', 2026, 'dashboard', ''), 'unconfirmed')

    def test_no_status_and_no_payment_stays_unreadable(self):
        # Neither a readable approval word NOR a payment → approval can't be confirmed → unreadable.
        self.assertEqual(_str_currency('', '', 2026, 'semakan_status', ''), 'unreadable')
        self.assertEqual(_str_currency('STR', '', 2026, 'semakan_status', 'RM0'), 'unreadable')

    def test_rejected_and_wrong_type_beat_the_payment_guard(self):
        # A Ditolak with a legacy amount is still rejected; a non-STR with an amount is still wrong_type.
        self.assertEqual(_str_currency('Ditolak', '', 2026, 'semakan_status', 'RM850'), 'rejected')
        self.assertEqual(_str_currency('', '', 2026, 'unknown', 'RM850'), 'wrong_type')


class TestFatherNameFromIc(SimpleTestCase):
    def test_a_p_connector(self):
        self.assertEqual(father_name_from_ic('DIVASHINI A/P MURUGAN'), 'MURUGAN')

    def test_a_l_connector(self):
        self.assertEqual(father_name_from_ic('SHARVIN A/L MARAN'), 'MARAN')

    def test_spaced_connector(self):
        self.assertEqual(father_name_from_ic('SHARVANI A / P KANAGEVELLU'), 'KANAGEVELLU')

    def test_bin_and_binti(self):
        self.assertEqual(father_name_from_ic('AHMAD BIN ALI'), 'ALI')
        self.assertEqual(father_name_from_ic('SITI BINTI YUSOF'), 'YUSOF')

    def test_s_o_d_o(self):
        self.assertEqual(father_name_from_ic('RAJ S/O KUMAR'), 'KUMAR')
        self.assertEqual(father_name_from_ic('PRIYA D/O RAMAN'), 'RAMAN')

    def test_multi_token_father(self):
        self.assertEqual(father_name_from_ic('MUTHU A/L SELVAM KUMAR'), 'SELVAM KUMAR')

    def test_no_connector_returns_blank(self):
        # A single name or a Chinese-style name has no patronymic → can't derive.
        self.assertEqual(father_name_from_ic('TAN WEI MING'), '')
        self.assertEqual(father_name_from_ic('MADHAVAN'), '')
        self.assertEqual(father_name_from_ic(''), '')


class TestRelationshipChecks(SimpleTestCase):
    def test_father_match_subset_of_full_name(self):
        # Father's given name from the student IC appears in the earner's fuller IC name.
        self.assertEqual(father_relationship('DIVASHINI A/P MURUGAN', 'MURUGAN A/L KESAVAN'), 'match')

    def test_father_exact_match(self):
        self.assertEqual(father_relationship('AHMAD BIN ALI', 'ALI BIN OSMAN'), 'match')

    def test_father_mismatch_disjoint(self):
        self.assertEqual(father_relationship('DIVASHINI A/P MURUGAN', 'RAJU A/L SAMY'), 'mismatch')

    def test_father_unknown_without_patronymic(self):
        self.assertEqual(father_relationship('TAN WEI MING', 'TAN AH KOW'), 'unknown')

    def test_father_pending_without_earner_name(self):
        self.assertEqual(father_relationship('DIVASHINI A/P MURUGAN', ''), 'pending')

    # ── #55: mononym student → father link via the birth certificate ──────────────
    def test_father_via_bc_match(self):
        # student DIVIYA (no patronymic); BC child=DIVIYA, BC father=SARAVANAN A/L VENU;
        # earner IC = SARAVANAN A/L VENU.
        self.assertEqual(
            father_via_bc('DIVIYA', 'SARAVANAN A/L VENU', 'DIVIYA', 'SARAVANAN A/L VENU'), 'match')

    def test_father_via_bc_mismatch_wrong_child_or_father(self):
        self.assertEqual(
            father_via_bc('SOMEONE A/P ELSE', 'SARAVANAN A/L VENU', 'DIVIYA', 'SARAVANAN A/L VENU'),
            'mismatch')
        self.assertEqual(
            father_via_bc('DIVIYA', 'OTHERMAN A/L X', 'DIVIYA', 'SARAVANAN A/L VENU'), 'mismatch')

    def test_father_via_bc_pending_when_bc_not_read(self):
        self.assertEqual(father_via_bc('', '', 'DIVIYA', 'SARAVANAN A/L VENU'), 'pending')

    def test_father_link_patronymic_wins_ignores_bc(self):
        # A normal applicant (has a patronymic) is unaffected — the BC is never consulted.
        self.assertEqual(
            father_link('SHAARVESHWAAR A/L SARAVANAN', 'SARAWANAN A/L SUPRAMANIAM'), 'match')

    def test_father_link_mononym_uses_bc(self):
        self.assertEqual(
            father_link('DIVIYA', 'SARAVANAN A/L VENU', 'DIVIYA', 'SARAVANAN A/L VENU'), 'match')

    def test_father_link_mononym_without_bc_stays_unknown(self):
        # No BC uploaded yet → still 'officer reviews', never a false match/mismatch.
        self.assertEqual(father_link('DIVIYA', 'SARAVANAN A/L VENU'), 'unknown')

    def test_member_status_father_uses_bc_fallback(self):
        self.assertEqual(
            member_relationship_status('father', 'DIVIYA', 'SARAVANAN A/L VENU',
                                       bc_child_name='DIVIYA', bc_father_name='SARAVANAN A/L VENU'),
            'match')

    def test_member_status_sibling_does_not_use_bc(self):
        # A sibling earner is verified by the shared patronymic only; the BAPA field is the
        # father's, not the sibling's, so a mononym student's sibling stays 'unknown'.
        self.assertEqual(
            member_relationship_status('brother', 'DIVIYA', 'BROTHER A/L VENU',
                                       bc_child_name='DIVIYA', bc_father_name='VENU'),
            'unknown')

    def test_mother_match(self):
        self.assertEqual(
            mother_relationship('DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN',
                                'DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN'), 'match')

    def test_mother_mismatch_wrong_child(self):
        self.assertEqual(
            mother_relationship('SOMEONE ELSE', 'KAMALA A/P RAMAN',
                                'DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN'), 'mismatch')

    def test_mother_mismatch_wrong_mother(self):
        self.assertEqual(
            mother_relationship('DIVASHINI A/P MURUGAN', 'STRANGER WOMAN',
                                'DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN'), 'mismatch')

    def test_mother_pending_when_bc_blank(self):
        self.assertEqual(mother_relationship('', '', 'DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN'),
                         'pending')

    def test_guardian_match_and_mismatch(self):
        self.assertEqual(guardian_relationship('RAJA A/L KUMAR', 'RAJA A/L KUMAR'), 'match')
        self.assertEqual(guardian_relationship('RAJA A/L KUMAR', 'STRANGER PERSON'), 'mismatch')
        self.assertEqual(guardian_relationship('', 'RAJA A/L KUMAR'), 'pending')


class TestNameTransliterationTolerance(SimpleTestCase):
    """#2 (2026-06-11) — relationship / cross-document name matching tolerates Malaysian-
    Tamil/Indian romanisation + OCR variance, so a real family link is not falsely red-flagged
    (the 'Sarawanan A/L Supramaniam' call). It is STRICTLY more lenient than the exact identity
    matcher — it can only turn a mismatch into a match, never the reverse."""

    def test_father_v_w_transliteration_matches(self):
        # Student IC patronymic 'SARAVANAN' (v) vs the father's own IC 'SARAWANAN' (w) is ONE
        # name — it must NOT read as a mismatch.
        self.assertEqual(
            father_relationship('SHAARVESHWAAR A/L SARAVANAN', 'SARAWANAN A/L SUPRAMANIAM'),
            'match')

    def test_matcher_folds_w_v_doubles_and_trailing_h(self):
        self.assertNotEqual(relationship_name_match('SARAVANAN', 'SARAWANAN'), 'mismatch')     # v/w
        self.assertNotEqual(relationship_name_match('LETCHUMANAN', 'LECHUMANAN'), 'mismatch')  # 1-char
        self.assertNotEqual(relationship_name_match('VINOTH', 'VINOT'), 'mismatch')            # silent h

    def test_genuinely_different_people_still_mismatch(self):
        # The tolerance must NOT merge distinct names — a false family link is the real harm.
        for a, b in [('SUPPIAH', 'RAMASAMY'), ('RAMASAMY', 'RAMAKRISHNAN'),
                     ('MURUGAN', 'KESAVAN'), ('SIVA', 'SIRA'), ('VANI', 'RATHA')]:
            self.assertEqual(relationship_name_match(a, b), 'mismatch', f'{a} vs {b}')

    def test_strictly_more_lenient_than_identity_matcher(self):
        # Differential audit: wherever the EXACT identity matcher matches, the tolerant one must
        # too (it only ADDS matches) — so the untouched identity path is never weakened.
        pairs = [('MURUGAN', 'MURUGAN A/L KESAVAN'), ('AHMAD BIN ALI', 'ALI BIN OSMAN'),
                 ('KAMALA A/P RAMAN', 'KAMALA A/P RAMAN'), ('SARAVANAN', 'SUPPIAH'),
                 ('VASAGI A/P SADAYEL', 'VASAGI A/P SADAYEL')]
        for a, b in pairs:
            if name_match(a, b) != 'mismatch':
                self.assertNotEqual(relationship_name_match(a, b), 'mismatch', f'{a} vs {b}')


class TestBirthCertificateWiring(SimpleTestCase):
    """The BC reader must be registered so the mother-relationship check has fields."""

    def test_birth_certificate_is_extractable(self):
        from apps.scholarship import vision
        self.assertIn('birth_certificate', vision._FIELD_SCHEMAS)
        self.assertIn('birth_certificate', vision._DOC_HINTS)
        props = vision._FIELD_SCHEMAS['birth_certificate']['properties']
        for f in ('bc_child_name', 'bc_mother_name', 'bc_father_name'):
            self.assertIn(f, props)

    def test_child_nric_warning_is_dropped_as_expected_noise(self):
        # A Malaysian BC shows no IC for the child, so a 'child NRIC missing' warning is
        # expected noise — it must not reach the officer. Real problems are kept.
        from apps.scholarship.vision import _drop_expected_warnings
        kept = _drop_expected_warnings('birth_certificate', [
            "Child's NRIC not explicitly labelled as 'No. Kad Pengenalan' in the CHILD section.",
            "Mother's name was partially obscured.",
        ])
        self.assertEqual(kept, ["Mother's name was partially obscured."])
        # Non-BC docs are untouched.
        self.assertEqual(_drop_expected_warnings('salary_slip', ['child ic missing']),
                         ['child ic missing'])

    def test_birth_certificate_is_in_the_upload_pipeline(self):
        # The schema existing is NOT enough — the upload handler only OCRs + field-extracts
        # doc types in these sets. A BC missing here was silently never read (child/mother
        # names always blank → relationship could never confirm). Guard against that regressing.
        from apps.scholarship import vision
        from apps.scholarship import views
        self.assertIn('birth_certificate', views.SUPPORTING_NAME_CHECK_TYPES)   # gets OCR'd
        self.assertIn('birth_certificate', vision.GEMINI_EXTRACT_DOC_TYPES)     # gets field-extracted
        self.assertIn('birth_certificate', views.RELATIONSHIP_DOC_TYPES)        # always-extract (cost knob can't skip)


class TestRelationshipDoc(SimpleTestCase):
    def test_relationship_doc_for(self):
        self.assertEqual(relationship_doc_for('father'), '')
        self.assertEqual(relationship_doc_for('mother'), 'birth_certificate')
        self.assertEqual(relationship_doc_for('guardian'), 'guardianship_letter')
        self.assertEqual(relationship_doc_for(''), '')


class TestIncomeRequirements(SimpleTestCase):
    """STR route + the blank fallback. The salary route is per-member (below)."""
    @staticmethod
    def _app(route='', earner='', members=None):
        return SimpleNamespace(income_route=route, income_earner=earner,
                               income_working_members=members or [])

    def test_blank_wizard_only_earner_ic(self):
        r = income_requirements(self._app())
        self.assertEqual(r['compulsory'], ['parent_ic'])
        self.assertEqual(r['optional'], [])
        self.assertEqual(r['members'], [])

    def test_str_route_father(self):
        r = income_requirements(self._app(route='str', earner='father'))
        self.assertEqual(r['route'], 'str')
        self.assertEqual(r['compulsory'], ['parent_ic', 'str'])
        self.assertIn('water_bill', r['optional'])
        self.assertIn('epf', r['optional'])

    def test_str_route_mother_needs_birth_certificate(self):
        r = income_requirements(self._app(route='str', earner='mother'))
        self.assertEqual(r['compulsory'], ['parent_ic', 'birth_certificate', 'str'])

    def test_str_route_guardian_needs_letter(self):
        r = income_requirements(self._app(route='str', earner='guardian'))
        self.assertEqual(r['compulsory'], ['parent_ic', 'guardianship_letter', 'str'])

    def test_str_no_doc_is_both_compulsory_and_optional(self):
        # De-dup guard: a doc compulsory on the STR route must not also appear optional.
        r = income_requirements(self._app(route='str', earner='mother'))
        self.assertFalse(set(r['compulsory']) & set(r['optional']))


class TestSalaryRoute(SimpleTestCase):
    """Multi-earner salary route: working_members + per-member document blocks."""
    @staticmethod
    def _app(members):
        return SimpleNamespace(income_route='salary', income_earner='',
                               income_working_members=members)

    def test_working_members_orders_and_dedupes(self):
        app = self._app(['sister', 'father', 'father', 'guardian'])
        self.assertEqual(working_members(app), ['father', 'guardian', 'sister'])

    def test_working_members_tolerates_garbage(self):
        self.assertEqual(working_members(self._app(None)), [])
        self.assertEqual(working_members(self._app(['nope', 'father'])), ['father'])
        self.assertEqual(working_members(SimpleNamespace()), [])

    def test_father_block_ic_and_slip_compulsory(self):
        # Gate v2: the salary slip is now COMPULSORY (order: IC → slip); EPF stays optional.
        [block] = salary_member_blocks(['father'])
        self.assertEqual(block['member'], 'father')
        self.assertEqual(block['compulsory'], [('parent_ic', 'father'), ('salary_slip', 'father')])
        self.assertEqual(block['optional'], [('epf', 'father')])
        self.assertEqual(block['rel_doc'], '')

    def test_mother_block_adds_untagged_birth_cert(self):
        [block] = salary_member_blocks(['mother'])
        self.assertEqual(block['compulsory'],
                         [('parent_ic', 'mother'), ('salary_slip', 'mother'), ('birth_certificate', '')])
        self.assertEqual(block['rel_doc'], 'birth_certificate')

    def test_guardian_block_adds_untagged_letter(self):
        [block] = salary_member_blocks(['guardian'])
        self.assertEqual(block['compulsory'],
                         [('parent_ic', 'guardian'), ('salary_slip', 'guardian'), ('guardianship_letter', '')])

    def test_sibling_block_is_ic_and_slip(self):
        [block] = salary_member_blocks(['brother'])
        self.assertEqual(block['compulsory'], [('parent_ic', 'brother'), ('salary_slip', 'brother')])
        self.assertEqual(block['optional'], [('epf', 'brother')])
        self.assertEqual(block['rel_doc'], '')

    def test_income_requirements_salary_returns_blocks_in_order(self):
        r = income_requirements(self._app(['sister', 'father']))
        self.assertEqual(r['route'], 'salary')
        self.assertEqual([b['member'] for b in r['members']], ['father', 'sister'])
        self.assertEqual(r['compulsory'], [])
        self.assertEqual(r['optional'], ['water_bill', 'electricity_bill'])

    def test_income_requirements_salary_no_members(self):
        r = income_requirements(self._app([]))
        self.assertEqual(r['members'], [])

    def test_member_relationship_routes_to_patronymic_for_siblings(self):
        # A brother's IC carries the SAME father's name as the student → match.
        self.assertEqual(
            member_relationship_status('brother', 'DIVASHINI A/P MURUGAN',
                                       'RAJESH A/L MURUGAN'), 'match')

    def test_member_relationship_sister_mismatch(self):
        self.assertEqual(
            member_relationship_status('sister', 'DIVASHINI A/P MURUGAN',
                                       'PRIYA A/P STRANGER'), 'mismatch')

    def test_member_relationship_mother_uses_birth_cert(self):
        self.assertEqual(
            member_relationship_status('mother', 'DIVASHINI A/P MURUGAN', 'KAMALA A/P RAMAN',
                                       bc_child_name='DIVASHINI A/P MURUGAN',
                                       bc_mother_name='KAMALA A/P RAMAN'), 'match')

    def test_member_relationship_guardian_uses_letter(self):
        self.assertEqual(
            member_relationship_status('guardian', 'DIVASHINI A/P MURUGAN', 'RAJA A/L KUMAR',
                                       letter_name='RAJA A/L KUMAR'), 'match')


class TestIncomeIcCheck(SimpleTestCase):
    """The per-document income IC check (father/sibling paths need no DB)."""
    @staticmethod
    def _doc(member, ic_name, *, run=True, error='', nric='800101-01-1234', address='KL'):
        # No income proof in this cluster (empty documents) → the proof-match check is a no-op;
        # these tests only exercise the father/sibling relationship (patronymic) path.
        _empty_qs = SimpleNamespace(order_by=lambda *a, **k: SimpleNamespace(first=lambda: None),
                                    first=lambda: None)
        app = SimpleNamespace(income_earner='', income_route='',
                              profile=SimpleNamespace(name='DIVASHINI A/P MURUGAN'),
                              documents=SimpleNamespace(filter=lambda **kw: _empty_qs))
        return SimpleNamespace(doc_type='parent_ic', household_member=member,
                               vision_nric=nric, vision_name=ic_name, vision_address=address,
                               vision_run_at=(object() if run else None), vision_error=error,
                               application=app)

    def test_non_parent_ic_returns_none(self):
        self.assertIsNone(student_income_ic_check(SimpleNamespace(doc_type='ic')))

    def test_father_match_surfaces_values_and_links(self):
        chk = student_income_ic_check(self._doc('father', 'MURUGAN A/L KESAVAN'))
        self.assertEqual(chk['member'], 'father')
        self.assertEqual(chk['name'], 'MURUGAN A/L KESAVAN')
        self.assertEqual(chk['nric'], '800101-01-1234')
        self.assertEqual(chk['name_status'], 'match')
        self.assertTrue(chk['readable'])

    def test_brother_shared_patronymic_matches(self):
        chk = student_income_ic_check(self._doc('brother', 'RAJESH A/L MURUGAN'))
        self.assertEqual(chk['name_status'], 'match')

    def test_sibling_disjoint_name_mismatches(self):
        chk = student_income_ic_check(self._doc('sister', 'PRIYA A/P STRANGER'))
        self.assertEqual(chk['name_status'], 'mismatch')

    def test_unreadable_ic(self):
        chk = student_income_ic_check(self._doc('father', '', error='blurry'))
        self.assertFalse(chk['readable'])
        self.assertEqual(chk['name_status'], 'pending')


# ── Utility-bill facts (current / reasonable / outstanding / name note) ────────
import datetime  # noqa: E402

from apps.scholarship.income_engine import (  # noqa: E402
    _parse_billing_month, _utility_currency, utility_reasonable, utility_check,
    _utility_name_unrelated, utility_holder_unknown, utility_address_mismatch,
    slip_epf_divergence, _reconciled_holder_name, _arrears_amount,
    earner_monthly_income, _epf_monthly_salary, _salary_monthly_amount,
    income_headroom, declared_amount, has_valid_str, has_income_support_doc,
    declared_income_gaps,
)


class _FakeQS(list):
    def order_by(self, *a, **k):
        return self

    def first(self):
        return self[0] if self else None

    def exists(self):
        return bool(self)


class _FakeDocs:
    def __init__(self, docs):
        self._docs = docs

    def filter(self, doc_type=None, **kw):
        return _FakeQS([d for d in self._docs if d.doc_type == doc_type])


def _bill(doc_type, fields=None, address_match='', name=''):
    return SimpleNamespace(doc_type=doc_type, vision_fields={'fields': fields or {}},
                           vision_address_match=address_match, vision_name=name)


def _app(docs, household_size=4, student_name=''):
    app = SimpleNamespace(profile=SimpleNamespace(household_size=household_size, name=student_name))
    app.documents = _FakeDocs(docs)
    for d in docs:
        d.application = app
    return app


class TestEpfMonthlySalary(SimpleTestCase):
    def test_max_formula_agrees_below_5000(self):
        # n=5 months; salary RM1,700 → employer 13% = 1105 total, employee 11% = 935 total;
        # both terms reverse to 1700, max() = 1700.
        f = {'employer_contribution_total': 'RM1105.00', 'employee_contribution_total': 'RM935.00',
             'months_counted': '5'}
        self.assertAlmostEqual(_epf_monthly_salary(f), 1700.0, places=0)

    def test_max_picks_employee_term_above_5000(self):
        # Above RM5,000 the employer share is 12% (we hardcode 13%), so the employer term
        # UNDER-states; the employee-via-11% term stays exact and max() selects it. Salary 6000,
        # 1 month: employer 12% = 720, employee 11% = 660 → max(720/.13=5538, 660/.11=6000)=6000.
        f = {'employer_contribution_total': 'RM720.00', 'employee_contribution_total': 'RM660.00',
             'months_counted': '1'}
        self.assertAlmostEqual(_epf_monthly_salary(f), 6000.0, places=0)

    def test_unemployed_when_employer_number_all_zeros(self):
        self.assertEqual(_epf_monthly_salary({'employer_number': '000000000',
                                              'employee_contribution_total': 'RM935', 'months_counted': '5'}), 0.0)

    def test_legacy_fallback_uses_combined_contribution(self):
        # Records extracted before the split totals → old combined contribution ÷ 0.24.
        self.assertAlmostEqual(_epf_monthly_salary({'avg_monthly_contribution': 'RM434.00'}),
                               round(434.0 / 0.24, 2))
        self.assertAlmostEqual(_epf_monthly_salary({'monthly_contribution': 'RM460.00'}),
                               round(460.0 / 0.24, 2))

    def test_none_when_nothing_usable(self):
        self.assertIsNone(_epf_monthly_salary({'employee_contribution_total': '', 'monthly_contribution': ''}))

    def test_epf_estimate_uses_max_formula(self):
        app = _app([_bill('epf', {'employer_contribution_total': 'RM1105', 'months_counted': '5',
                                  'employee_contribution_total': 'RM935'})])
        amt, src = earner_monthly_income(app, 'father')
        self.assertEqual(src, 'epf_estimate')
        self.assertAlmostEqual(amt, 1700.0, places=0)


class TestSalaryMonthlyAmount(SimpleTestCase):
    def test_consistent_read_uses_gross(self):
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM5300.00',
                                                 'net_income': 'RM4856.75'}), 5300.0)

    def test_gross_only(self):
        self.assertEqual(_salary_monthly_amount({'gross_income': 'RM3000'}), 3000.0)

    def test_net_only_when_no_gross(self):
        self.assertEqual(_salary_monthly_amount({'net_income': 'RM2400'}), 2400.0)

    def test_ytd_annualised_preferred_over_single_month(self):
        # #13: a single month (RM3,800) under-states a job with variable O/T — YTD ÷ 12 is the
        # representative monthly (84,774.59 ÷ 12 ≈ 7,064.55).
        self.assertAlmostEqual(
            _salary_monthly_amount({'gross_income': 'RM3,800', 'gross_income_ytd': 'RM84,774.59'}),
            round(84774.59 / 12, 2), places=2)

    def test_ytd_not_used_when_it_would_deflate(self):
        # A mis-read / partial YTD lower than the single month must NOT deflate the figure.
        self.assertEqual(
            _salary_monthly_amount({'gross_income': 'RM3000', 'gross_income_ytd': 'RM12000'}), 3000.0)

    def test_net_over_gross_is_rejected(self):
        # #66: a hand-written voucher whose ruled ringgit|sen columns were concatenated —
        # the RM326.00 EPF deduction read as gross '32600', RM343.25 deductions as net
        # '34325'. net > gross is impossible on a real payslip → don't trust the amount.
        self.assertIsNone(_salary_monthly_amount({'gross_income': '32600', 'net_income': '34325'}))

    def test_garbled_slip_makes_income_unknown(self):
        # The knock-on: the per-capita driver returns unknown, so income → verify-at-interview
        # instead of asserting a false (100x-inflated) figure over the B40 line.
        app = _app([_bill('salary_slip', {'gross_income': '32600', 'net_income': '34325'})])
        amt, src = earner_monthly_income(app, 'father')
        self.assertIsNone(amt)
        self.assertEqual(src, 'unknown')


class TestIncomeHeadroom(SimpleTestCase):
    """Margin-graded B40 confidence for the salary route (str-proof-spec.md §7.1)."""
    def _hh(self, *, gross=None, ytd=None, size=4, members=('father',)):
        f = {}
        if gross is not None:
            f['gross_income'] = str(gross)
        if ytd is not None:
            f['gross_income_ytd'] = str(ytd)
        app = _app([_bill('salary_slip', f)], household_size=size)
        app.cohort = SimpleNamespace(income_ceiling=5860, per_capita_ceiling=1584)
        return income_headroom(app, list(members))

    def test_far_under_line_is_probable(self):
        # SARA-like: RM687.50/mo pension, household 6 → breach-room ≈ RM8,816 (an undeclared earner
        # would need an implausible wage to breach) → highly probable B40.
        band, ctx = self._hh(gross=687.50, size=6)
        self.assertEqual(band, 'probable')
        self.assertGreater(ctx['breach_room'], 1584)

    def test_near_line_thin_headroom_is_unsure(self):
        # #13-like: annualised ~RM7,064 (YTD 84,774.59 ÷ 12), household 5 → per-capita ~1,413 (under
        # the line) but breach-room ≈ RM856 — an undeclared earner could plausibly breach → unsure.
        band, ctx = self._hh(gross=3800, ytd=84774.59, size=5)
        self.assertEqual(band, 'unsure')
        self.assertEqual(ctx['per_capita'], round(84774.59 / 12 / 5))  # annualised drove it
        self.assertLess(ctx['breach_room'], 1584)

    def test_over_line_is_over(self):
        # per-capita 3,000 > 1,584 AND gross 12,000 > 5,860 → above B40 (never auto-rejected).
        band, _ = self._hh(gross=12000, size=4)
        self.assertEqual(band, 'over')

    def test_income_unreadable_is_unknown(self):
        band, _ = self._hh(gross=None, size=4)
        self.assertEqual(band, 'unknown')

    def test_no_household_size_is_unknown(self):
        band, _ = self._hh(gross=2000, size=None)
        self.assertEqual(band, 'unknown')


class TestDeclaredIncome(SimpleTestCase):
    """Phase 2A — a working member's DECLARED informal income: accepted on a valid STR (the
    means-test) or a supporting doc, else UNPROVEN → income stays Unsure until evidence lands."""

    def _str_doc(self):
        # A valid (approved, dateless → 'unconfirmed') STR — enough for has_valid_str.
        return _bill('str', {'status': 'Lulus', 'recipient_name': '', 'recipient_nric': '',
                             'year': '', 'amount': '', 'source_type': ''})

    def _salary_app(self, *, declared=None, docs=(), earner=''):
        app = _app(list(docs))
        app.income_route = 'salary'
        app.income_earner = earner
        app.income_declared = declared or {}
        app.income_working_members = list((declared or {}).keys())
        app.cohort = SimpleNamespace(year=2026, income_ceiling=5860, per_capita_ceiling=1584)
        return app

    def test_declared_amount_reads_positive_int(self):
        self.assertEqual(declared_amount(self._salary_app(declared={'father': 1500}), 'father'), 1500)

    def test_declared_zero_or_garbage_is_none(self):
        self.assertIsNone(declared_amount(self._salary_app(declared={'father': 0}), 'father'))
        self.assertIsNone(declared_amount(self._salary_app(declared={'father': 'abc'}), 'father'))
        self.assertIsNone(declared_amount(self._salary_app(declared={}), 'father'))

    def test_valid_str_accepts_declared(self):
        app = self._salary_app(declared={'father': 1500}, docs=[self._str_doc()])
        self.assertTrue(has_valid_str(app))
        self.assertEqual(earner_monthly_income(app, 'father'), (1500.0, 'declared_str'))

    def test_support_doc_accepts_declared_when_no_str(self):
        app = self._salary_app(declared={'father': 1500}, docs=[_bill('income_support_doc', {})])
        self.assertFalse(has_valid_str(app))
        self.assertEqual(earner_monthly_income(app, 'father'), (1500.0, 'declared_evidenced'))

    def test_unproven_declared_returns_none(self):
        amt, src = earner_monthly_income(self._salary_app(declared={'father': 1500}), 'father')
        self.assertIsNone(amt)
        self.assertEqual(src, 'declared_unproven')

    def test_salary_slip_beats_declared(self):
        app = self._salary_app(declared={'father': 1500},
                               docs=[_bill('salary_slip', {'gross_income': 'RM3000'})])
        self.assertEqual(earner_monthly_income(app, 'father'), (3000.0, 'salary'))

    def test_rejected_str_is_not_valid_str(self):
        # A rejected STR is not a means-test → a declared amount still needs its own evidence.
        rejected = _bill('str', {'status': 'Ditolak', 'source_type': 'semakan_status', 'year': '2026'})
        app = self._salary_app(declared={'father': 1500}, docs=[rejected])
        self.assertFalse(has_valid_str(app))
        self.assertEqual(earner_monthly_income(app, 'father')[1], 'declared_unproven')

    def test_gaps_empty_when_str_valid(self):
        app = self._salary_app(declared={'father': 1500}, docs=[self._str_doc()])
        self.assertEqual(declared_income_gaps(app), [])

    def test_gaps_list_unproven_member(self):
        self.assertEqual(declared_income_gaps(self._salary_app(declared={'father': 1500})),
                         [{'member': 'father'}])

    def test_gaps_cleared_by_support_doc(self):
        app = self._salary_app(declared={'father': 1500}, docs=[_bill('income_support_doc', {})])
        self.assertEqual(declared_income_gaps(app), [])

    def test_gaps_empty_off_salary_route(self):
        app = self._salary_app(declared={'father': 1500})
        app.income_route = 'str'
        self.assertEqual(declared_income_gaps(app), [])


class TestBillingMonthParse(SimpleTestCase):
    def test_malay_month_name(self):
        self.assertEqual(_parse_billing_month('Mei 2026'), (2026, 5))

    def test_english_month_name(self):
        self.assertEqual(_parse_billing_month('April 2026'), (2026, 4))

    def test_numeric_mm_yyyy(self):
        self.assertEqual(_parse_billing_month('05/2026'), (2026, 5))

    def test_iso_yyyy_mm(self):
        self.assertEqual(_parse_billing_month('2026-05'), (2026, 5))

    def test_unparseable_returns_none(self):
        self.assertIsNone(_parse_billing_month(''))
        self.assertIsNone(_parse_billing_month('this month'))


class TestUtilityCurrency(SimpleTestCase):
    TODAY = datetime.date(2026, 6, 5)

    def test_within_three_months_is_current(self):
        self.assertEqual(_utility_currency('Mei 2026', self.TODAY), 'current')
        self.assertEqual(_utility_currency('Mac 2026', self.TODAY), 'current')

    def test_older_than_three_months_is_stale(self):
        self.assertEqual(_utility_currency('Jan 2026', self.TODAY), 'stale')
        self.assertEqual(_utility_currency('2025-12', self.TODAY), 'stale')

    def test_no_date_is_unknown(self):
        self.assertEqual(_utility_currency('', self.TODAY), 'unknown')

    def test_future_dated_treated_current(self):
        self.assertEqual(_utility_currency('07/2026', self.TODAY), 'current')


class TestUtilityReasonable(SimpleTestCase):
    def test_both_cheap_is_reasonable(self):
        app = _app([_bill('water_bill', {'amount': '40'}), _bill('electricity_bill', {'amount': '40'})], household_size=4)
        r = utility_reasonable(app)
        self.assertEqual(r['status'], 'reasonable')   # 80 / 4 = 20 → well under RM40/head
        self.assertEqual(r['detail'], 'both')

    def test_only_genuinely_high_flags(self):
        # > RM60/head is the only thing worth an officer's eye now.
        app = _app([_bill('water_bill', {'amount': '150'}), _bill('electricity_bill', {'amount': '150'})], household_size=4)
        self.assertEqual(utility_reasonable(app)['status'], 'high')   # 300 / 4 = 75 > 60

    def test_former_borderline_is_now_reasonable(self):
        # The old amber 'borderline' band is gone — a normal household reads 'reasonable',
        # so we never raise a spurious "explain your utility spend" query (e.g. #61's RM31/head).
        app = _app([_bill('water_bill', {'amount': '67'}), _bill('electricity_bill', {'amount': '89'})], household_size=5)
        self.assertEqual(utility_reasonable(app)['status'], 'reasonable')   # 156 / 5 = 31.25 ≤ 60

    def test_mid_fifties_is_reasonable_not_high(self):
        app = _app([_bill('water_bill', {'amount': '100'}), _bill('electricity_bill', {'amount': '120'})], household_size=4)
        self.assertEqual(utility_reasonable(app)['status'], 'reasonable')   # 220 / 4 = 55 ≤ 60

    def test_one_bill_only_is_partial(self):
        app = _app([_bill('water_bill', {'amount': '40'})], household_size=4)
        r = utility_reasonable(app)
        self.assertEqual(r['status'], 'partial')
        self.assertEqual(r['detail'], 'water_only')

    def test_no_household_size_is_unknown(self):
        app = _app([_bill('water_bill', {'amount': '40'}), _bill('electricity_bill', {'amount': '40'})], household_size=None)
        self.assertEqual(utility_reasonable(app)['status'], 'unknown')


# ── Cross-bill holder-name reconciliation (a wrinkled/cut bill dropped a letter) ──────

class TestHolderNameReconciliation(SimpleTestCase):
    def test_cut_letter_recovered_from_clean_bill(self):
        # The water bill was creased so the 'T' was cut → 'HANA BALAN'; the electricity
        # bill reads it cleanly → 'THANA BALAN'. Both rows should report the clean name.
        docs = [_bill('water_bill', {'amount': '89', 'name': 'HANA BALAN A/L NARAYANAN'}),
                _bill('electricity_bill', {'amount': '67', 'name': 'THANA BALAN A/L NARAYANAN'})]
        app = _app(docs, household_size=5, student_name='SHAARVESHWAAR A/L SARAWANAN')
        self.assertEqual(utility_check(docs[0])['name'], 'THANA BALAN A/L NARAYANAN')   # water row
        self.assertEqual(utility_check(docs[1])['name'], 'THANA BALAN A/L NARAYANAN')   # elec row

    def test_holder_unknown_flag_quotes_the_clean_name(self):
        docs = [_bill('water_bill', {'amount': '89', 'name': 'HANA BALAN A/L NARAYANAN'}),
                _bill('electricity_bill', {'amount': '67', 'name': 'THANA BALAN A/L NARAYANAN'})]
        app = _app(docs, household_size=5, student_name='SHAARVESHWAAR A/L SARAWANAN')
        self.assertEqual(utility_holder_unknown(app), 'THANA BALAN A/L NARAYANAN')

    def test_two_genuinely_different_holders_never_merge(self):
        # Father's bill vs a stranger's bill — different people, so neither is rewritten.
        docs = [_bill('water_bill', {'amount': '50', 'name': 'SARAWANAN A/L SUPRAMANIAM'}),
                _bill('electricity_bill', {'amount': '50', 'name': 'THANA BALAN A/L NARAYANAN'})]
        app = _app(docs, household_size=5, student_name='SHAARVESHWAAR A/L SARAWANAN')
        self.assertEqual(utility_check(docs[0])['name'], 'SARAWANAN A/L SUPRAMANIAM')
        self.assertEqual(utility_check(docs[1])['name'], 'THANA BALAN A/L NARAYANAN')

    def test_single_bill_unchanged(self):
        app = _app([_bill('water_bill', {'amount': '40', 'name': 'HANA BALAN A/L NARAYANAN'})], household_size=4)
        self.assertEqual(_reconciled_holder_name(app, 'HANA BALAN A/L NARAYANAN'), 'HANA BALAN A/L NARAYANAN')


# ── Arrears: a CREDIT balance must read as zero owed, not positive arrears ────────────

class TestArrearsCredit(SimpleTestCase):
    TODAY = datetime.date(2026, 6, 5)

    def test_credit_balance_parses_as_zero(self):
        self.assertEqual(_arrears_amount('-1.29'), 0.0)
        self.assertEqual(_arrears_amount('RM -1.29'), 0.0)
        self.assertEqual(_arrears_amount('200.00 CR'), 0.0)

    def test_normal_arrears_still_parse(self):
        self.assertEqual(_arrears_amount('RM 145.92'), 145.92)
        self.assertEqual(_arrears_amount('1,234.50'), 1234.50)
        self.assertIsNone(_arrears_amount(''))

    def test_credit_does_not_show_outstanding(self):
        # A household IN CREDIT (-1.29) must not read as 'arrears' on the bill row.
        app = _app([_bill('water_bill', {'amount': '31', 'unpaid_balance': '-1.29'})], household_size=4)
        chk = utility_check(app.documents.filter(doc_type='water_bill').first(), today=self.TODAY)
        self.assertEqual(chk['outstanding_status'], '')

    def test_credit_does_not_count_as_hardship(self):
        from apps.scholarship.income_engine import utility_hardship
        # A large credit (e.g. a RM200 deposit refund) must NOT trip the hardship signal.
        app = _app([_bill('water_bill', {'amount': '31', 'unpaid_balance': '-200.00'}),
                    _bill('electricity_bill', {'amount': '50', 'unpaid_balance': '-200.00'})], household_size=4)
        self.assertFalse(utility_hardship(app))


class TestUtilityCheck(SimpleTestCase):
    TODAY = datetime.date(2026, 6, 5)

    def test_assembles_all_facts(self):
        docs = [_bill('water_bill', {'amount': '20', 'billing_period': 'Mei 2026'}, address_match='found'),
                _bill('electricity_bill', {'amount': '20'})]
        app = _app(docs, household_size=4)
        chk = utility_check(docs[0], today=self.TODAY)
        self.assertEqual(chk['address_status'], 'found')
        self.assertEqual(chk['current_status'], 'current')
        self.assertEqual(chk['reasonable_status'], 'reasonable')   # 40 / 4 = 10

    def test_outstanding_only_when_arrears_exceed_charge(self):
        app = _app([_bill('water_bill', {'amount': '30', 'unpaid_balance': '80'})], household_size=4)
        self.assertEqual(utility_check(app.documents.filter(doc_type='water_bill').first(), today=self.TODAY)['outstanding_status'], 'arrears')
        app2 = _app([_bill('water_bill', {'amount': '30', 'unpaid_balance': '10'})], household_size=4)
        self.assertEqual(utility_check(app2.documents.filter(doc_type='water_bill').first(), today=self.TODAY)['outstanding_status'], '')

    def test_name_note_unrelated_when_stranger(self):
        docs = [_bill('water_bill', {'amount': '20', 'name': 'RAJESWARI A/P RAMALINGAM'}),
                _bill('parent_ic', name='MURUGAN A/L KESAVAN')]
        app = _app(docs, household_size=4, student_name='DIVASHINI A/P MURUGAN')
        self.assertEqual(utility_check(docs[0], today=self.TODAY)['name_note'], 'unrelated')

    def test_name_note_blank_when_matches_parent_ic(self):
        docs = [_bill('water_bill', {'amount': '20', 'name': 'MURUGAN A/L KESAVAN'}),
                _bill('parent_ic', name='MURUGAN A/L KESAVAN')]
        app = _app(docs, household_size=4, student_name='DIVASHINI A/P MURUGAN')
        self.assertEqual(utility_check(docs[0], today=self.TODAY)['name_note'], '')

    def test_name_note_blank_when_blank_name(self):
        app = _app([_bill('water_bill', {'amount': '20'}, name='')], household_size=4)
        self.assertFalse(_utility_name_unrelated(app, ''))

    def test_non_utility_doc_returns_none(self):
        app = _app([_bill('ic')], household_size=4)
        self.assertIsNone(utility_check(app.documents.filter(doc_type='ic').first(), today=self.TODAY))


# ── #8 utility holder / address → query helpers ──────────────────────────────

class TestUtilityHolderUnknown(SimpleTestCase):
    def test_returns_name_when_stranger(self):
        docs = [_bill('water_bill', {'amount': '20', 'name': 'RAJESWARI A/P RAMALINGAM'}),
                _bill('parent_ic', name='MURUGAN A/L KESAVAN')]
        app = _app(docs, student_name='DIVASHINI A/P MURUGAN')
        self.assertEqual(utility_holder_unknown(app), 'RAJESWARI A/P RAMALINGAM')

    def test_none_when_holder_is_a_parent(self):
        docs = [_bill('electricity_bill', {'amount': '20', 'name': 'MURUGAN A/L KESAVAN'}),
                _bill('parent_ic', name='MURUGAN A/L KESAVAN')]
        app = _app(docs, student_name='DIVASHINI A/P MURUGAN')
        self.assertIsNone(utility_holder_unknown(app))

    def test_none_when_no_utility_bill(self):
        app = _app([_bill('ic')], student_name='DIVASHINI A/P MURUGAN')
        self.assertIsNone(utility_holder_unknown(app))


class TestUtilityAddressMismatch(SimpleTestCase):
    def test_true_only_on_hard_mismatch(self):
        app = _app([_bill('water_bill', {'amount': '20'}, address_match='mismatch')])
        self.assertTrue(utility_address_mismatch(app))

    def test_partial_stays_silent(self):
        # A missing postcode / shortened street reads as 'partial' — NOT a query.
        app = _app([_bill('water_bill', {'amount': '20'}, address_match='partial')])
        self.assertFalse(utility_address_mismatch(app))

    def test_found_is_not_a_mismatch(self):
        app = _app([_bill('electricity_bill', {'amount': '20'}, address_match='found')])
        self.assertFalse(utility_address_mismatch(app))


# ── #9 payslip vs EPF divergence ─────────────────────────────────────────────

class TestSlipEpfDivergence(SimpleTestCase):
    def test_agree_within_tolerance_returns_none(self):
        # gross 3000 vs epf 720/0.24 = 3000 → ratio 1.0 → no flag.
        app = _app([_bill('salary_slip', {'gross_income': 'RM 3000'}),
                    _bill('epf', {'monthly_contribution': 'RM 720'})])
        self.assertIsNone(slip_epf_divergence(app, 'father'))

    def test_diverge_flags_with_both_figures(self):
        # gross 3000 vs epf 200/0.24 ≈ 833 → ratio ≈ 3.6 → flag.
        app = _app([_bill('salary_slip', {'gross_income': 'RM 3000'}),
                    _bill('epf', {'monthly_contribution': 'RM 200'})])
        out = slip_epf_divergence(app, 'father')
        self.assertIsNotNone(out)
        self.assertEqual(out['slip'], 3000.0)
        self.assertEqual(out['epf_implied'], round(200 / 0.24, 2))

    def test_only_payslip_returns_none(self):
        app = _app([_bill('salary_slip', {'gross_income': 'RM 3000'})])
        self.assertIsNone(slip_epf_divergence(app, 'father'))

    def test_only_epf_returns_none(self):
        app = _app([_bill('epf', {'monthly_contribution': 'RM 200'})])
        self.assertIsNone(slip_epf_divergence(app, 'father'))

    def test_unreadable_figures_return_none(self):
        app = _app([_bill('salary_slip', {'gross_income': ''}),
                    _bill('epf', {'monthly_contribution': ''})])
        self.assertIsNone(slip_epf_divergence(app, 'father'))

    def test_modest_overtime_within_band_stays_quiet(self):
        # gross 3300 vs epf 720/0.24 = 3000 → ratio 1.1 → within band, no flag.
        app = _app([_bill('salary_slip', {'gross_income': 'RM 3300'}),
                    _bill('epf', {'monthly_contribution': 'RM 720'})])
        self.assertIsNone(slip_epf_divergence(app, 'father'))


class TestEffectiveWorkingMembers(SimpleTestCase):
    """The salary-route fallback for the prefill-not-saved gap (#90): the income wizard
    pre-ticks the roster earners + tags uploads, but only persists income_working_members on
    an explicit toggle — so an accepted prefill leaves tagged docs + an EMPTY list. The
    requirement engine must reconstruct the earners, never read income as undeclared."""

    class _Docs:
        """Minimal documents-manager stub: .filter(...).exclude(...).values_list('x', flat=True)."""
        def __init__(self, tagged):
            self._tagged = list(tagged)
        def filter(self, **kw):
            return self
        def exclude(self, **kw):
            return self
        def values_list(self, *a, **kw):
            return list(self._tagged)

    @staticmethod
    def _app(members=None, route='salary', tagged=None, mother='', father='', others=None):
        return SimpleNamespace(
            income_route=route, income_earner='', income_working_members=members or [],
            documents=TestEffectiveWorkingMembers._Docs(tagged or []),
            mother_occupation=mother, father_occupation=father,
            other_family_members=others or [])

    def test_explicit_selection_always_wins(self):
        # A real saved selection is never overridden by the fallback.
        app = self._app(members=['father'], tagged=['mother'], mother='clerk')
        self.assertEqual(effective_working_members(app), ['father'])

    def test_empty_falls_back_to_tagged_income_docs(self):
        # #90 exactly: salary route, empty list, but mother's income docs are tagged → mother.
        app = self._app(members=[], tagged=['mother', 'mother'], mother='clerk')
        self.assertEqual(effective_working_members(app), ['mother'])

    def test_empty_with_no_tags_falls_back_to_roster(self):
        # No tagged docs yet → reconstruct from the family roster's earners (mother clerk works,
        # father non-earner). Order follows _MEMBER_ORDER.
        app = self._app(members=[], tagged=[], mother='clerk', father='no_contact')
        self.assertEqual(effective_working_members(app), ['mother'])

    def test_tagged_docs_take_priority_over_roster(self):
        # The student actually uploaded the father's docs → trust that over the roster.
        app = self._app(members=[], tagged=['father'], mother='clerk', father='no_contact')
        self.assertEqual(effective_working_members(app), ['father'])

    def test_str_route_never_falls_back(self):
        app = self._app(members=[], route='str', tagged=['mother'], mother='clerk')
        self.assertEqual(effective_working_members(app), [])

    def test_blank_route_never_falls_back(self):
        app = self._app(members=[], route='', tagged=['mother'], mother='clerk')
        self.assertEqual(effective_working_members(app), [])

    def test_income_requirements_uses_the_fallback(self):
        # The headline fix: with an empty list but mother's docs tagged, income_requirements
        # now yields mother's compulsory block (IC + salary slip + birth cert) — not nothing.
        app = self._app(members=[], tagged=['mother'], mother='clerk')
        req = income_requirements(app)
        self.assertEqual([b['member'] for b in req['members']], ['mother'])
        compulsory = {dt for dt, _ in req['members'][0]['compulsory']}
        self.assertEqual(compulsory, {'parent_ic', 'salary_slip', 'birth_certificate'})


# ── IC-NUMBER chain (Item A) ───────────────────────────────────────────────────
# The Birth Certificate carries the parents' IC NUMBERS; the income proof (STR / salary / EPF)
# carries the recipient's NRIC. When the two NUMBERS match, the earner is confirmed as that parent
# even when the IC physically uploaded in their slot is the wrong card or absent (#9: father's IC
# in the mother slot, but BC-mother / STR / EPF all carry the mother's number).
from apps.scholarship.income_engine import (  # noqa: E402
    chain_verified_earner, student_str_check, student_bc_check, student_income_proof_check,
)
from apps.scholarship.resolution import doc_match_verdict  # noqa: E402

_STUDENT = 'THERESA D/O RAJAN'
_MOTHER = 'MARY THOMAS'
_FATHER = 'RAJAN KUMAR'
_MOTHER_NRIC = '750721-04-5130'
_FATHER_NRIC = '720314-04-1122'


class _ChainQS(list):
    def order_by(self, *a, **k):
        return self

    def first(self):
        return self[0] if self else None


class _ChainDocs:
    def __init__(self, docs):
        self._docs = docs

    def filter(self, doc_type=None, household_member=None, household_member__in=None, **kw):
        out = []
        for d in self._docs:
            if doc_type is not None and d.doc_type != doc_type:
                continue
            hm = getattr(d, 'household_member', '')
            if household_member is not None and hm != household_member:
                continue
            if household_member__in is not None and hm not in household_member__in:
                continue
            out.append(d)
        return _ChainQS(out)


def _bc_doc(*, child=_STUDENT, mother_nric=_MOTHER_NRIC, status='genuine'):
    return SimpleNamespace(
        doc_type='birth_certificate', household_member='', vision_run_at=object(), vision_error='',
        vision_fields={'fields': {'bc_child_name': child, 'bc_mother_name': _MOTHER,
                                  'bc_mother_nric': mother_nric, 'bc_father_name': _FATHER,
                                  'bc_father_nric': _FATHER_NRIC},
                       'authenticity': {'status': status}})


def _wrong_card_ic():
    """The father's IC physically uploaded in the MOTHER slot (#9)."""
    return SimpleNamespace(doc_type='parent_ic', household_member='mother', vision_name=_FATHER,
                           vision_nric=_FATHER_NRIC, vision_address='KL',
                           vision_run_at=object(), vision_error='')


def _str_doc(*, nric=_MOTHER_NRIC, name=_MOTHER):
    return SimpleNamespace(doc_type='str', household_member='',
                           vision_fields={'fields': {'recipient_name': name, 'recipient_nric': nric,
                                                      'status': 'lulus', 'year': '2026'}})


def _epf_doc(*, nric=_MOTHER_NRIC, name=_MOTHER):
    return SimpleNamespace(doc_type='epf', household_member='mother',
                           vision_fields={'fields': {'name': name, 'nric': nric,
                                                      'monthly_contribution': '300.00'}})


def _chain_app(docs, *, route='str', earner='mother'):
    app = SimpleNamespace(income_route=route, income_earner=earner,
                          income_working_members=['mother'] if route == 'salary' else [],
                          profile=SimpleNamespace(name=_STUDENT, nric='050101-04-9999'),
                          cohort=SimpleNamespace(year=2026))
    app.documents = _ChainDocs(docs)
    for d in docs:
        d.application = app
    return app


class TestIcNumberChain(SimpleTestCase):
    # ── The chain fires (STR route) ──────────────────────────────────────────
    def test_chain_verified_when_bc_mother_nric_matches_str(self):
        app = _chain_app([_wrong_card_ic(), _bc_doc(), _str_doc()])
        self.assertTrue(chain_verified_earner(app, 'mother'))

    def test_wrong_card_ic_no_longer_blocks(self):
        ic = _wrong_card_ic()
        _chain_app([ic, _bc_doc(), _str_doc()])
        chk = student_income_ic_check(ic)
        self.assertTrue(chk['chain_verified'])
        self.assertTrue(chk['wrong_card'])             # the card IS a different person's
        self.assertEqual(chk['name_status'], 'match')  # but the earner relationship is confirmed
        self.assertEqual(doc_match_verdict(ic), 'ok')  # so it does NOT red-block

    def test_str_recipient_reanchored_to_bc_mother(self):
        str_doc = _str_doc()
        _chain_app([_wrong_card_ic(), _bc_doc(), str_doc])
        sc = student_str_check(str_doc)
        self.assertEqual(sc['name_status'], 'match')
        self.assertEqual(sc['nric_status'], 'match')

    def test_bc_mother_row_reanchored_to_proof(self):
        bc = _bc_doc()
        _chain_app([_wrong_card_ic(), bc, _str_doc()])
        bcc = student_bc_check(bc)
        self.assertEqual(bcc['mother_status'], 'match')
        self.assertEqual(doc_match_verdict(bc), 'ok')

    # ── The chain fires (salary route, EPF) ───────────────────────────────────
    def test_epf_reanchored_to_bc_mother_on_salary_route(self):
        epf = _epf_doc()
        _chain_app([_wrong_card_ic(), _bc_doc(), epf], route='salary')
        pc = student_income_proof_check(epf)
        self.assertEqual(pc['name_status'], 'match')
        self.assertEqual(pc['nric_status'], 'match')
        self.assertEqual(doc_match_verdict(epf), 'ok')

    # ── One-digit OCR drift still chains WHEN the name corroborates ────────────
    def test_one_digit_drift_with_name_corroboration_chains(self):
        app = _chain_app([_wrong_card_ic(), _bc_doc(mother_nric='750721-04-5131'), _str_doc()])
        self.assertTrue(chain_verified_earner(app, 'mother'))

    # ── The chain does NOT fire — reds preserved ──────────────────────────────
    def test_suspect_bc_cannot_anchor(self):
        ic = _wrong_card_ic()
        _chain_app([ic, _bc_doc(status='suspect'), _str_doc()])
        chk = student_income_ic_check(ic)
        self.assertFalse(chk['chain_verified'])
        self.assertEqual(chk['name_status'], 'mismatch')
        self.assertEqual(doc_match_verdict(ic), 'mismatch')   # hard block preserved

    def test_bc_for_a_different_child_cannot_anchor(self):
        # #5-style true catch: the BC is genuine but its child is NOT this student.
        app = _chain_app([_wrong_card_ic(), _bc_doc(child='SOMEONE ELSE'), _str_doc()])
        self.assertFalse(chain_verified_earner(app, 'mother'))

    def test_different_number_no_corroboration_stays_blocked(self):
        # Wrong person entirely: BC mother number != STR number, and the card disagrees too.
        ic = _wrong_card_ic()
        _chain_app([ic, _bc_doc(mother_nric='990101-14-7777'), _str_doc()])
        chk = student_income_ic_check(ic)
        self.assertFalse(chk['chain_verified'])
        self.assertEqual(doc_match_verdict(ic), 'mismatch')

    def test_genuine_mother_card_is_unaffected(self):
        # A CORRECT mother IC (right card) still verifies the ordinary way — chain is a bonus path.
        ic = SimpleNamespace(doc_type='parent_ic', household_member='mother', vision_name=_MOTHER,
                             vision_nric=_MOTHER_NRIC, vision_address='KL',
                             vision_run_at=object(), vision_error='')
        _chain_app([ic, _bc_doc(), _str_doc()])
        chk = student_income_ic_check(ic)
        self.assertEqual(chk['name_status'], 'match')
        self.assertFalse(chk['wrong_card'])            # the right card -> no wrong-card note
        self.assertEqual(doc_match_verdict(ic), 'ok')
