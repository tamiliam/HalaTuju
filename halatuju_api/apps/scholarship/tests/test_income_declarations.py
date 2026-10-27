"""Income declarations (#374, owner ruling 2026-10-27) — synthetic text only, no real applicant data.

"An informal income document counts ONLY if it carries a HEADER (issuing body) AND an APPROVER (signed or
stamped by someone). A self-declaration form with no approver does NOT count. Even when it counts, a
declared amount is never Certain."
"""
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.scholarship.models import ApplicantDocument
from apps.scholarship.tests.factories import make_application, make_student

# The #374 SHAPE — a self-filled parents' income form (synthetic: no real name, IC or amount).
FORM = ('BORANG PENGESAHAN PENDAPATAN IBU BAPA / PENJAGA\n'
        'Nama Bapa: PEMOHON CONTOH  No. K.P Baru: 000000-00-0000  No. K.P Lama: A000000\n'
        'Pekerjaan: NELAYAN   Sektor: Kerajaan / Swasta / Tentera/ Polis / Bekerja Sendiri\n'
        'Kumpulan Perkhidmatan: -\nPendapatan Bersih Sebulan: RM800\n'
        'Jumlah Pendapatan Isi Rumah: RM1,200\nTandatangan: ______')
UNTITLED = FORM.replace('BORANG PENGESAHAN PENDAPATAN IBU BAPA / PENJAGA', 'MAKLUMAT IBU BAPA')
GOVT_SLIP = ('JABATAN AKAUNTAN NEGARA MALAYSIA\nPENYATA GAJI BAGI BULAN MAC 2026\nGRED: N19\n'
             'GAJI POKOK 2,100.00  ELAUN 300.00  POTONGAN 150.00  GAJI BERSIH 2,250.00')
STUDENT, STUDENT_NRIC = 'DIVASHINI A/P MURUGAN', '080115-05-0132'
FATHER, FATHER_NRIC = 'MURUGAN A/L SUBRAMANIAM', '700707-05-5671'
APPROVED = {'issuer_header': 'JAWATANKUASA KEMAJUAN DAN KESELAMATAN KAMPUNG CONTOH',
            'approver_name': 'ENCIK CONTOH', 'approver_title': 'Ketua Kampung', 'has_stamp_or_signature': 'yes'}


class TheSalaryScorer(SimpleTestCase):

    def test_the_374_shape_matched_the_civil_service_marker_and_three_wage_labels(self):
        """What the old model saw: 'KUMPULAN PERKHIDMATAN' (the form's sector field) as a JANM slip, plus
        PENDAPATAN / PENDAPATAN BERSIH / JUMLAH PENDAPATAN — 0.70 + 3 × 0.03 = 0.79, the stored score."""
        from apps.scholarship.genuineness.salary_doc import score_family
        m = score_family(UNTITLED)
        self.assertEqual((m['wage'], m['statutory'], m['govt']), (3, 0, False))     # govt no longer

    def test_a_declaration_form_is_never_a_payslip_family(self):
        from apps.scholarship.genuineness.salary_doc import salary_genuineness
        for text in (FORM, UNTITLED + '\nSaya mengaku bahawa maklumat di atas adalah benar.'):
            with self.subTest(text[:20]):
                g = salary_genuineness(text)
                self.assertEqual((g['status'], g['family']), ('suspect', 'declaration'))

    def test_an_untitled_form_with_no_oath_is_informal_not_govt(self):
        from apps.scholarship.genuineness.salary_doc import salary_genuineness
        self.assertEqual(salary_genuineness(UNTITLED)['family'], 'informal')

    def test_a_real_government_payslip_is_still_govt(self):
        from apps.scholarship.genuineness.salary_doc import salary_genuineness
        for text in (GOVT_SLIP, 'PENYATA GAJI\nGAJI POKOK 1,800\nGAJI BERSIH 1,700',
                     'SLIP GAJI\nGRED DG 41\nGAJI POKOK 3,000', 'JANM\nGAJI POKOK 1,900'):
            with self.subTest(text[:12]):
                g = salary_genuineness(text)
                self.assertEqual((g['status'], g['family']), ('genuine', 'govt'))

    def test_a_bare_gred_label_or_janm_inside_a_word_is_not_govt(self):
        from apps.scholarship.genuineness.salary_doc import score_family
        for text in ('SLIP GAJI\nGRED JAWATAN\nGAJI POKOK 900', 'SLIP GAJI KEDAI XJANM JANMY\nGAJI POKOK 900'):
            with self.subTest(text[10:20]):
                self.assertIs(score_family(text)['govt'], False)

    def test_a_support_letter_is_scored_only_when_it_is_a_declaration(self):
        from apps.scholarship.genuineness.declaration_doc import income_doc_genuineness
        self.assertEqual(income_doc_genuineness('SURAT PENGESAHAN PENDAPATAN\nRM800', 'income_support_doc')['family'],
                         'declaration')
        self.assertEqual(income_doc_genuineness('Kepada sesiapa yang berkenaan, gaji RM800', 'income_support_doc'), {})


