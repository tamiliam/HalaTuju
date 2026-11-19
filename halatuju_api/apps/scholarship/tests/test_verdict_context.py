"""LL4 phase 1 - the record of what fed a decision (`verdict_context`).

Pins: the record is built from at most THREE queries (the documents, and the profile and the intake
when they are not already loaded; one under the record-verdict view's own fetch); its keys at every
level are an explicit allow-list and every value is a plain int or str; no fixture PII reaches it;
the evidence fingerprint is stable for the same evidence (twice, in another row order, after a fresh
fetch, in another time zone, after the engine has run on the same instance) and moves when a
document is replaced, removed, added, re-read, or its stored status or version moves, and when any
declared field, listed profile field, intake rule or stage fact moves, but NOT when an unrelated
field (of any of the three rows) moves or the status moves inside one bucket the engine reads;
`key_check` and the fingerprint follow the secret key; the safe wrapper returns the failed record
and logs no PII. All data is made up.
"""
import datetime
import re
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.courses.models import StudentProfile
from apps.scholarship import verdict_context as vc
from apps.scholarship.model_registry import MODELS
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.factories import fake_nric, make_application, make_cohort
from apps.scholarship.verdict_engine import build_verdict

#: Made-up PII planted in the fixture. None of it may reach the record or the log.
NRIC = fake_nric()
FATHER = 'TEST FATHER A/L SAMPLE'
MOTHER = 'TEST MOTHER A/P SAMPLE'
ADDRESS = '12 JALAN CONTOH 3, TAMAN UJIAN'
INCOME = 1234.56

#: THE ALLOW-LIST, written out here on purpose (not read from the module): a key added to the
#: record fails these until it is added here too, by someone who has checked it holds no PII.
TOP_KEYS = {'schema', 'documents', 'models', 'fingerprint', 'key_check'}
DOC_KEYS = {'id', 'doc_type', 'member', 'results_kind', 'uploaded_at', 'verification',
            'read_state', 'genuineness', 'model_version', 'parser_version',
            'offer_reader_version', 'sample_check_version'}
FAILED_KEYS = {'schema', 'error'}

#: A new value for each declared field. Its keys must be exactly `DECLARED_FIELDS`, so a field
#: added to the fingerprint needs a test value here.
CHANGED_VALUES = {
    'income_route': 'salary',
    'income_earner': 'mother',
    'income_working_members': ['father', 'mother'],
    'income_declared': {'father': 999},
    'income_nonearning': {'mother': 'homemaker'},
    'other_family_members': [{'relation': 'brother', 'occupation': 'gov'}],
    'father_name': 'SOMEONE ELSE',
    'mother_name': 'SOMEONE ELSE',
    'father_occupation': 'private',
    'mother_occupation': 'private',
    'chosen_pathway': 'stpm',
    'intended_pathway': 'stpm',
    'chosen_programme': {'course': 'other'},
    'pathway_confirmed_at': datetime.datetime(2026, 2, 3, 4, 5, 6, tzinfo=datetime.timezone.utc),
    'requirements_snapshot': {'docs': ['ic']},
    'reporting_date': datetime.date(2026, 3, 1),
}

