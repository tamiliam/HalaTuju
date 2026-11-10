"""Audit sprint A3.8 — GOLDEN CASES for the money modules, recorded BEFORE the split.

A3.8 splits ``contracts.py`` and ``sponsorship.py`` into packages and breaks up two long functions —
``bursary.render_agreement_html`` and ``services.offer_sync.autofill_pathway_from_offer`` — by MOVING
code, never changing it. The signed agreement is a legal document and the payment schedule decides
what a student is paid, so "the tests still pass" is not enough. Every case below is compared with
``fixtures/a38_money_goldens.json``, which was written on the untouched tree:

  * ``agreement`` — the full agreement HTML, BYTE-EQUAL, across two gifts (a deployed flagship
    template and a second gift's draft with its own wording, clauses and schedule), several amounts,
    pathways (STPM fresh and continuing, matric, university, a pathway with no row of its own) and
    locales (en, ms, and ta falling back to en), plus the schedule row each case was paid on;
  * ``schedules`` — every schedule reader (summary text, table, calendar, paid-month grid, quiz
    checkpoints, locale resolution) and the preview HTML, for both templates and all three locales;
  * ``autofill`` — what ``autofill_pathway_from_offer`` returned, the ORDER of the saves it made (with
    their ``update_fields``) and the fields it left, for every branch of the function;
  * ``surface`` — every name the four modules define, with its signature, so the old import paths
    (``apps.scholarship.contracts.X``, ``apps.scholarship.sponsorship.X``) must keep resolving.

⚠ NEVER RE-RECORD THIS FILE TO MAKE A REFACTOR GREEN. A difference here is a change to a contract or
a payment, and it stops the sprint. Re-record (``UPDATE_A38_GOLDEN=1``, run serially) only for a
deliberate, owner-approved change, and say so in the commit.

All people here are made up. No real student data, no database dump.
"""
import ast
import datetime
import inspect
import json
import os
import pathlib
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from apps.courses.models import (
    Course, CourseInstitution, FieldTaxonomy, Institution, StpmCourse, StpmRequirement,
)
from apps.scholarship import bursary, contracts, sponsorship
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import autofill_pathway_from_offer, offer_sync
from apps.scholarship.tests.contract_helpers import brightpath_org, make_deployable, seed_draft
from apps.scholarship.tests.factories import (
    create_document, fake_nric, make_application, make_cohort, make_programme, make_student,
)
from apps.scholarship.tests.test_offer_course_match import seed_realign_catalogue

GOLDEN = pathlib.Path(__file__).parent / 'fixtures' / 'a38_money_goldens.json'
UPDATE = os.environ.get('UPDATE_A38_GOLDEN') == '1'

STUDENT = 'PELAJAR CONTOH A/P UJIAN'
STUDENT_NRIC = '080808-14-0808'
GUARDIAN = 'PENJAGA CONTOH A/L UJIAN'
GUARDIAN_NRIC = '700707-14-0707'
SIGNED = datetime.datetime(2026, 8, 3, 10, 15, tzinfo=datetime.timezone.utc)
COUNTERSIGNED = datetime.datetime(2026, 8, 5, 16, 40, tzinfo=datetime.timezone.utc)


def _j(value):
    """A JSON-stable picture of a value (Decimals, dates and tuples made plain)."""
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _load():
    if GOLDEN.exists():
        return json.loads(GOLDEN.read_text(encoding='utf-8'))
    return {}


class _GoldenBase(TestCase):
    SECTION = ''

    def check(self, results):
        """Compare (or, under UPDATE_A38_GOLDEN=1, record) this section's answers."""
        results = _j(results)
        data = _load()
        if UPDATE:
            data[self.SECTION] = results
            GOLDEN.parent.mkdir(parents=True, exist_ok=True)
            GOLDEN.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + '\n',
                              encoding='utf-8')
            return
        self.assertIn(self.SECTION, data, f'{GOLDEN.name} has no "{self.SECTION}" section')
        golden = data[self.SECTION]
        self.assertEqual(sorted(results), sorted(golden), 'the case list itself changed')
        for case in sorted(golden):
            with self.subTest(case=case):
                self.assertEqual(results[case], golden[case])