class TheExtraction(SimpleTestCase):

    def test_both_slots_read_the_approval(self):
        """The four fields and the prompt hint reach both income slots (Gemini reads the image)."""
        from apps.scholarship import vision
        from apps.scholarship.income_declaration import APPROVAL_FIELDS, APPROVAL_HINT
        for slot in ('salary_slip', 'income_support_doc'):
            with self.subTest(slot):
                self.assertLessEqual(set(APPROVAL_FIELDS), set(vision._FIELD_SCHEMAS[slot]['properties']))
                self.assertIn(APPROVAL_HINT, vision._DOC_HINTS[slot])

    def test_a_read_that_ran_always_carries_the_approval_keys(self):
        """So 'never checked' (a read before the rule) stays tellable from 'checked, nothing found'."""
        from apps.scholarship import vision
        from apps.scholarship.income_declaration import APPROVAL_FIELDS
        for slot in ('salary_slip', 'income_support_doc'):
            with self.subTest(slot):
                self.assertLessEqual(set(APPROVAL_FIELDS), set(vision._sanitize_extracted_fields(slot, {'name': 'X'})))
        self.assertNotIn('issuer_header', vision._sanitize_extracted_fields('epf', {'name': 'X'}))


#: What a read since the rule stores when the document shows no header or approver at all.
CHECKED = {'issuer_header': '', 'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no'}


def _doc(app, doc_type, *, member='father', fields=None, seen='declaration', status='suspect', verdict='ok'):
    vf = {'fields': fields or {}, 'student_verdict': verdict, 'error': ''}
    if seen is not None:
        vf['authenticity'] = {'status': status, 'doc_seen': seen, 'probability': 0.5}
    return ApplicantDocument.objects.create(
        application=app, doc_type=doc_type, household_member=member, vision_fields=vf,
        storage_path=f'test/{doc_type}/{ApplicantDocument.objects.count()}', vision_run_at=timezone.now())


class TheApproverRule(SimpleTestCase):

    def _doc(self, doc_type='salary_slip', seen='declaration', **fields):
        vf = {'fields': fields}
        if seen:
            vf['authenticity'] = {'status': 'suspect', 'doc_seen': seen}
        return ApplicantDocument(doc_type=doc_type, vision_fields=vf)

    def test_what_an_informal_document_lacks(self):
        from apps.scholarship.income_declaration import approval_counts, approval_missing, missing_reason
        cases = [(CHECKED, ('header', 'approver'), 'approval_no_header_approver'),
                 ({**CHECKED, 'issuer_header': 'SK CONTOH'}, ('approver',), 'approval_no_approver'),
                 ({**CHECKED, 'approver_title': 'Guru Besar', 'has_stamp_or_signature': 'yes'}, ('header',),
                  'approval_no_header'),
                 ({**CHECKED, 'issuer_header': 'SK CONTOH', 'approver_name': 'CIKGU CONTOH'},
                  ('approver',), 'approval_no_approver'),          # a name with no mark is no approver
                 ({**CHECKED, 'issuer_header': 'SK CONTOH', 'has_stamp_or_signature': 'yes'}, ('approver',),
                  'approval_no_approver'),                          # a mark nobody owns is no approver
                 (APPROVED, (), '')]
        for slot, seen in (('salary_slip', 'declaration'), ('salary_slip', 'informal'), ('income_support_doc', None)):
            for fields, missing, reason in cases:
                with self.subTest(slot=slot, seen=seen, fields=fields):
                    doc = self._doc(slot, seen, **fields)
                    self.assertEqual(approval_missing(doc), missing)
                    self.assertEqual(missing_reason(doc), reason)
                    self.assertIs(approval_counts(doc), not missing)

    def test_a_document_read_before_the_rule_is_unchecked_not_missing(self):
        from apps.scholarship.income_declaration import (approval_counts, approval_missing, approval_unchecked,
                                                         missing_reason)
        for slot, seen in (('income_support_doc', None), ('salary_slip', 'informal')):
            with self.subTest(slot):
                doc = self._doc(slot, seen, amount='RM800')        # no approval key at all
                self.assertIs(approval_unchecked(doc), True)
                self.assertEqual(approval_missing(doc), ())         # never "get it signed"
                self.assertIs(approval_counts(doc), False)          # TD-394: never pass on what nobody read
                self.assertEqual(missing_reason(doc), 'approval_unchecked')

    def test_a_formal_or_unscored_payslip_is_not_informal(self):
        from apps.scholarship.income_declaration import approval_counts, is_informal
        for seen in ('private', 'govt', None):
            with self.subTest(seen):
                slip = self._doc('salary_slip', seen)
                self.assertIs(is_informal(slip), False)
                self.assertIs(approval_counts(slip), True)