#: A new value for each listed profile field (LL4 phase 2). Its keys must be exactly
#: `PROFILE_FIELDS`, so a field added to the fingerprint needs a test value here.
CHANGED_PROFILE_VALUES = {
    'name': 'SOMEONE ELSE',
    'nric': fake_nric(),
    'exam_type': 'stpm',
    'results_exam_type': 'stpm',
    'completed_qualifications': ['spm', 'stpm'],
    'grades': {'bm': 'A'},
    'spm_prereq_grades': {'bm': 'B'},
    'stpm_grades': {'PA': 'A'},
    'stpm_cgpa': 3.5,
    'stpm_koko': 8.0,
    'higher_cgpa': 3.25,
    'higher_koko': 7.5,
    'higher_institution_type': 'ipta',
    'stream_subjects': ['physics'],
    'household_size': 9,
}
#: Profile fields the engine does not read on the verdict path: changing them must not move it.
UNLISTED_PROFILE_VALUES = {
    'school': 'SMK LAIN',
    'address': '99 JALAN LAIN',
    'postal_code': '99999',
    'contact_phone': '0100000000',
}
#: A new value for each intake rule. Its keys must be exactly `INTAKE_FIELDS`.
CHANGED_INTAKE_VALUES = {
    'year': 2031,
    'income_ceiling': 4321,
    'per_capita_ceiling': 765,
    'min_stpm_pngk': 2.75,
    'allowed_start_years': [2030, 2031],
}
#: Intake fields the engine does not read on the verdict path: changing them must not move it.
UNLISTED_INTAKE_VALUES = {
    'name': 'Another Made-up Intake',
    'is_active': False,
    'allowed_birth_states': ['14'],
}
#: Two instants in the same Malaysian year (a resubmission re-stamps), and one in the next.
SUBMIT_A = datetime.datetime(2026, 3, 1, 2, 0, tzinfo=datetime.timezone.utc)
SUBMIT_B = datetime.datetime(2026, 9, 9, 9, 0, tzinfo=datetime.timezone.utc)
SUBMIT_NEXT_YEAR = datetime.datetime(2026, 12, 31, 17, 0, tzinfo=datetime.timezone.utc)  # 1 Jan MYT


def _vision(status='genuine', model_version='1.2.0', parser_version='spm_slip 1.1.0', name=FATHER):
    return {'fields': {'name': name, 'nric': NRIC, 'address': ADDRESS, 'income': INCOME},
            'authenticity': {'status': status, 'model_version': model_version},
            'parser_version': parser_version}


class _Base(TestCase):
    def setUp(self):
        self.app = make_application(
            'submitted', income_route='str', income_earner='father', father_name=FATHER,
            mother_name=MOTHER, income_declared={'father': INCOME}, father_occupation='gov',
            mother_occupation='homemaker', chosen_pathway='diploma')
        self.ic = self._doc('ic', vision_nric=NRIC, vision_name=FATHER, vision_address=ADDRESS,
                            vision_fields=_vision())
        self.slip = self._doc('salary_slip', household_member='father', vision_fields=_vision())

    def _doc(self, doc_type, **kw):
        kw.setdefault('storage_path', f'org/app/{doc_type}/{NRIC}.pdf')
        kw.setdefault('original_filename', f'{FATHER}.pdf')
        return ApplicantDocument.objects.create(application=self.app, doc_type=doc_type, **kw)

    def _fp(self, app=None):
        return vc.build_verdict_context(app or self.app)['fingerprint']

    def _stage(self, status, submitted_at):
        """Set the two stage columns in memory (status, submission stamp)."""
        self.app.status, self.app.profile_completed_at = status, submitted_at