# ── the two templates ───────────────────────────────────────────────────────────────────────

#: The second gift's own wording — merge variables (one unknown, left visible), **bold**, characters
#: that must be escaped, and a clause tree three levels deep.
SECOND_CONFIG = {
    'title_en': 'Golden Gift Bursary Agreement for {{student_name}}',
    'title_ms': 'Perjanjian Biasiswa Hadiah Emas untuk {{student_name}}',
    'preamble_en': ('This agreement is made between **the Foundation** and {{student_name}} '
                    '({{student_nric}}) for {{amount}} at {{institution}} reading {{course}}, '
                    'starting {{commencement_date}}. Kept as typed: {{not_a_variable}} & <b>.'),
    'preamble_ms': 'Perjanjian ini antara **Yayasan** dan {{student_name}} untuk {{amount}}.',
    'progress_standard_en': 'Pass every semester with a CGPA of 2.50 or better.',
    'progress_standard_ms': 'Lulus setiap semester dengan PNGK 2.50 atau lebih.',
    'counterparty_name': 'Pegawai Contoh',
    'counterparty_title': 'Pengarah <Ujian> & Co',
    'counterparty_nric': '000000-00-0001',
    'counterparty_address': 'No. 1, Jalan Contoh, 50000 Kuala Lumpur',
    'parent_role': 'minor_only',
}
SECOND_CLAUSES = [
    {'heading_en': 'Award', 'body_en': 'The award is {{amount}} for **{{course}}**.',
     'heading_ms': 'Anugerah', 'body_ms': 'Anugerah ialah {{amount}}.', 'level': 0},
    {'heading_en': 'Payment', 'body_en': 'Paid monthly into the account of {{student_name}}.',
     'heading_ms': 'Bayaran', 'body_ms': '', 'level': 1},
    {'heading_en': 'Exam months', 'body_en': 'No payment in an exam month < > &.',
     'heading_ms': '', 'body_ms': '', 'level': 2},
    {'heading_en': 'Progress', 'body_en': '{{progress_standard}}', 'level': 1},
    {'heading_en': 'Guarantor', 'body_en': '{{guarantor_name}} ({{guarantor_relationship}}) '
     'stands surety.', 'heading_ms': 'Penjamin', 'body_ms': '{{guarantor_name}} menjamin.',
     'level': 0},
]
SECOND_SCHEDULE = [
    {'pathway': 'stpm', 'variant': '', 'label_en': 'Form Six', 'label_ms': 'Tingkatan Enam',
     'monthly_amount': '200', 'start_month': 11, 'paid_offsets': [0, 1, 2, 3, 5, 6, 7, 8, 9, 10,
                                                                  11, 12, 13, 15, 16]},
    {'pathway': 'stpm', 'variant': 'continuing', 'label_en': 'Form Six (second year)',
     'monthly_amount': '125', 'start_month': 1, 'paid_offsets': [0, 1, 2, 3, 4, 5, 6, 7]},
    {'pathway': 'university', 'variant': '', 'label_en': 'Degree', 'label_ms': 'Ijazah',
     'monthly_amount': '250', 'start_month': 9, 'paid_offsets': [0, 1, 2, 4, 5, 6, 7, 8]},
    {'pathway': 'default', 'variant': '', 'label_en': 'Everyone else', 'label_ms': 'Lain-lain',
     'monthly_amount': '200', 'start_month': 7, 'paid_offsets': [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]},
]


def _templates():
    """(flagship, deployed) and (a second gift, draft) — the same two in every section."""
    first = make_deployable('2026-v1')
    contracts.submit_for_deployment(first)
    contracts.deploy(first, is_super=True)
    first.refresh_from_db()
    make_programme(organisation=brightpath_org(), code='a38-golden-gift', name_en='Golden Gift')
    second = seed_draft('2026-a38', programme='a38-golden-gift')
    contracts.update_config(second, **SECOND_CONFIG)
    contracts.replace_clauses(second, SECOND_CLAUSES)
    contracts.replace_schedule(second, SECOND_SCHEDULE)
    second.refresh_from_db()
    return first, second