class _Case(TestCase):

    def _app(self, **kw):
        kw.setdefault('income_route', 'salary')
        kw.setdefault('income_working_members', ['father'])
        kw.setdefault('mother_occupation', 'homemaker')
        return make_application(
            'profile_complete', income_earner='', father_name='Murugan', father_occupation='fisherman',
            other_family_members=[], student=make_student(name=STUDENT, nric=STUDENT_NRIC), **kw)

    def _father_ic(self, app):
        ApplicantDocument.objects.create(
            application=app, doc_type='parent_ic', household_member='father', vision_name=FATHER,
            vision_nric=FATHER_NRIC, storage_path=f'test/pic/{app.id}', vision_run_at=timezone.now())


class ThePerEarnerAnswerAndTheGate(_Case):

    def test_an_unapproved_form_in_the_payslip_slot_shows_nothing_and_asks_for_it_signed(self):
        from apps.scholarship.income_shown import income_shown
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._father_ic(app)
        form = _doc(app, 'salary_slip', fields={'gross_income': 'RM800', **CHECKED})
        a = income_shown(app, 'father')
        self.assertIs(a.shown, False)
        self.assertEqual([u.as_dict() for u in a.unusable], [{'doc_id': form.id, 'doc_type': 'salary_slip',
                                                             'reason': 'approval_no_header_approver'}])
        out = income_doc_blockers(app)
        self.assertIn('income_doc_unapproved:father', out)
        self.assertNotIn('income_evidence_missing:father', out)

    def test_an_informal_payslip_needs_its_approver_too(self):
        """Ruling 2A: an informal employer's slip counts only signed and stamped (a real payslip as before)."""
        from apps.scholarship.income_shown import income_shown
        for fields, shown in ((CHECKED, False), (APPROVED, True)):
            with self.subTest(shown):
                app = self._app()
                _doc(app, 'salary_slip', seen='informal', fields={'gross_income': '900', **fields})
                a = income_shown(app, 'father')
                self.assertEqual((a.shown, a.declared), (shown, False))   # a payslip, not a declared amount

    def test_an_approved_form_counts_but_as_a_declared_amount(self):
        from apps.scholarship.income_shown import income_shown
        from apps.scholarship.services import income_doc_blockers
        app = self._app()
        self._father_ic(app)
        _doc(app, 'salary_slip', fields={'gross_income': 'RM800', **APPROVED})
        a = income_shown(app, 'father')
        self.assertEqual((a.shown, a.way, a.declared), (True, 'salary_slip', True))
        self.assertEqual(income_doc_blockers(app), [])

    def test_a_real_payslip_or_epf_outranks_an_approved_form(self):
        from apps.scholarship.income_shown import income_shown
        for other, way in (('salary_slip', 'salary_slip'), ('epf', 'epf')):
            with self.subTest(other):
                app = self._app()
                _doc(app, 'salary_slip', fields={'gross_income': 'RM800', **APPROVED})
                _doc(app, other, seen='private' if other == 'salary_slip' else None, status='genuine',
                     fields={'gross_income': '1,450.00', 'monthly_contribution': '300.00'})
                a = income_shown(app, 'father')
                self.assertEqual((a.shown, a.way, a.declared), (True, way, False))

    def test_any_support_letter_backs_a_declared_amount_only_when_approved(self):
        """Ruling 2A: a plain penghulu / employer letter too — not only a declaration form."""
        from apps.scholarship.income_engine import has_income_support_doc
        from apps.scholarship.services import income_doc_blockers
        for seen in ('declaration', None):
            for fields, counts in (({'amount': 'RM800', **CHECKED}, False), ({'amount': 'RM800', **APPROVED}, True)):
                with self.subTest(seen=seen, counts=counts):
                    app = self._app(income_declared={'father': 800})
                    self._father_ic(app)
                    _doc(app, 'income_support_doc', seen=seen, fields=fields)
                    self.assertIs(has_income_support_doc(app, 'father'), counts)
                    out = income_doc_blockers(app)
                    self.assertEqual('income_doc_unapproved:father' in out, not counts)

    def test_an_unchecked_letter_does_not_count_and_the_family_is_told_we_are_still_checking(self):
        """TD-394 + never blame: no "get it signed", no "show their income" — the existing "try later"."""
        from apps.scholarship.income_engine import has_income_support_doc
        from apps.scholarship.services import income_doc_blockers
        app = self._app(income_declared={'father': 800})
        self._father_ic(app)
        _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM800'})     # read before the rule
        self.assertIs(has_income_support_doc(app, 'father'), False)
        out = income_doc_blockers(app)
        self.assertIn('ic_service_down', out)
        self.assertNotIn('income_doc_unapproved:father', out)
        self.assertNotIn('income_evidence_missing:father', out)