class TestTheRecord(_Base):
    def test_the_record_is_built(self):
        record = vc.build_verdict_context(self.app)
        self.assertEqual(record['schema'], 1)
        self.assertEqual([d['id'] for d in record['documents']], sorted([self.ic.id, self.slip.id]))
        slip = next(d for d in record['documents'] if d['id'] == self.slip.id)
        self.assertEqual((slip['doc_type'], slip['member'], slip['genuineness']),
                         ('salary_slip', 'father', 'genuine'))
        self.assertEqual((slip['model_version'], slip['parser_version']), ('1.2.0', 'spm_slip 1.1.0'))
        self.assertEqual(set(record['models']), set(MODELS))
        self.assertTrue(all(record['models'].values()), record['models'])
        self.assertNotIn(vc.NOT_A_CODE, record['models'].values())
        self.assertRegex(record['fingerprint'], r'^[0-9a-f]{64}$')
        self.assertRegex(record['key_check'], r'^[0-9a-f]{8}$')

    def test_the_record_holds_every_live_document_and_no_superseded_one(self):
        self.slip.superseded_at = timezone.now()
        self.slip.save()
        ids = [d['id'] for d in vc.build_verdict_context(self.app)['documents']]
        self.assertEqual(ids, [self.ic.id])

    def test_the_documents_the_profile_and_the_intake_cost_three_queries(self):
        """A fresh application: one query each for the documents, its profile and its intake."""
        app = ScholarshipApplication.objects.get(pk=self.app.pk)
        with self.assertNumQueries(3):
            vc.build_verdict_context(app)

    def test_a_loaded_profile_costs_no_extra_query(self):
        app = ScholarshipApplication.objects.select_related('profile').get(pk=self.app.pk)
        with self.assertNumQueries(2):
            vc.build_verdict_context(app)

    def test_under_the_record_verdict_fetch_it_costs_one_query(self):
        """The record-verdict view loads the profile and the intake with the case
        (`views_admin/base.py`): only the documents are left to read."""
        app = ScholarshipApplication.objects.select_related('profile', 'cohort').get(pk=self.app.pk)
        with self.assertNumQueries(1):
            vc.build_verdict_context(app)

    def test_every_declared_and_stage_field_is_a_column_of_the_application(self):
        columns = {f.name for f in ScholarshipApplication._meta.concrete_fields}
        self.assertEqual(
            sorted(set(vc.DECLARED_FIELDS + vc.STAGE_FIELDS + (vc.NOTES_FIELD,)) - columns), [])

    def test_every_intake_field_is_a_column_of_the_intake(self):
        columns = {f.name for f in ScholarshipCohort._meta.concrete_fields}
        self.assertEqual(sorted(set(vc.INTAKE_FIELDS) - columns), [])

    def test_every_profile_field_is_a_column_of_the_profile(self):
        columns = {f.name for f in StudentProfile._meta.concrete_fields}
        self.assertEqual(sorted(set(vc.PROFILE_FIELDS) - columns), [])

    def test_an_application_without_a_profile_still_builds(self):
        self.app.profile = None
        record = vc.build_verdict_context(self.app)
        self.assertEqual(set(record), TOP_KEYS)

    def test_an_application_without_an_intake_still_builds(self):
        self.app.cohort = None
        record = vc.build_verdict_context(self.app)
        self.assertEqual(set(record), TOP_KEYS)


class TestTheAllowList(_Base):
    def _leaves(self, value, path='record'):
        if isinstance(value, dict):
            for k, v in value.items():
                self.assertIsInstance(k, str, path)
                yield from self._leaves(v, f'{path}.{k}')
        elif isinstance(value, list):
            for i, v in enumerate(value):
                yield from self._leaves(v, f'{path}[{i}]')
        else:
            yield path, value

    def test_the_keys_at_every_level_are_the_pinned_set(self):
        record = vc.build_verdict_context(self.app)
        self.assertEqual(set(record), TOP_KEYS)
        self.assertEqual(set(record['models']), set(MODELS))
        for doc in record['documents']:
            self.assertEqual(set(doc), DOC_KEYS)

    def test_every_value_is_a_plain_int_or_str(self):
        for path, value in self._leaves(vc.build_verdict_context(self.app)):
            self.assertTrue(type(value) in (int, str), f'{path} is {type(value).__name__}')

    def test_no_fixture_pii_reaches_the_record(self):
        text = vc.canonical_json(vc.build_verdict_context(self.app))
        for secret in (NRIC, FATHER, MOTHER, ADDRESS, str(INCOME), 'org/app', '.pdf'):
            self.assertNotIn(secret, text)

    def test_no_profile_value_reaches_the_record(self):
        """The profile fields are hashed only: none of their values is written out."""
        profile = self.app.profile
        profile.grades = {'bm': 'A+'}
        profile.stream_subjects = ['made_up_subject_xyz']
        profile.save()
        text = vc.canonical_json(vc.build_verdict_context(self.app))
        for secret in (profile.nric, re.sub(r'\D', '', profile.nric), profile.name,
                       'made_up_subject_xyz', 'A+'):
            self.assertNotIn(secret, text)

    def test_no_intake_or_stage_value_reaches_the_record(self):
        """The intake rules and the stage facts are hashed only: when every one of them moves, the
        record moves in its fingerprint and nowhere else."""
        before = vc.build_verdict_context(self.app)
        for name, value in CHANGED_INTAKE_VALUES.items():
            setattr(self.app.cohort, name, value)
        self.app.profile_completed_at, self.app.status = SUBMIT_A, 'recommended'
        after = vc.build_verdict_context(self.app)
        self.assertNotEqual(after.pop('fingerprint'), before.pop('fingerprint'))
        self.assertEqual(after, before)

    def test_no_results_note_text_reaches_the_record(self):
        """The notes are read for one derived fact, hashed only: no note text, kind or id list is
        written out."""
        self.app.results_change_notes = [
            {'kind': 'refiled_higher', 'document_id': self.slip.id, 'by': 'team',
             'note': 'made_up_note_text_xyz'}]
        text = vc.canonical_json(vc.build_verdict_context(self.app))
        for secret in ('made_up_note_text_xyz', 'refiled_higher', vc.MOVED_TO_HIGHER):
            self.assertNotIn(secret, text)

    def test_the_failed_record_has_its_own_pinned_keys(self):
        self.assertEqual(set(vc.failed_record(vc.BUILD_FAILED)), FAILED_KEYS)

    def test_a_status_or_version_that_is_not_a_code_is_masked(self):
        self.ic.vision_fields = _vision(status=FATHER, model_version=FATHER, parser_version=MOTHER)
        self.ic.save()
        doc = next(d for d in vc.build_verdict_context(self.app)['documents'] if d['id'] == self.ic.id)
        self.assertEqual((doc['genuineness'], doc['model_version'], doc['parser_version']),
                         (vc.NOT_A_CODE,) * 3)