# ── 1. the agreement HTML, byte-equal ───────────────────────────────────────────────────────

class TestGoldenAgreement(_GoldenBase):
    SECTION = 'agreement'

    @classmethod
    def setUpTestData(cls):
        cls.first, cls.second = _templates()
        cls.cohort = make_cohort(year=2026)

    def _app(self, **over):
        student = make_student(name=STUDENT, nric=STUDENT_NRIC)
        return make_application('submitted', cohort=self.cohort, student=student, **over)

    def _render(self, app, template, locale, *, parties='signed', particulars=None):
        p = particulars if particulars is not None else bursary.particulars_for(app, template, locale)
        if parties == 'signed':
            student = {'name': STUDENT, 'nric': STUDENT_NRIC, 'signed_at': SIGNED}
            guarantor = {'name': GUARDIAN, 'nric': GUARDIAN_NRIC, 'relationship': 'Father',
                         'signed_at': SIGNED}
            foundation = {'name': template.counterparty_name, 'nric': template.counterparty_nric,
                          'title': template.counterparty_title, 'signed_at': COUNTERSIGNED}
            witness = {'name': 'Saksi Contoh', 'org': 'Pertubuhan Contoh', 'signed_at': COUNTERSIGNED}
        else:   # nobody has signed yet; the witness is only an organisation
            student = {'name': STUDENT, 'nric': STUDENT_NRIC}
            guarantor = {'name': GUARDIAN}
            foundation = {'name': template.counterparty_name}
            witness = {'org': 'Pertubuhan <Contoh> & Rakan'}
        html = bursary.render_agreement_html(
            app, p, student=student, guarantor=guarantor, foundation=foundation, witness=witness,
            locale=locale, template=template)
        row = contracts.schedule_row_for(template, app)
        return {'html': html, 'particulars': p,
                'row': [row.pathway, row.variant] if row is not None else None}

    def test_agreement_html_is_byte_equal(self):
        stpm = {'course_name': 'Tingkatan Enam', 'institution': 'SMK Contoh'}
        uni = {'course_id': 'UX0001', 'course_name': 'Sarjana Muda Sains Contoh & Ujian',
               'institution': 'Universiti Contoh <Kampus Utama>'}
        cases = {
            'flagship_stpm_fresh_en_3000': (
                self._app(chosen_pathway='stpm', award_amount=3000, chosen_programme=stpm),
                self.first, 'en', {}),
            'flagship_stpm_continuing_ms_1000': (
                self._app(chosen_pathway='stpm', award_amount=1000, chosen_programme=stpm,
                          reporting_date=datetime.date(2025, 7, 1)),
                self.first, 'ms', {}),
            'flagship_matric_ta_falls_back_2000_unsigned': (
                self._app(chosen_pathway='matric', award_amount=2000,
                          chosen_programme={'course_name': 'Program Matrikulasi'}),
                self.first, 'ta', {'parties': 'unsigned'}),
            'flagship_university_no_amount_no_programme': (
                self._app(chosen_pathway='university', award_amount=None, chosen_programme={}),
                self.first, 'en', {}),
            'flagship_unknown_pathway_takes_default': (
                self._app(chosen_pathway='kolej_komuniti', award_amount=2000, chosen_programme=uni),
                self.first, 'ms-MY', {}),
            'second_gift_stpm_en_with_commencement': (
                self._app(chosen_pathway='stpm', award_amount=3000, chosen_programme=stpm),
                self.second, 'en', {'commencement': datetime.date(2026, 11, 2)}),
            'second_gift_university_ms_unsigned': (
                self._app(chosen_pathway='university', award_amount=2000, chosen_programme=uni),
                self.second, 'ms', {'parties': 'unsigned'}),
            'second_gift_continuing_en_odd_amount': (
                self._app(chosen_pathway='stpm', award_amount='1000.5', chosen_programme=stpm,
                          reporting_date=datetime.date(2025, 3, 3)),
                self.second, 'en', {'commencement': 'Semester 1, 2026'}),
        }
        results = {}
        for name, (app, template, locale, opts) in cases.items():
            particulars = None
            if 'commencement' in opts:
                particulars = dict(bursary.particulars_for(app, template, locale),
                                   commencement_date=opts['commencement'])
            results[name] = self._render(app, template, locale, parties=opts.get('parties', 'signed'),
                                         particulars=particulars)
        self.check(results)