class TheCoachAndCheckTwo(_Case):

    def test_the_coach_asks_for_it_signed(self):
        from apps.scholarship.help_engine import verdict_for_document
        from apps.scholarship.income_engine import student_income_proof_check
        app = self._app()
        self._father_ic(app)
        form = _doc(app, 'salary_slip', fields={'gross_income': 'RM800', **CHECKED, 'issuer_header': 'SK CONTOH'})
        self.assertEqual(student_income_proof_check(form)['approval_missing'], ['approver'])
        self.assertEqual(verdict_for_document(form), 'income_doc_needs_approver')
        approved = _doc(app, 'salary_slip', fields={'gross_income': 'RM800', **APPROVED})
        self.assertEqual(verdict_for_document(approved), '')
        unchecked = _doc(app, 'salary_slip', seen='informal', fields={'gross_income': '900'})
        self.assertEqual(verdict_for_document(unchecked), '')          # ours to finish, no coach

    def test_check_two_asks_again_for_a_member_whose_only_proof_is_an_unapproved_form(self):
        from apps.scholarship.check2_queries import sync_check2_queries
        app = self._app(income_working_members=['father', 'mother'], mother_occupation='private',
                        mother_name='Lakshmi')
        self._father_ic(app)
        _doc(app, 'salary_slip', seen='private', status='genuine', fields={'gross_income': '1,450.00'})
        _doc(app, 'salary_slip', member='mother', fields={'gross_income': 'RM400', **CHECKED})
        sync_check2_queries(app)
        self.assertTrue(app.resolution_items.filter(code='mother_income_proof_missing', status='open').exists())

    def test_check_two_waits_while_her_document_is_unchecked(self):
        """Not asked again for what she sent: the re-read decides (`check2_deferred`)."""
        from apps.scholarship.check2_queries import sync_check2_queries
        app = self._app(income_working_members=['father', 'mother'], mother_occupation='private',
                        mother_name='Lakshmi')
        self._father_ic(app)
        _doc(app, 'salary_slip', seen='private', status='genuine', fields={'gross_income': '1,450.00'})
        _doc(app, 'salary_slip', member='mother', seen='informal', fields={'gross_income': 'RM400'})
        sync_check2_queries(app)
        self.assertFalse(app.resolution_items.filter(code='mother_income_proof_missing').exists())