class TestTheFingerprintHolds(_Base):
    def test_same_evidence_same_fingerprint(self):
        self.assertEqual(self._fp(), self._fp())

    def _parts(self):
        return (vc.declared_values(self.app), vc.profile_values(self.app),
                vc.intake_values(self.app), vc.stage_facts(self.app))

    def test_the_row_order_does_not_count(self):
        rows = vc._live_document_rows(self.app)
        declared, profile, intake, stage = self._parts()
        self.assertEqual(vc.evidence_fingerprint(rows, declared, profile, intake, stage),
                         vc.evidence_fingerprint(list(reversed(rows)), declared, profile, intake,
                                                 stage))

    def test_a_fresh_fetch_gives_the_same_fingerprint(self):
        self.assertEqual(self._fp(), self._fp(ScholarshipApplication.objects.get(pk=self.app.pk)))

    def test_the_time_zone_of_an_instant_does_not_count(self):
        utc = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
        myt = utc.astimezone(datetime.timezone(datetime.timedelta(hours=8)))
        rows = vc._live_document_rows(self.app)
        declared, profile, intake, stage = self._parts()
        a = vc.evidence_fingerprint(rows, dict(declared, pathway_confirmed_at=utc), profile,
                                    intake, stage)
        b = vc.evidence_fingerprint(rows, dict(declared, pathway_confirmed_at=myt), profile,
                                    intake, stage)
        self.assertEqual(a, b)

    def test_running_the_engine_first_does_not_move_it(self):
        """The view runs `build_verdict` on the same instance before it builds the record. The
        engine writes only private memos on it, never a hashed field: the fingerprint after the
        run equals the one before it and the one of a fresh fetch of the stored row."""
        before = self._fp()
        build_verdict(self.app)
        self.assertEqual(self._fp(), before)
        self.assertEqual(self._fp(ScholarshipApplication.objects.get(pk=self.app.pk)), before)

    def test_an_unrelated_field_does_not_move_it(self):
        before = self._fp()
        self.app.verdict_reason = 'a reason'
        self.app.officer_verdict = {'identity': 'pass'}
        self.app.ai_verdict_snapshot = [{'fact': 'identity'}]
        self.app.ai_verdict_context = {'schema': 1, 'error': 'build_failed'}
        self.assertEqual(self._fp(), before)

    def test_an_unlisted_profile_field_does_not_move_it(self):
        self.assertFalse(set(UNLISTED_PROFILE_VALUES) & set(vc.PROFILE_FIELDS))
        before = self._fp()
        for name, value in UNLISTED_PROFILE_VALUES.items():
            setattr(self.app.profile, name, value)
        self.assertEqual(self._fp(), before)

    def test_an_unlisted_intake_field_does_not_move_it(self):
        self.assertFalse(set(UNLISTED_INTAKE_VALUES) & set(vc.INTAKE_FIELDS))
        before = self._fp()
        for name, value in UNLISTED_INTAKE_VALUES.items():
            self.assertNotEqual(getattr(self.app.cohort, name), value)
            setattr(self.app.cohort, name, value)
        self.assertEqual(self._fp(), before)

    def test_a_resubmission_in_the_same_year_does_not_move_it(self):
        """The engine reads the submission stamp only for being there and for its Malaysian year
        (`str_route.str_this_year`): a re-stamp inside the year is not new evidence."""
        self._stage('interviewing', SUBMIT_A)
        before = self._fp()
        self._stage('interviewing', SUBMIT_B)
        self.assertEqual(self._fp(), before)

    def test_a_status_move_inside_one_bucket_does_not_move_it(self):
        """Moves that happen at or after the decision without changing any fact the engine
        reads: verify-accept / submit-decline (interviewing -> interviewed), and the student's
        confirmation once stamped (shortlisted -> profile_complete with the stamp)."""
        for old, new, stamp in (('interviewing', 'interviewed', SUBMIT_A),
                                ('shortlisted', 'profile_complete', SUBMIT_A),
                                ('recommended', 'rejected', SUBMIT_A)):
            with self.subTest(old=old, new=new):
                self._stage(old, stamp)
                before = self._fp()
                self._stage(new, stamp)
                self.assertEqual(self._fp(), before)

    def test_the_stored_order_of_the_start_years_does_not_count(self):
        """The engine reads the years through `start_year.stored_years`, which sorts them and drops
        a repeat: another stored order of the same years is the same evidence."""
        self.app.cohort.allowed_start_years = [2025, 2026]
        before = self._fp()
        for same in ([2026, 2025], [2026, 2025, 2026]):
            with self.subTest(years=same):
                self.app.cohort.allowed_start_years = same
                self.assertEqual(self._fp(), before)

    def test_results_notes_the_engine_ignores_do_not_move_it(self):
        """The engine reads only which documents a `refiled_higher` note names
        (`wrong_slip._moved_here`). Other notes, other keys, a repeat and an id it can never
        match do not count."""
        moved = {'kind': 'refiled_higher', 'document_id': self.slip.id, 'by': 'team',
                 'at': '2026-03-01T10:00:00+08:00', 'submitted': False}
        self.app.results_change_notes = [moved]
        before = self._fp()
        for notes in (
                [dict(moved, at='2026-04-01T10:00:00+08:00', submitted=True, by='student')],
                [moved, moved],
                [moved, {'kind': 'refiled_spm', 'document_id': self.ic.id, 'note': 'made-up text'}],
                [moved, {'kind': 'team_split', 'note': 'made-up text'}],
                [moved, {'kind': 'refiled_higher', 'document_id': str(self.ic.id)}],
                [moved, 'not a note']):
            with self.subTest(notes=notes):
                self.app.results_change_notes = notes
                self.assertEqual(self._fp(), before)

    @override_settings(SECRET_KEY='made-up-key-for-the-pinned-fingerprint-0000000000')
    def test_the_canonical_form_is_pinned(self):
        """A fixed input under a fixed key gives a fixed answer: any change to the canonical form
        (key names, ordering, instant format) shows here, before it splits old and new records."""
        row = {c: '' for c in vc._DOC_COLUMNS}
        row.update(id=7, doc_type='ic', vision_fields={'authenticity': {'status': 'genuine'}},
                   uploaded_at=datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
                   vision_fields_run_at=None, vision_run_at=None)
        declared = dict({name: None for name in vc.DECLARED_FIELDS}, **{vc.MOVED_TO_HIGHER: []})
        profile = {name: None for name in vc.PROFILE_FIELDS}
        intake = dict({name: None for name in vc.INTAKE_FIELDS}, cohort_id=None)
        stage = {'submitted_year': 2026, 'pre_submit_status': None, 'in_review_status': True,
                 'decided_status': False}
        self.assertEqual(set(declared), set(vc.declared_values(self.app)))
        self.assertEqual(set(intake), set(vc.intake_values(self.app)))
        self.assertEqual(set(stage), set(vc.stage_facts(self.app)))
        self.assertEqual(vc.key_check(), PINNED_KEY_CHECK)
        self.assertEqual(vc.evidence_fingerprint([row], declared, profile, intake, stage),
                         PINNED_FINGERPRINT)