# ── 2. the schedule readers and the preview ─────────────────────────────────────────────────

class TestGoldenSchedules(_GoldenBase):
    SECTION = 'schedules'

    @classmethod
    def setUpTestData(cls):
        cls.first, cls.second = _templates()

    def _template_picture(self, template):
        rows = sorted(template.schedule_rows.all(), key=lambda r: (r.pathway, r.variant))
        out = {'resolve_locale': {repr(loc): contracts.resolve_locale(loc, template)
                                  for loc in ('en', 'ms', 'ta', 'ms-MY', 'fr', '', None)}}
        for lang in ('en', 'ms', 'ta'):
            out[f'table_{lang}'] = contracts.schedule_table(template, lang)
            out[f'quiz_checkpoints_{lang}'] = contracts.quiz_checkpoints(template, lang)
            out[f'preview_{lang}'] = contracts.render_preview_html(template, lang)
            for r in rows:
                key = f'{r.pathway}/{r.variant or "-"}'
                out[f'summary_{lang}_{key}'] = contracts.schedule_summary_text(r, lang)
                out[f'calendar_{lang}_{key}'] = contracts.schedule_calendar(r, 2026, lang)
        for r in rows:
            key = f'{r.pathway}/{r.variant or "-"}'
            out[f'paid_grid_{key}'] = [
                [y, m] for y in (2026, 2027, 2028) for m in range(1, 13)
                if contracts.is_paid_month(r, 2026, m, y)]
            out[f'paid_default_year_{key}'] = [
                m for m in range(1, 13) if contracts.is_paid_month(r, 2026, m)]
        out['validation'] = list(contracts.validate_for_deployment(template).errors)
        return out

    def test_schedule_readers_and_preview_are_unchanged(self):
        results = {'flagship': self._template_picture(self.first),
                   'second_gift': self._template_picture(self.second)}
        results['no_row'] = {
            'calendar': contracts.schedule_calendar(None, 2026, 'en'),
            'paid': contracts.is_paid_month(None, 2026, 1),
            'row_for_no_template': contracts.schedule_row_for(None, None),
        }
        levels = [0, 1, 2, 2, 1, 0, 3, 1, 0, 2]
        results['numbering'] = {
            'normalise_levels': contracts.normalise_levels(levels),
            'clause_numbers': contracts.clause_numbers(contracts.normalise_levels(levels)),
        }
        results['merge'] = {
            'substitute_vars': contracts.substitute_vars(
                'Dear {{student_name}}, {{amount}} {{ unknown }} {{course}}',
                {'student_name': 'A & B', 'amount': 'RM1,000.00', 'course': ''}),
        }
        self.check(results)


# ── 3. autofill_pathway_from_offer, every branch ────────────────────────────────────────────

UITM_LETTER = ('BA272 SARJANA MUDA PERNIAGAAN KEWANGAN (KEPUJIAN)', 'UiTM Shah Alam',
               'Universiti Teknologi MARA')
UM_PICK = {'course_id': 'UM6343002', 'course_name': 'Sarjana Muda Pengurusan Muamalat',
           'institution': 'Universiti Malaya', 'source': 'student_picked'}
LETTER_202 = {'programme': 'Sarjana Muda Sains Kimia dengan Kepujian - UW6442001',
              'institution': 'Kolej Allamanda', 'issuer': 'Universiti Malaysia Sarawak (UNIMAS)',
              'intake': 'Semester 1 Sesi 2023/2024'}


