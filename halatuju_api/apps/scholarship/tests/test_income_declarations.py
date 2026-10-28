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

    def test_a_government_pension_statement_is_govt(self):
        """Review of d0d5d079 / round 2: a JPA / PERKESO pension STATEMENT is computer-printed and never
        stamped, so it stays a formal family — a pension issuer word WITH a statement marker."""
        from apps.scholarship.genuineness.salary_doc import salary_genuineness
        for text in ('JABATAN PERKHIDMATAN AWAM MALAYSIA\nPENYATA BAYARAN BAGI TAHUN 2026\nPENCEN BULANAN 1,200.00\n'
                     'JUMLAH PENDAPATAN 1,200.00',
                     'JABATAN PERKHIDMATAN AWAM MALAYSIA\nwww.jpa.gov.my\nPENDAPATAN 1,200.00',
                     'KWAP\nNo. Akaun Pencen: 000000\nPENDAPATAN BERSIH 900.00',
                     'PERKESO\nPENYATA BAYARAN FAEDAH 2026\nPENCEN PENAKAT\nJUMLAH PENDAPATAN 687.50'):
            with self.subTest(text[:14]):
                g = salary_genuineness(text)
                self.assertEqual((g['status'], g['family']), ('genuine', 'govt'))

    def test_a_form_s_sector_field_or_a_lone_pension_word_is_not_govt(self):
        """Round 2: a self-written statement naming JPA in an occupation line, or "pencen KWAP" in a line,
        has no statement layout — not govt; nor half a pension title, nor the site alone."""
        from apps.scholarship.genuineness.salary_doc import score_family
        for text in (UNTITLED, 'MAKLUMAT\nSektor: Perkhidmatan Awam\nPENDAPATAN BERSIH 800',
                     'MAKLUMAT IBU BAPA\nPekerjaan: Jabatan Perkhidmatan Awam\nPENDAPATAN BERSIH 900',
                     'MAKLUMAT\nSumber: pencen KWAP\nPENDAPATAN BERSIH 900', 'www.jpa.gov.my\nPENDAPATAN 800',
                     'PENYATA BAYARAN\nPENDAPATAN 800', 'BAYARAN PENCEN\nPENDAPATAN 800'):
            with self.subTest(text[:14]):
                self.assertIs(score_family(text)['govt'], False)

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

    """Review round 2: the approval is read off the IMAGE (one multimodal call), never the OCR text — a form
    prints "Cop dan tandatangan" whether its box is stamped or EMPTY, and a hand signature has no text."""

    def _doc(self, doc_type='income_support_doc'):
        return ApplicantDocument(doc_type=doc_type, content_type='image/jpeg', vision_fields={})

    def _read(self, doc, answer, *, text='SURAT PENGESAHAN\nRM800', image=b'img', ex=None):
        from unittest import mock
        from apps.scholarship.income_declaration import read_approval
        ex = ex if ex is not None else {'fields': {'amount': 'RM800'}, 'warnings': [], 'error': ''}
        with mock.patch('apps.scholarship.vision._call_gemini_json', return_value=answer) as gem:
            out = read_approval(doc, ex, text, lambda: image)
        return out, gem

    def test_the_text_read_no_longer_asks_for_the_approval(self):
        from apps.scholarship import vision
        from apps.scholarship.income_declaration import APPROVAL_FIELDS, APPROVAL_PROMPT
        for slot in ('salary_slip', 'income_support_doc'):
            with self.subTest(slot):
                self.assertFalse(set(APPROVAL_FIELDS) & set(vision._FIELD_SCHEMAS[slot]['properties']))
        for words in ('EMPTY signature or stamp boxes', 'HANDWRITTEN', 'ink or rubber-stamp impression',
                      'never from a printed label'):
            self.assertIn(words, APPROVAL_PROMPT)

    def test_an_empty_labelled_box_is_not_approval(self):
        """The model's answer for an empty "Cop dan tandatangan" box ("no") is checked — and not approved."""
        from apps.scholarship.income_declaration import approval_counts, approval_missing
        out, gem = self._read(self._doc(), {'issuer_header': 'JKKK KAMPUNG CONTOH', 'approver_name': '',
                                            'approver_title': '', 'has_stamp_or_signature': 'no'})
        self.assertEqual(gem.call_count, 1)
        self.assertEqual(gem.call_args.kwargs['image'], b'img')
        doc = self._doc()
        doc.vision_fields = {'fields': out['fields']}
        self.assertEqual(approval_missing(doc), ('approver',))
        self.assertIs(approval_counts(doc), False)

    def test_a_stamp_impression_approves(self):
        from apps.scholarship.income_declaration import approval_counts
        out, _gem = self._read(self._doc(), {'issuer_header': 'KEDAI CONTOH', 'approver_name': '',
                                             'approver_title': '', 'has_stamp_or_signature': 'stamp'})
        doc = self._doc()
        doc.vision_fields = {'fields': out['fields']}
        self.assertIs(approval_counts(doc), True)
        self.assertEqual(out['fields']['amount'], 'RM800')                 # the money fields stay the text read's

    def test_our_failure_leaves_it_unchecked_never_no(self):
        from apps.scholarship.income_declaration import APPROVAL_FIELDS, approval_unchecked
        for answer, image in (({'_error': 'Gemini error: 402 credit'}, b'img'), ({'has_stamp_or_signature': 'stamp'}, None)):
            with self.subTest(image=image):
                out, _gem = self._read(self._doc(), answer, image=image)
                self.assertFalse(set(APPROVAL_FIELDS) & set(out['fields']))
                doc = self._doc()
                doc.vision_fields = {'fields': out['fields'], **{k: out[k] for k in out if k.startswith('approval_read')}}
                self.assertIs(approval_unchecked(doc), True)

    def test_a_failed_image_read_is_retried_for_72_hours_then_checked_by_eye(self):
        """Round 3, TD-390's shape: the window is stamped at the FIRST failure and kept on the next; after it
        the officer checks by eye ("approval_unreadable") and the family is asked again (the normal ask)."""
        import time
        from apps.scholarship.income_declaration import (APPROVAL_ERROR, APPROVAL_UNTIL, approval_counts,
                                                         approval_expired, approval_missing, approval_unchecked,
                                                         missing_reason)
        out, _gem = self._read(self._doc(), {'_error': 'Gemini error: 503'})
        self.assertAlmostEqual(out[APPROVAL_UNTIL], time.time() + 72 * 3600, delta=60)
        again = self._doc()
        again.vision_fields = {APPROVAL_ERROR: 'x', APPROVAL_UNTIL: 1234}
        out2, _gem = self._read(again, {'_error': 'Gemini error: 503'})
        self.assertEqual(out2[APPROVAL_UNTIL], 1234)                         # never pushed forward
        doc = self._doc()
        doc.vision_fields = {'fields': {'amount': 'RM800'}, APPROVAL_ERROR: 'x', APPROVAL_UNTIL: int(time.time()) + 600}
        self.assertEqual((approval_unchecked(doc), approval_expired(doc), missing_reason(doc)),
                         (True, False, 'approval_unchecked'))
        doc.vision_fields[APPROVAL_UNTIL] = int(time.time()) - 1
        self.assertEqual((approval_unchecked(doc), approval_expired(doc), missing_reason(doc)),
                         (False, True, 'approval_unreadable'))
        self.assertEqual(approval_missing(doc), ('header', 'approver'))
        self.assertIs(approval_counts(doc), False)

    def test_a_two_page_form_is_read_with_its_last_page(self):
        """Round 3: the stamp is on page 2 — the one image call sees it (pages stacked, page 1 first)."""
        import io
        from PIL import Image
        from apps.scholarship.pdf_pages import pdf_pages_png
        white = Image.new('RGB', (200, 280), 'white')
        stamped = Image.new('RGB', (200, 280), 'white')
        stamped.paste(Image.new('RGB', (80, 80), (255, 0, 0)), (60, 100))     # the "stamp", page 2 only
        buf = io.BytesIO()
        white.save(buf, format='PDF', save_all=True, append_images=[stamped])
        pdf = buf.getvalue()
        doc = ApplicantDocument(doc_type='income_support_doc', content_type='application/pdf', vision_fields={})
        out, gem = self._read(doc, {'issuer_header': 'KEDAI CONTOH', 'approver_name': '', 'approver_title': '',
                                    'has_stamp_or_signature': 'stamp'}, image=pdf)
        self.assertEqual(gem.call_count, 1)
        self.assertEqual(gem.call_args.kwargs['mime_type'], 'image/png')
        sheet = Image.open(io.BytesIO(gem.call_args.kwargs['image'])).convert('RGB')

        def red(px):
            return px[0] > 180 and px[1] < 90 and px[2] < 90
        reds = [y for y in range(sheet.height) if red(sheet.getpixel((sheet.width // 2, y)))]
        self.assertTrue(reds and min(reds) > sheet.height // 2)                # the stamp, in the lower page
        self.assertEqual(out['fields']['has_stamp_or_signature'], 'stamp')
        five = io.BytesIO()                                                    # a long form: first two + last
        white.save(five, format='PDF', save_all=True, append_images=[white, white, white, stamped])
        sheet5 = Image.open(io.BytesIO(pdf_pages_png(five.getvalue()))).convert('RGB')
        self.assertAlmostEqual(sheet5.height / sheet.height, 1.5, delta=0.1)   # 3 pages, not 5
        self.assertTrue(any(red(sheet5.getpixel((sheet5.width // 2, y)))
                            for y in range(2 * sheet5.height // 3, sheet5.height)))

    def test_the_read_path_adds_the_image_approval(self):
        """Wired: a support letter's field read ends with the image approval read (one image call)."""
        from unittest import mock
        from apps.scholarship import vision
        doc = ApplicantDocument(doc_type='income_support_doc', content_type='image/jpeg', storage_path='x',
                                vision_fields={})
        doc.save = lambda *a, **k: None
        answer = {'name': 'AHMAD', 'amount': 'RM800', 'issuer': 'JKKK', 'kind': 'community_letter',
                  'issuer_header': 'JKKK KAMPUNG CONTOH', 'approver_name': 'ENCIK CONTOH',
                  'approver_title': 'Ketua Kampung', 'has_stamp_or_signature': 'stamp', 'warnings': []}
        ocr = {'text': 'SURAT PENGESAHAN PENDAPATAN\nRM800', 'words': None, 'image': b'img', 'error': None}
        with mock.patch('apps.scholarship.vision._call_gemini_json', return_value=dict(answer)) as gem:
            vision._run_field_extraction_impl(doc, names=['AHMAD'], ocr=ocr)
        self.assertEqual(doc.vision_fields['fields']['has_stamp_or_signature'], 'stamp')
        self.assertTrue(any(c.kwargs.get('image') == b'img' for c in gem.call_args_list))

    def test_the_read_path_stores_a_failed_image_read_for_the_retry(self):
        from unittest import mock
        from apps.scholarship import vision
        from apps.scholarship.income_declaration import APPROVAL_ERROR, APPROVAL_UNTIL, approval_unchecked
        doc = ApplicantDocument(doc_type='income_support_doc', content_type='image/jpeg', storage_path='x',
                                vision_fields={})
        doc.save = lambda *a, **k: None
        text_read = {'name': 'AHMAD', 'amount': 'RM800', 'issuer': 'JKKK', 'kind': 'community_letter', 'warnings': []}
        ocr = {'text': 'SURAT PENGESAHAN PENDAPATAN\nRM800', 'words': None, 'image': b'img', 'error': None}
        with mock.patch('apps.scholarship.vision._call_gemini_json',
                        side_effect=[text_read, {'_error': 'Gemini error: 503'}]):
            vision._run_field_extraction_impl(doc, names=['AHMAD'], ocr=ocr)
        self.assertIn(APPROVAL_ERROR, doc.vision_fields)
        self.assertIn(APPROVAL_UNTIL, doc.vision_fields)
        self.assertIs(approval_unchecked(doc), True)

    def test_only_informal_income_documents_cost_the_extra_call(self):
        _out, gem = self._read(self._doc('salary_slip'), {}, text=GOVT_SLIP)            # a formal payslip
        gem.assert_not_called()
        _out, gem = self._read(self._doc('salary_slip'), {}, text=UNTITLED)             # an informal one
        self.assertEqual(gem.call_count, 1)
        _out, gem = self._read(self._doc('epf'), {})
        gem.assert_not_called()
        bank = {'fields': {'kind': 'bank_statement', 'issuer': 'Malayan Banking Berhad (Maybank)', 'amount': 'RM800'},
                'warnings': [], 'error': ''}
        _out, gem = self._read(self._doc(), {}, text='MAYBANK\nPENYATA AKAUN\nBAKI', ex=bank)   # 4A: no call
        gem.assert_not_called()
        _out, gem = self._read(self._doc(), {}, text=FORM, ex=dict(bank))   # a declaration labelled "bank": call
        self.assertEqual(gem.call_count, 1)
        typed = {'fields': {'kind': 'bank_statement', 'issuer': 'PENYATA BANK', 'amount': 'RM800'},
                 'warnings': [], 'error': ''}
        _out, gem = self._read(self._doc(), {}, text='PENYATA BANK\nBAKI RM800', ex=typed)   # names no bank: call
        self.assertEqual(gem.call_count, 1)
        _out, gem = self._read(self._doc(), {}, ex={'fields': {}, 'warnings': [], 'error': 'Gemini error: 503'})
        gem.assert_not_called()                                                          # a failed read: no call


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
                 ({**CHECKED, 'issuer_header': 'SK CONTOH', 'has_stamp_or_signature': 'signature'}, ('approver',),
                  'approval_no_approver'),                          # a signature nobody owns is no approver
                 ({**CHECKED, 'issuer_header': 'SK CONTOH', 'has_stamp_or_signature': 'yes'}, ('approver',),
                  'approval_no_approver'),                          # an older "yes" reads as a signature
                 ({**CHECKED, 'issuer_header': 'KEDAI CONTOH', 'has_stamp_or_signature': 'stamp'}, (), ''),  # 3A
                 ({**CHECKED, 'has_stamp_or_signature': 'stamp'}, ('header',), 'approval_no_header'),
                 ({**CHECKED, 'issuer_header': 'SK CONTOH', 'approver_title': 'Guru Besar',
                   'has_stamp_or_signature': 'signature'}, (), ''),    # a titled signer
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

    def test_owner_ruling_3a_a_company_chop_alone_approves(self):
        """3A (2026-10-28): a small shop's payslip with its chop counts, no named signer needed; a letter
        with only a header, or a signature nobody is named for, or a QR code only, does not."""
        from apps.scholarship.income_shown import income_shown
        for fields, shown in (({'issuer_header': 'KEDAI RUNCIT CONTOH', 'has_stamp_or_signature': 'stamp'}, True),
                              ({'issuer_header': 'KEDAI RUNCIT CONTOH', 'has_stamp_or_signature': 'no'}, False),
                              ({'issuer_header': 'KEDAI RUNCIT CONTOH', 'has_stamp_or_signature': 'signature'}, False),
                              ({'issuer_header': 'KEDAI RUNCIT CONTOH', 'approver_name': 'AH CONTOH',
                                'has_stamp_or_signature': 'signature'}, True)):
            with self.subTest(fields):
                app = self._app()
                _doc(app, 'salary_slip', seen='informal', fields={'gross_income': '900', **CHECKED, **fields})
                self.assertIs(income_shown(app, 'father').shown, shown)

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

    def test_hotfix_live_shapes_a_village_stamp_with_its_approver_needs_no_letterhead(self):
        """Hotfix 2026-10-28, from the live re-read's field shapes: a stamp + a named/titled approver counts
        with NO header (a village form has none); #374 / #133 (mark 'no', no approver) and a header-only letter
        still fail."""
        from apps.scholarship.income_engine import has_income_support_doc
        blank = {'issuer_header': '', 'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no'}
        cases = (({'approver_title': 'KETUA KAMPUNG', 'has_stamp_or_signature': 'stamp'}, True),
                 ({'approver_title': 'Pengerusi JKKK', 'has_stamp_or_signature': 'stamp'}, True),
                 ({'approver_name': 'ENCIK CONTOH', 'approver_title': 'Pesuruhjaya Sumpah',
                   'has_stamp_or_signature': 'stamp'}, True),
                 ({'approver_name': 'ENCIK CONTOH', 'has_stamp_or_signature': 'stamp'}, True),
                 ({'has_stamp_or_signature': 'stamp'}, False),                     # a stamp nobody is named for
                 ({'approver_title': 'KETUA KAMPUNG', 'has_stamp_or_signature': 'signature'}, False),  # no header
                 ({}, False),                                                      # #374 / #133: mark 'no'
                 ({'issuer_header': 'JKKK KAMPUNG CONTOH'}, False))               # header only
        for fields, counts in cases:
            with self.subTest(fields):
                app = self._app(income_declared={'father': 800})
                _doc(app, 'income_support_doc', fields={'amount': 'RM800', **blank, **fields})
                self.assertIs(has_income_support_doc(app, 'father'), counts)

    def test_hotfix_a_government_payslip_or_pension_statement_is_not_informal(self):
        """JHEV veteran pension statements and a Dewan Bahasa dan Pustaka payslip (scored 'informal', mark 'no')
        are official statements; a DECLARATION form on a ministry's form keeps the approver rule."""
        from apps.scholarship.income_shown import income_shown
        blank = {'approver_name': '', 'approver_title': '', 'has_stamp_or_signature': 'no'}
        for seen, header, shown in (('informal', 'JABATAN HAL EHWAL VETERAN ATM KEMENTERIAN PERTAHANAN', True),
                                    ('informal', 'DEWAN BAHASA DAN PUSTAKA', True),
                                    ('informal', 'KEDAI RUNCIT CONTOH', False),
                                    ('informal', 'JABATAN KERJA SENDIRI', False),          # review: bare word
                                    ('informal', 'MAJLIS BELIA KAMPUNG', False),
                                    ('informal', 'JABATAN PERTANIAN, PUTRAJAYA', True),    # + a second marker
                                    ('informal', 'KEMENTERIAN KESIHATAN MALAYSIA', True),  # a ministry by name
                                    ('declaration', 'KEMENTERIAN PENDIDIKAN BAHAGIAN MATRIKULASI', False)):
            with self.subTest(header):
                app = self._app()
                _doc(app, 'salary_slip', seen=seen, fields={'gross_income': '1,800.00', 'issuer_header': header, **blank})
                self.assertIs(income_shown(app, 'father').shown, shown)

    def test_hotfix_a_bank_named_on_the_letterhead_counts(self):
        """A live statement's text read named no issuer; its letterhead (the image read) did."""
        from apps.scholarship.income_engine import has_income_support_doc
        for header, counts in (('MAYBANK ISLAMIC BERHAD', True), ('', False)):
            with self.subTest(header):
                app = self._app(income_declared={'father': 800})
                _doc(app, 'income_support_doc', seen=None,
                     fields={'kind': 'bank_statement', 'issuer': '', 'amount': 'RM800', **CHECKED,
                             'issuer_header': header})
                self.assertIs(has_income_support_doc(app, 'father'), counts)

    def test_owner_ruling_4a_a_bank_statement_needs_no_approver(self):
        """4A (2026-10-28): the bank's header is enough — a statement whose issuer NAMES a known Malaysian bank
        counts with no approver (and is not "still checking"); a self-typed "PENYATA BANK" naming no bank, or
        one the scorer reads as a DECLARATION form, still needs its approver."""
        from apps.scholarship.income_engine import has_income_support_doc
        from apps.scholarship.income_declaration import is_informal
        cases = ((None, 'Malayan Banking Berhad', {}, False, True), (None, 'CIMB BANK BERHAD', {}, False, True),
                 (None, 'bank islam malaysia', {}, False, True),
                 (None, 'PENYATA BANK', {}, True, False), (None, 'PENYATA BANK', CHECKED, True, False),
                 (None, 'Kedai RHBX', {}, True, False),                       # whole words only
                 ('declaration', 'Maybank', {}, True, False), ('declaration', 'Maybank', APPROVED, True, True))
        for seen, issuer, fields, informal, counts in cases:
            with self.subTest(seen=seen, issuer=issuer, fields=fields):
                app = self._app(income_declared={'father': 800})
                d = _doc(app, 'income_support_doc', seen=seen,
                         fields={'kind': 'bank_statement', 'issuer': issuer, 'amount': 'RM800', **fields})
                self.assertIs(is_informal(d), informal)
                self.assertIs(has_income_support_doc(app, 'father'), counts)

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

    def test_the_hourly_sweep_re_reads_each_unchecked_document_once(self):
        """Review of d0d5d079: the self-heal sweep re-reads a live unchecked income document on an open
        case — a support letter, an informal / declaration / govt payslip — once, gated like read_retry."""
        from unittest import mock
        from apps.scholarship.services import reprocess_unread_ic_documents
        from apps.scholarship.services.read_retry import approval_unchecked_documents
        app = self._app()
        letter = _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM800'})
        govt = _doc(app, 'salary_slip', seen='govt', status='genuine', fields={'gross_income': '800'})
        _doc(app, 'salary_slip', seen='private', status='genuine', fields={'gross_income': '1,450'})   # formal
        _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM800', **APPROVED})              # checked
        _doc(app, 'income_support_doc', seen=None, fields={}, verdict='')                              # never read
        closed = self._app()
        closed.status = 'closed'
        closed.save(update_fields=['status'])
        _doc(closed, 'income_support_doc', seen=None, fields={'amount': 'RM800'})
        self.assertEqual({d.id for d in approval_unchecked_documents(50)}, {letter.id, govt.id})

        def reread(doc):
            doc.vision_fields = {'fields': {**doc.vision_fields['fields'], **CHECKED}, 'student_verdict': 'ok'}
            doc.save(update_fields=['vision_fields'])
        with mock.patch('apps.scholarship.services.outage.gemini_reads_down', return_value=False), \
                mock.patch('apps.scholarship.reextract.reextract_document', side_effect=reread) as rx:
            reprocess_unread_ic_documents()
            self.assertLessEqual({letter.id, govt.id}, {c.args[0].id for c in rx.call_args_list})
            rx.reset_mock()
            reprocess_unread_ic_documents()                       # read now: never picked again
            self.assertFalse({letter.id, govt.id} & {c.args[0].id for c in rx.call_args_list})

    def test_the_sweep_waits_while_gemini_is_down_and_tries_a_failing_read_only_once(self):
        from unittest import mock
        from apps.scholarship.services import reprocess_unread_ic_documents
        from apps.scholarship.services.read_retry import approval_unchecked_documents
        app = self._app()
        letter = _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM800'})
        with mock.patch('apps.scholarship.services.outage.gemini_reads_down', return_value=True), \
                mock.patch('apps.scholarship.reextract.reextract_document') as rx:
            reprocess_unread_ic_documents()
            rx.assert_not_called()
        with mock.patch('apps.scholarship.services.outage.gemini_reads_down', return_value=False), \
                mock.patch('apps.scholarship.reextract.reextract_document') as rx:    # a read that lands nothing
            reprocess_unread_ic_documents()
        self.assertNotIn(letter.id, {d.id for d in approval_unchecked_documents(50)})   # tried: officer's now

    def test_the_sweep_retries_a_failed_image_read_inside_its_window_only(self):
        import time
        from apps.scholarship.services.read_retry import APPROVAL_TRIED, approval_unchecked_documents
        app = self._app()
        now = int(time.time())
        live = _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM800'})
        live.vision_fields = {**live.vision_fields, APPROVAL_TRIED: now, 'approval_read_error': 'x',
                              'approval_read_until': now + 3600}
        live.save(update_fields=['vision_fields'])
        gone = _doc(app, 'income_support_doc', seen=None, fields={'amount': 'RM900'})
        gone.vision_fields = {**gone.vision_fields, 'approval_read_error': 'x', 'approval_read_until': now - 1}
        gone.save(update_fields=['vision_fields'])
        self.assertEqual({d.id for d in approval_unchecked_documents(50)}, {live.id})

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