PINNED_KEY_CHECK = 'cad1960c'
#: Re-pinned in LL4 phase 2 when the profile values joined the payload, and again in the LL4 review
#: round when the intake rules and the stage facts joined it, and again in review round 2 when the
#: moved-to-higher fact (from the results notes) joined the declared values. The pin is new in
#: branch ll4: no stored fingerprint was ever computed under any earlier form.
PINNED_FINGERPRINT = '39e586e15d9d3012574ddded20683c6d5ac646c264d3cdab5b2bc5ec770fe63a'


class TestTheFingerprintMoves(_Base):
    def _moved(self, change):
        before = self._fp()
        change()
        self.assertNotEqual(self._fp(), before)

    def test_a_replaced_document(self):
        """The same slot, the same stored read and versions: only the document (its id and upload
        time) is new, and that alone moves the fingerprint."""
        def replace():
            self.slip.superseded_at = timezone.now()
            self.slip.save()
            self._doc('salary_slip', household_member='father', vision_fields=_vision())
        self._moved(replace)

    def test_a_removed_document(self):
        self._moved(self.slip.delete)

    def test_an_added_document(self):
        self._moved(lambda: self._doc('offer_letter', vision_fields=_vision()))

    def _set(self, doc, **kw):
        for k, v in kw.items():
            setattr(doc, k, v)
        doc.save()

    def test_a_stored_status(self):
        self._moved(lambda: self._set(self.slip, vision_fields=_vision(status='suspect')))

    def test_a_stored_model_version(self):
        self._moved(lambda: self._set(self.slip, vision_fields=_vision(model_version='1.3.0')))

    def test_a_stored_parser_version(self):
        self._moved(lambda: self._set(self.slip, vision_fields=_vision(parser_version='spm_slip 1.2.0')))

    def test_a_re_read_under_the_same_versions(self):
        self._moved(lambda: self._set(self.slip, vision_fields=_vision(name=MOTHER)))

    def test_an_officer_verification(self):
        self._moved(lambda: self._set(self.ic, verification_status='verified'))

    def test_every_declared_field(self):
        self.assertEqual(set(CHANGED_VALUES), set(vc.DECLARED_FIELDS))
        for name, value in CHANGED_VALUES.items():
            with self.subTest(field=name):
                before = self._fp()
                old = getattr(self.app, name)
                setattr(self.app, name, value)
                self.assertNotEqual(self._fp(), before)
                setattr(self.app, name, old)

    def test_every_listed_profile_field(self):
        self.assertEqual(set(CHANGED_PROFILE_VALUES), set(vc.PROFILE_FIELDS))
        profile = self.app.profile
        for name, value in CHANGED_PROFILE_VALUES.items():
            with self.subTest(field=name):
                before = self._fp()
                old = getattr(profile, name)
                self.assertNotEqual(old, value)
                setattr(profile, name, value)
                self.assertNotEqual(self._fp(), before)
                setattr(profile, name, old)

    def test_every_intake_rule(self):
        self.assertEqual(set(CHANGED_INTAKE_VALUES), set(vc.INTAKE_FIELDS))
        cohort = self.app.cohort
        for name, value in CHANGED_INTAKE_VALUES.items():
            with self.subTest(field=name):
                before = self._fp()
                old = getattr(cohort, name)
                self.assertNotEqual(old, value)
                setattr(cohort, name, value)
                self.assertNotEqual(self._fp(), before)
                setattr(cohort, name, old)

    def test_another_set_of_start_years(self):
        self.app.cohort.allowed_start_years = [2025, 2026]
        self._moved(lambda: setattr(self.app.cohort, 'allowed_start_years', [2025, 2027]))

    def test_a_start_year_list_of_junk_is_not_an_empty_one(self):
        """An entry that is not a year is dropped from the reading but keeps the rule ON
        (`start_year.rule_on`): it accepts nobody, so it is not the same as no rule."""
        self.app.cohort.allowed_start_years = []
        self._moved(lambda: setattr(self.app.cohort, 'allowed_start_years', ['not a year']))

    def test_a_document_moved_to_higher_results(self):
        """The engine counts a not-yet-read higher-results upload as STPM only when a
        `refiled_higher` note names it (`wrong_slip._moved_here`)."""
        self._moved(lambda: setattr(self.app, 'results_change_notes', [
            {'kind': 'refiled_higher', 'document_id': self.slip.id, 'submitted': False}]))

    def test_a_move_note_naming_another_document(self):
        self.app.results_change_notes = [{'kind': 'refiled_higher', 'document_id': self.slip.id}]
        self._moved(lambda: setattr(self.app, 'results_change_notes', [
            {'kind': 'refiled_higher', 'document_id': self.ic.id}]))

    def test_another_intake(self):
        """The same rules under another intake still move it: the case was judged in that one."""
        other = make_cohort(**{name: getattr(self.app.cohort, name) for name in vc.INTAKE_FIELDS})
        self._moved(lambda: setattr(self.app, 'cohort', other))

    def test_a_submission_in_another_year(self):
        self._stage('interviewing', SUBMIT_A)
        self._moved(lambda: self._stage('interviewing', SUBMIT_NEXT_YEAR))

    def test_a_submission(self):
        self._stage('shortlisted', None)
        self._moved(lambda: self._stage('profile_complete', SUBMIT_A))

    def test_an_unstamped_case_leaving_the_pre_submit_statuses(self):
        """No stamp: `str_this_year` reads the intake year once the status is past shortlisted."""
        self._stage('shortlisted', None)
        self._moved(lambda: self._stage('interviewing', None))

    def test_a_case_being_decided(self):
        """QC accept: the engine reads the decided statuses (`higher_owed._too_late`) and the
        in-review ones (`amounts._to_myr`), so this one moves it. LL5 replays under the stage as
        at the decision (`evidence_fingerprint` takes the stage as an argument)."""
        self._stage('interviewing', SUBMIT_A)
        self._moved(lambda: self._stage('recommended', SUBMIT_A))