class TestGoldenAutofill(_GoldenBase):
    SECTION = 'autofill'

    @classmethod
    def setUpTestData(cls):
        cls.cohort = make_cohort(year=2026)
        ft = FieldTaxonomy.objects.create(key='a38acc', name_en='Accounting', name_ms='Perakaunan',
                                          name_ta='Kanakkiyal', image_slug='a38acc')
        psp = Institution.objects.create(institution_id='a38-psp', institution_name='Politeknik Seberang Perai',
                                         type='Politeknik', state='Pulau Pinang')
        puo = Institution.objects.create(institution_id='a38-puo', institution_name='Politeknik Ungku Omar',
                                         type='Politeknik', state='Perak')
        dac = Course.objects.create(course_id='DAC', course='Diploma Perakaunan', level='Diploma',
                                    department='Commerce', field='Accounting', field_key=ft)
        CourseInstitution.objects.create(course=dac, institution=psp)
        dkm = Course.objects.create(course_id='POLY-X', course='Diploma Kejuruteraan Mekanikal',
                                    level='Diploma', department='Eng', field='Eng', field_key=ft)
        CourseInstitution.objects.create(course=dkm, institution=puo)
        CourseInstitution.objects.create(course=dkm, institution=psp)
        seed_realign_catalogue()
        unimas = Institution.objects.get(institution_id='RA-UNIMAS')
        sc = StpmCourse.objects.create(course_id='UW6442001',
                                       course_name='Sarjana Muda Sains Kimia dengan Kepujian',
                                       university='Universiti Malaysia Sarawak', institution=unimas,
                                       field_key=FieldTaxonomy.objects.get(key='realign'))
        StpmRequirement.objects.create(course=sc)

    def _app(self, stage='profile_complete', **over):
        student = make_student(name=STUDENT, nric=fake_nric())
        if 'grades' in over:
            student.grades = over.pop('grades')
            student.save(update_fields=['grades'])
        base = dict(chosen_pathway='', pre_u_institution='', pre_u_track='',
                    pathways_considered=['stpm'], pathway_certainty='uncertain', chosen_programme={})
        base.update(over)
        return make_application(stage, cohort=self.cohort, student=student, **base)

    def _offer(self, app, programme, institution, *, issuer='', nric=None, name=None,
               status=None, extra=None, doc_seen=None):
        prof = app.profile
        fields = {'candidate_name': name if name is not None else prof.name,
                  'candidate_nric': (nric if nric is not None else prof.nric).replace('-', ''),
                  'programme': programme, 'institution': institution}
        if issuer:
            fields['issuer'] = issuer
        fields.update(extra or {})
        vf = {'fields': fields, 'student_verdict': 'ok', 'warnings': [], 'error': ''}
        if status or doc_seen:
            vf['authenticity'] = {k: v for k, v in (('status', status), ('doc_seen', doc_seen)) if v}
        return create_document(application=app, doc_type='offer_letter',
                               storage_path=f'fake/a38/{app.id}/offer', vision_fields=vf,
                               vision_run_at=timezone.now())

    def _run(self, app, times=1):
        saves = []
        real_save = ScholarshipApplication.save

        def spy(instance, *args, **kwargs):
            uf = kwargs.get('update_fields')
            saves.append(list(uf) if uf is not None else ['<all>'])
            return real_save(instance, *args, **kwargs)

        returns = []
        with mock.patch.object(ScholarshipApplication, 'save', spy):
            for _ in range(times):
                returns.append(autofill_pathway_from_offer(app))
        app.refresh_from_db()
        return {
            'returns': returns, 'saves': saves,
            'chosen_pathway': app.chosen_pathway, 'pre_u_institution': app.pre_u_institution,
            'pre_u_track': app.pre_u_track, 'chosen_programme': app.chosen_programme,
            'pathway_certainty': app.pathway_certainty,
            'pathway_confirmed_at_set': app.pathway_confirmed_at is not None,
            'reporting_date': app.reporting_date,
        }

    def test_autofill_fixtures_are_unchanged(self):
        r = {}
        a = self._app()
        r['no_offer_letter'] = self._run(a)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1', 'SEKOLAH MENENGAH KEBANGSAAN CONTOH JAYA')
        r['pre_u_undecided_settles_and_is_idempotent'] = self._run(a, times=2)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1 (Sains Sosial)', 'SMK Tinggi Contoh')
        r['stpm_stream_parsed'] = self._run(a)

        a = self._app(grades={'phy': 'B', 'chem': 'B', 'bio': 'C', 'addmath': 'C', 'math': 'A'})
        self._offer(a, 'Tingkatan Enam Semester 1', 'SMK Contoh')
        r['stpm_bidang_from_science_grades'] = self._run(a)

        a = self._app(pre_u_institution='smk contoh indah', pre_u_track='not_sure')
        self._offer(a, 'TINGKATAN ENAM SEMESTER 1 TAHUN 2026', 'SMK CONTOH INDAH')
        r['stpm_typed_school_kept_track_not_sure_filled'] = self._run(a)

        a = self._app(pathways_considered=['matric'])
        self._offer(a, 'Program Matrikulasi Jurusan PERAKAUNAN', 'KOLEJ MATRIKULASI CONTOH')
        r['matric_track_parsed'] = self._run(a)

        a = self._app(pathways_considered=['matric'], chosen_pathway='matric', pre_u_track='sains')
        self._offer(a, 'Program Matrikulasi (Sains)', 'KOLEJ MATRIKULASI LABUAN')
        r['matric_declared_track_kept'] = self._run(a)

        a = self._app()
        self._offer(a, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        r['tertiary_catalogue_match'] = self._run(a)

        a = self._app()
        self._offer(a, 'DIPLOMA SENI BINA', 'KOLEJ SWASTA TIADA DALAM KATALOG')
        r['tertiary_labels_only'] = self._run(a)

        a = self._app()
        self._offer(a, 'POLITEKNIK SEBERANG PERAI', 'Tarikh: 1 Julai 2026')
        r['mis_slotted_offer_sanitised'] = self._run(a)

        a = self._app(chosen_programme={'course_name': 'Asasi Perubatan', 'institution': ''})
        self._offer(a, 'Program ASASIpintar UKM', "Kolej Pendeta Za'ba, UKM")
        r['genuine_clash_left_alone'] = self._run(a)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1', 'SMK X', name='ORANG LAIN A/L CONTOH',
                    nric=fake_nric())
        r['wrong_person'] = self._run(a)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1', 'SMK Contoh', doc_seen='confirmation_form6')
        r['confirmation_letter'] = self._run(a)

        a = self._app()
        self._offer(a, '2.4.', '2.5.')
        r['nothing_readable'] = self._run(a)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1', '2.5.')
        r['clause_number_institution_dropped'] = self._run(a)

        a = self._app()
        self._offer(a, 'Tingkatan Enam Semester 1', 'SMK Contoh',
                    extra={'reporting_date': '12 Mei 2026', 'intake': 'Mei 2026'})
        r['reporting_date_written'] = self._run(a)

        a = self._app(chosen_programme={'course_name': 'Asasi Perubatan', 'institution': ''})
        self._offer(a, 'Program ASASIpintar UKM', "Kolej Pendeta Za'ba, UKM",
                    extra={'reporting_date': '3 Ogos 2026'})
        r['clash_still_writes_reporting_date'] = self._run(a)

        a = self._app(pathway_certainty='sure',
                      chosen_programme={'course_id': 'DAC', 'course_name': 'Diploma Perakaunan',
                                        'institution': 'Politeknik Seberang Perai'})
        self._offer(a, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        r['locked_specific_pick_protected'] = self._run(a)

        a = self._app(chosen_pathway='stpm', pathway_certainty='sure', pre_u_track='',
                      chosen_programme={'course_id': 'STPM-X', 'course_name': 'Tingkatan Enam',
                                        'institution': 'SMK X'})
        self._offer(a, 'Tingkatan Enam Semester 1 (Sains Sosial)', 'SMK X')
        r['locked_pre_u_track_still_standardised'] = self._run(a)

        a = self._app(pathway_certainty='sure',
                      chosen_programme={'course_id': 'DAC', 'course_name': 'Diploma Perakaunan',
                                        'institution': 'POLITEKNIK SEBERANG PERAI (POLITEKNIK PREMIER)'})
        self._offer(a, 'DAC - DIPLOMA PERAKAUNAN', 'POLITEKNIK SEBERANG PERAI')
        r['locked_institution_aligned_to_catalogue'] = self._run(a)

        a = self._app(pathway_certainty='sure',
                      chosen_programme={'course_id': 'POLY-X',
                                        'course_name': 'Diploma Kejuruteraan Mekanikal'})
        self._offer(a, 'DKM - DIPLOMA KEJURUTERAAN MEKANIKAL', 'POLITEKNIK UNGKU OMAR (POLITEKNIK PREMIER)')
        r['locked_blank_institution_from_offer_multicampus'] = self._run(a)

        a = self._app(chosen_programme={'course_id': 'POLY-X',
                                        'course_name': 'Diploma Kejuruteraan Mekanikal'})
        self._offer(a, 'DKM - DIPLOMA KEJURUTERAAN MEKANIKAL', 'POLITEKNIK UNGKU OMAR')
        r['unlocked_course_id_pick_kept_institution_filled'] = self._run(a)

        a = self._app('shortlisted', chosen_pathway='university', chosen_programme={},
                      pre_u_track='perakaunan', pre_u_institution='KM Labuan')
        self._offer(a, LETTER_202['programme'], LETTER_202['institution'], issuer=LETTER_202['issuer'],
                    status='genuine', extra={'intake': LETTER_202['intake']})
        r['empty_pick_filled_from_letter'] = self._run(a)

        a = self._app(chosen_pathway='university', pathway_certainty='sure',
                      chosen_programme=dict(UM_PICK))
        self._offer(a, UITM_LETTER[0], UITM_LETTER[1], issuer=UITM_LETTER[2], status='genuine')
        r['bumi_only_pick_realigned'] = self._run(a)

        self.check(r)


# ── 4. the import surface: every old path keeps resolving ───────────────────────────────────

SURFACE_MODULES = {
    'apps.scholarship.contracts': contracts,
    'apps.scholarship.sponsorship': sponsorship,
    'apps.scholarship.bursary': bursary,
    'apps.scholarship.services.offer_sync': offer_sync,
}


def _defined_names(module):
    """Every top-level name the module's own source binds (def, class, assignment, and a
    ``from . import`` / ``from .x import`` of this app), with a signature for the callables."""
    tree = ast.parse(pathlib.Path(inspect.getsourcefile(module)).read_text(encoding='utf-8'))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.ImportFrom) and node.level >= 1:
            for alias in node.names:
                names.add(alias.asname or alias.name)
    out = {}
    for name in sorted(names):
        obj = getattr(module, name)
        try:
            sig = str(inspect.signature(obj)) if callable(obj) and not inspect.ismodule(obj) else ''
        except (TypeError, ValueError):
            sig = ''
        out[name] = sig
    return out


class TestGoldenSurface(_GoldenBase):
    SECTION = 'surface'

    def test_every_old_name_still_resolves_with_the_same_signature(self):
        if UPDATE:
            self.check({path: _defined_names(mod) for path, mod in SURFACE_MODULES.items()})
            return
        golden = _load().get(self.SECTION)
        self.assertIsNotNone(golden, f'{GOLDEN.name} has no "{self.SECTION}" section')
        for path, names in golden.items():
            module = SURFACE_MODULES[path]
            for name, sig in names.items():
                with self.subTest(name=f'{path}.{name}'):
                    self.assertTrue(hasattr(module, name), f'{path}.{name} no longer resolves')
                    obj = getattr(module, name)
                    if sig:
                        self.assertEqual(str(inspect.signature(obj)), sig)
