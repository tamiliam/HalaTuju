"""Income Check-1 (item 3) — pure engine: patronymic parse, relationship checks,
and the document requirement matrix. No DB, no live calls."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.scholarship.income_engine import (
    father_name_from_ic, father_relationship, mother_relationship,
    guardian_relationship, relationship_doc_for, income_requirements,
    working_members, salary_member_blocks, member_relationship_status,
)


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

    def test_father_block_ic_plus_optional_income(self):
        [block] = salary_member_blocks(['father'])
        self.assertEqual(block['member'], 'father')
        self.assertEqual(block['compulsory'], [('parent_ic', 'father')])      # no extra doc
        self.assertEqual(block['optional'], [('salary_slip', 'father'), ('epf', 'father')])
        self.assertEqual(block['rel_doc'], '')

    def test_mother_block_adds_untagged_birth_cert(self):
        [block] = salary_member_blocks(['mother'])
        self.assertEqual(block['compulsory'], [('parent_ic', 'mother'), ('birth_certificate', '')])
        self.assertEqual(block['rel_doc'], 'birth_certificate')

    def test_guardian_block_adds_untagged_letter(self):
        [block] = salary_member_blocks(['guardian'])
        self.assertEqual(block['compulsory'], [('parent_ic', 'guardian'), ('guardianship_letter', '')])

    def test_sibling_block_is_ic_only(self):
        [block] = salary_member_blocks(['brother'])
        self.assertEqual(block['compulsory'], [('parent_ic', 'brother')])
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