class TestTheKey(_Base):
    def test_the_key_check_and_the_fingerprint_follow_the_secret_key(self):
        with override_settings(SECRET_KEY='made-up-key-one-000000000000000000000000000000'):
            a = vc.build_verdict_context(self.app)
        with override_settings(SECRET_KEY='made-up-key-two-000000000000000000000000000000'):
            b = vc.build_verdict_context(self.app)
        self.assertNotEqual(a['key_check'], b['key_check'])
        self.assertNotEqual(a['fingerprint'], b['fingerprint'])

    def test_the_same_key_gives_the_same_key_check(self):
        self.assertEqual(vc.key_check(), vc.key_check())


class TestTheSafeWrapper(_Base):
    def test_a_failure_returns_the_failed_record_and_logs_no_pii(self):
        boom = ValueError(f'could not read {NRIC} for {FATHER}')
        with mock.patch.object(vc, '_live_document_rows', side_effect=boom):
            with self.assertLogs('apps.scholarship.verdict_context', level='WARNING') as logs:
                record = vc.verdict_context_or_empty(self.app)
        self.assertEqual(record, {'schema': 1, 'error': vc.BUILD_FAILED})
        text = '\n'.join(logs.output)
        self.assertEqual(len(logs.output), 1)
        self.assertIn('ValueError', text)
        self.assertIn(str(self.app.pk), text)
        for secret in (NRIC, FATHER, re.sub(r'\D', '', NRIC)):
            self.assertNotIn(secret, text)

    def test_a_value_with_no_canonical_form_fails_safely(self):
        self.app.income_declared = {'father': object()}
        with self.assertLogs('apps.scholarship.verdict_context', level='WARNING') as logs:
            record = vc.verdict_context_or_empty(self.app)
        self.assertEqual(record['error'], vc.BUILD_FAILED)
        self.assertIn('TypeError', logs.output[0])

    def test_an_unsaved_application_returns_the_failed_record(self):
        self.assertEqual(vc.verdict_context_or_empty(ScholarshipApplication()),
                         {'schema': 1, 'error': vc.NO_APPLICATION})

    def test_a_good_build_passes_through(self):
        self.assertEqual(vc.verdict_context_or_empty(self.app), vc.build_verdict_context(self.app))
