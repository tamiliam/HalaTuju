"""Income Check-1 (item 3) — pure engine: patronymic parse, relationship checks,
and the document requirement matrix. No DB, no live calls."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.income_engine import (
    father_name_from_ic, father_relationship, mother_relationship,
    guardian_relationship, relationship_doc_for, income_requirements,
    working_members, salary_member_blocks, member_relationship_status,
    student_income_ic_check, _str_currency,
)


class TestStrCurrency(SimpleTestCase):
    def test_unread_str_is_unknown_not_current(self):
        # No status AND no readable year → 'unknown' (an unread STR must NOT badge Current/Verified).
        self.assertEqual(_str_currency('', '', 2026), 'unknown')

    def test_approved_current_year_is_current(self):
        self.assertEqual(_str_currency('diluluskan', '2026', 2026), 'current')

    def test_older_year_is_stale(self):
        self.assertEqual(_str_currency('diluluskan', '2024', 2026), 'stale')

    def test_rejected_status(self):
        self.assertEqual(_str_currency('permohonan ditolak', '2026', 2026), 'rejected')

    def test_status_present_but_no_year_is_current(self):
        # A real screenshot with an approved status but no parseable year stays 'current'.
        self.assertEqual(_str_currency('diluluskan', '', 2026), 'current')


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


class TestBirthCertificateWiring(SimpleTestCase):
    """The BC reader must be registered so the mother-relationship check has fields."""

    def test_birth_certificate_is_extractable(self):
        from apps.scholarship import vision
        self.assertIn('birth_certificate', vision._FIELD_SCHEMAS)
        self.assertIn('birth_certificate', vision._DOC_HINTS)
        props = vision._FIELD_SCHEMAS['birth_certificate']['properties']
        for f in ('bc_child_name', 'bc_mother_name', 'bc_father_name'):
            self.assertIn(f, props)


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
        app = SimpleNamespace(income_earner='',
                              profile=SimpleNamespace(name='DIVASHINI A/P MURUGAN'))
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
    _utility_name_unrelated,
)


class _FakeQS(list):
    def order_by(self, *a, **k):
        return self

    def first(self):
        return self[0] if self else None


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
        self.assertEqual(r['status'], 'reasonable')   # 80 / 4 = 20 < 25
        self.assertEqual(r['detail'], 'both')

    def test_both_high_is_high(self):
        app = _app([_bill('water_bill', {'amount': '100'}), _bill('electricity_bill', {'amount': '120'})], household_size=4)
        self.assertEqual(utility_reasonable(app)['status'], 'high')   # 220 / 4 = 55 > 40

    def test_both_middle_is_borderline(self):
        app = _app([_bill('water_bill', {'amount': '60'}), _bill('electricity_bill', {'amount': '70'})], household_size=4)
        self.assertEqual(utility_reasonable(app)['status'], 'borderline')   # 130 / 4 = 32.5

    def test_one_bill_only_is_partial(self):
        app = _app([_bill('water_bill', {'amount': '40'})], household_size=4)
        r = utility_reasonable(app)
        self.assertEqual(r['status'], 'partial')
        self.assertEqual(r['detail'], 'water_only')

    def test_no_household_size_is_unknown(self):
        app = _app([_bill('water_bill', {'amount': '40'}), _bill('electricity_bill', {'amount': '40'})], household_size=None)
        self.assertEqual(utility_reasonable(app)['status'], 'unknown')


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
