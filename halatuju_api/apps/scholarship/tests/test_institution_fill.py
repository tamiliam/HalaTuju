"""``chosen_programme.institution`` is a MUST-FILL fact — owner 2026-07-25, off #48.

Sprint 1 of `docs/plans/2026-07-25-institution-must-fill-roadmap.md`. Two units:

* ``offer_pathway.sole_catalogue_institution`` — the hint-less catalogue answer, allowed only when
  the course has exactly one campus.
* ``services.sync_institution_from_catalogue`` — the institution's OWN writer, called from
  ``autofill_pathway_from_offer`` ABOVE every pathway guard.

Guard coverage here is deliberate. `docs/lessons.md` #11 records that the identical reporting-date
bug survived because a test pinned the LOCK guard and nobody checked the four guards above it — so
every exit of ``autofill_pathway_from_offer`` gets its own assertion below.
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import (
    Course, CourseInstitution, FieldTaxonomy, Institution, StudentProfile,
)
from apps.scholarship import offer_pathway as op
from apps.scholarship.models import (
    ApplicantDocument, ScholarshipApplication, ScholarshipCohort,
)
from apps.scholarship.services import (
    autofill_pathway_from_offer, sync_institution_from_catalogue,
)


class _Base(TestCase):
    """Fixtures.

    Course ids here are SYNTHETIC (`TST-…`) on purpose: migrations 0017/0018 already seed the
    pre-U virtual courses + the 15 Kolej Matrikulasi into every test DB, and the field taxonomy is
    seeded too, so creating real ids would collide. The one exception is the MATRIC test, which
    deliberately uses the seeded `matric-perakaunan` → `KM Selangor` link — that is the real path
    the code walks, and asserting against invented rows would prove nothing.
    """

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='inst', name='B40', year=2026)
        cls.ft, _ = FieldTaxonomy.objects.get_or_create(
            key='multimedia',
            defaults={'name_en': 'Multimedia', 'name_ms': 'Multimedia',
                      'name_ta': 'மல்டிமீடியா', 'image_slug': 'multimedia'})

    _seq = 0

    def _app(self, **over):
        _Base._seq += 1
        prof = StudentProfile.objects.create(
            supabase_user_id=f'inst-{self.id()}-{_Base._seq}',
            name=over.pop('name', 'LAKSMITHA A/P VIJAYAN'),
            nric=over.pop('nric', '080725-04-0054'))
        defaults = dict(cohort=self.cohort, profile=prof, status='profile_complete',
                        chosen_pathway='', pre_u_institution='', pre_u_track='',
                        pathway_certainty='uncertain', chosen_programme={})
        defaults.update(over)
        return ScholarshipApplication.objects.create(**defaults)

    def _offer(self, app, programme, institution, *, name=None, nric=None):
        prof = app.profile
        return ApplicantDocument.objects.create(
            application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
            vision_fields={'fields': {
                'candidate_name': name if name is not None else prof.name,
                'candidate_nric': (nric if nric is not None else prof.nric).replace('-', ''),
                'programme': programme, 'institution': institution},
                'student_verdict': 'ok', 'warnings': [], 'error': ''},
            vision_run_at=timezone.now())

    def _course(self, cid, name, *campuses, level='Diploma', inst_type='Universiti'):
        c, _ = Course.objects.get_or_create(
            course_id=cid,
            defaults={'course': name, 'level': level, 'department': 'x', 'field': 'x',
                      'field_key': self.ft})
        for inst_name, inst_id, *acr in campuses:
            inst, _ = Institution.objects.get_or_create(
                institution_id=inst_id,
                defaults={'institution_name': inst_name, 'type': inst_type, 'state': 'Johor',
                          'acronym': (acr[0] if acr else '')})
            CourseInstitution.objects.get_or_create(course=c, institution=inst)
        return c

    def _multi(self, app):
        """Re-point an app at a two-campus poly course."""
        self._course('TST-POLY', 'Diploma Kejuruteraan Awam',
                     ('Politeknik Kota Bharu', 'pkb'), ('Politeknik Mersing', 'pm'),
                     inst_type='Politeknik')
        app.chosen_pathway = 'poly'
        app.chosen_programme = {'course_id': 'TST-POLY',
                                'course_name': 'Diploma Kejuruteraan Awam'}
        app.save(update_fields=['chosen_pathway', 'chosen_programme'])
        return app


class TestSoleCatalogueInstitution(_Base):
    """The hint-less answer — strictly ``count == 1``."""

    def test_one_campus_answers_without_a_hint(self):
        self._course('TST-ANIM', 'Diploma Teknologi Animasi',
                     ('Universiti Tun Hussein Onn Malaysia', 'uthm', 'UTHM'))
        self.assertEqual(op.sole_catalogue_institution('TST-ANIM'),
                         'Universiti Tun Hussein Onn Malaysia')

    def test_two_campuses_abstain(self):
        # A multi-campus course must come from the offer letter, never a guess (lessons #378 —
        # a fuzzy match over a near-duplicate name set silently picks the wrong row).
        self._course('TST-POLY', 'Diploma Kejuruteraan Awam',
                     ('Politeknik Kota Bharu', 'pkb'), ('Politeknik Mersing', 'pm'),
                     inst_type='Politeknik')
        self.assertEqual(op.sole_catalogue_institution('TST-POLY'), '')

    def test_no_catalogue_rows_abstain(self):
        # The #132 / #136 catalogue gap — fixed in the catalogue, never invented here.
        self._course('TST-LAW', 'Sarjana Muda Undang-Undang', level='Ijazah Sarjana Muda')
        self.assertEqual(op.sole_catalogue_institution('TST-LAW'), '')

    def test_blank_course_id_abstains(self):
        self.assertEqual(op.sole_catalogue_institution(''), '')
        self.assertEqual(op.sole_catalogue_institution(None), '')


class TestSyncInstitutionFromCatalogue(_Base):
    def setUp(self):
        self._course('TST-ANIM', 'Diploma Teknologi Animasi',
                     ('Universiti Tun Hussein Onn Malaysia', 'uthm', 'UTHM'))

    def _picked(self, **over):
        """A student's own apply-form pick: course_id + name, NO institution, NO source — the
        shape every one of the 24 live blanks actually has."""
        return self._app(chosen_pathway='university', chosen_programme={
            'course_id': 'TST-ANIM', 'course_name': 'Diploma Teknologi Animasi',
            'field_key': 'multimedia'}, **over)

    # ── the sole-campus fill ──────────────────────────────────────────────────

    def test_fills_a_sole_campus_course_with_no_offer_at_all(self):
        app = self._picked()
        self.assertTrue(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_touches_only_the_institution_sub_key(self):
        # Nothing may be re-attributed to a letter: no `source` appears, the pick survives.
        app = self._picked()
        sync_institution_from_catalogue(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['course_id'], 'TST-ANIM')
        self.assertEqual(app.chosen_programme['course_name'], 'Diploma Teknologi Animasi')
        self.assertNotIn('source', app.chosen_programme)

    def test_never_overwrites_a_recorded_institution(self):
        app = self._picked()
        app.chosen_programme = {**app.chosen_programme, 'institution': 'UTHM Pagoh'}
        app.save(update_fields=['chosen_programme'])
        self.assertFalse(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'UTHM Pagoh')

    def test_is_idempotent(self):
        app = self._picked()
        self.assertTrue(sync_institution_from_catalogue(app))
        self.assertFalse(sync_institution_from_catalogue(app))

    # ── the offer as a campus hint (multi-campus only) ────────────────────────

    def test_multi_campus_fills_from_the_students_own_offer(self):
        app = self._multi(self._app())
        self._offer(app, 'DIPLOMA KEJURUTERAAN AWAM', 'POLITEKNIK MERSING')
        self.assertTrue(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'Politeknik Mersing')

    def test_multi_campus_ignores_a_wrong_person_letter(self):
        # A letter that isn't this student's may never name their campus — even though the
        # sole-campus path is happy to answer with no letter at all.
        app = self._multi(self._app())
        self._offer(app, 'DIPLOMA KEJURUTERAAN AWAM', 'POLITEKNIK MERSING',
                    name='SOMEONE ELSE BINTI OTHER')
        self.assertFalse(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('institution', ''), '')

    def test_multi_campus_refuses_an_institution_that_is_not_a_campus_of_the_course(self):
        # The clash class (#11 / #64 / #86 / #113 / #93): a private college on the letter against a
        # declared public course. The catalogue refuses; a human decides.
        app = self._multi(self._app())
        self._offer(app, 'DIPLOMA KEJURUTERAAN AWAM', 'UNIVERSITY OF CYBERJAYA')
        self.assertFalse(sync_institution_from_catalogue(app))

    def test_zero_catalogue_rows_stays_blank_even_with_a_clean_offer(self):
        self._course('TST-LAW', 'Sarjana Muda Undang-Undang', level='Ijazah Sarjana Muda')
        app = self._app(chosen_programme={'course_id': 'TST-LAW',
                                          'course_name': 'Sarjana Muda Undang-Undang'})
        self._offer(app, 'SARJANA MUDA UNDANG-UNDANG', 'Universiti Utara Malaysia')
        self.assertFalse(sync_institution_from_catalogue(app))

    # ── pre-U ─────────────────────────────────────────────────────────────────

    def test_matric_resolves_the_catalogue_college_from_the_declared_state(self):
        # No fixtures created: migration 0018 already links KM Selangor to matric-perakaunan.
        app = self._app(chosen_pathway='matric', pre_u_track='perakaunan',
                        pre_u_institution='KM Selangor')
        self.assertTrue(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'], 'KM Selangor')

    def test_stpm_is_deliberately_not_resolved(self):
        # ~250 near-identical school names make a catalogue match unsafe (lessons #378), and
        # copying the student's declared school into chosen_programme would attribute their own
        # answer to the offer letter (the #117(d) guard). A human fills it — Sprint 2's entry box.
        app = self._app(chosen_pathway='stpm', pre_u_track='sains',
                        pre_u_institution='SMK DATUK MANSOR')
        self.assertFalse(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('institution', ''), '')


    # ── the letter-vs-declaration contradiction stop ───────────────────────────

    def test_an_acronym_on_the_letter_is_not_a_contradiction(self):
        """#48's own letter reads "UTHM - KAMPUS (CAWANGAN PAGOH)" — no distinctive token in common
        with "Universiti Tun Hussein Onn Malaysia". Matching on the catalogue ACRONYM is what keeps
        the sole-campus fill working on the very case it exists for."""
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UTHM - KAMPUS (CAWANGAN PAGOH)')
        self.assertTrue(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_abstains_when_the_letter_names_a_different_institution(self):
        # The #11/#64/#86/#113/#93 shape: a private/other place on the letter against a declared
        # public course. The catalogue's answer would be consistent with the DECLARATION and wrong
        # about the STUDENT — on a sponsor-facing field. A human decides.
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UNIVERSITY OF CYBERJAYA')
        self.assertFalse(sync_institution_from_catalogue(app))
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('institution', ''), '')

    def test_junk_in_the_institution_slot_never_reads_as_a_contradiction(self):
        # A leaked clause number is not a place (#47) — it must not block the catalogue fill.
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', '2.5.')
        self.assertTrue(sync_institution_from_catalogue(app))

    def test_a_wrong_person_letter_cannot_contradict_either(self):
        # It is not this student's letter, so it carries no information about where THEY study —
        # neither to fill from nor to object with.
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UNIVERSITY OF CYBERJAYA',
                    name='SOMEONE ELSE BINTI OTHER')
        self.assertTrue(sync_institution_from_catalogue(app))

    # ── every guard in autofill_pathway_from_offer is now BELOW the write ─────

    def test_autofill_fills_it_past_the_wrong_person_name_guard(self):
        """#48 exactly: the offer OCR doubled a letter ("LAKSMITHAA"), autofill returned at the
        wrong-person guard, and the institution was lost while the already-hoisted reporting date
        landed — a ticked date beside an empty Institution."""
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UTHM - KAMPUS (CAWANGAN PAGOH)',
                    name='SOMEONE ELSE BINTI OTHER')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_autofill_fills_it_past_the_wrong_person_ic_guard(self):
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UTHM', nric='999999-99-9999')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_autofill_fills_it_past_the_nothing_readable_guard(self):
        app = self._picked()
        self._offer(app, '', '')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_autofill_fills_it_past_the_clause_number_guard(self):
        # A leaked section header ("2.4." / "2.5.", #47) clears both slots → the old code returned.
        app = self._picked()
        self._offer(app, '2.4.', '2.5.')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_autofill_fills_it_past_the_pathway_mismatch_guard(self):
        # A PROGRAMME clash at the same university: the pathway reads 'mismatch' (the confirm
        # query's job) but the letter and the declared course agree about WHERE, so the institution
        # must still land. The old code returned at this guard and lost it.
        app = self._picked(pathway_certainty='sure')
        self._offer(app, 'DIPLOMA KEJURUTERAAN MEKANIKAL', 'UTHM')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')
        self.assertEqual(app.chosen_programme['course_id'], 'TST-ANIM')   # pick untouched

    def test_autofill_fills_it_for_a_locked_pick(self):
        # The lock guard the reporting-date fix already pinned — asserted here for the institution
        # too, so the pair can't drift apart again.
        app = self._picked(pathway_certainty='sure')
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UTHM')
        autofill_pathway_from_offer(app)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_autofill_returns_true_when_only_the_institution_landed(self):
        # backfill_offer_pathways counts this return value — moving the write out of the tail must
        # not turn a real update into a reported no-op (the lessons-#11 corollary).
        app = self._picked()
        self._offer(app, 'DIPLOMA TEKNOLOGI ANIMASI', 'UTHM',
                    name='SOMEONE ELSE BINTI OTHER')
        self.assertTrue(autofill_pathway_from_offer(app))


class TestBackfillInstitutionCommand(_Base):
    """``backfill_institution`` — read-only by default, and it must NAME what it cannot fill.

    A "N still blank" number with no list is a dead end (lessons #321): the whole point of the
    by-cause grouping is that a catalogue gap and a genuine clash need different human actions.
    """

    def _run(self, *args):
        out = StringIO()
        call_command('backfill_institution', *args, stdout=out)
        return out.getvalue()

    def test_reports_without_writing_by_default(self):
        self._course('TST-ANIM', 'Diploma Teknologi Animasi',
                     ('Universiti Tun Hussein Onn Malaysia', 'uthm', 'UTHM'))
        app = self._app(chosen_pathway='university', chosen_programme={
            'course_id': 'TST-ANIM', 'course_name': 'Diploma Teknologi Animasi'})
        out = self._run()
        self.assertIn('FILLED (1)', out)
        self.assertIn(f'#{app.pk}', out)
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme.get('institution', ''), '')   # nothing written

    def test_apply_persists_the_resolvable_ones(self):
        self._course('TST-ANIM', 'Diploma Teknologi Animasi',
                     ('Universiti Tun Hussein Onn Malaysia', 'uthm', 'UTHM'))
        app = self._app(chosen_pathway='university', chosen_programme={
            'course_id': 'TST-ANIM', 'course_name': 'Diploma Teknologi Animasi'})
        self._run('--apply')
        app.refresh_from_db()
        self.assertEqual(app.chosen_programme['institution'],
                         'Universiti Tun Hussein Onn Malaysia')

    def test_groups_the_causes_a_human_must_act_on(self):
        # One of each: a catalogue gap, a clash, and an STPM school.
        self._course('TST-LAW', 'Sarjana Muda Undang-Undang', level='Ijazah Sarjana Muda')
        gap = self._app(chosen_programme={'course_id': 'TST-LAW',
                                          'course_name': 'Sarjana Muda Undang-Undang'})
        clash = self._multi(self._app(name='OTHER STUDENT'))
        self._offer(clash, 'DIPLOMA KEJURUTERAAN AWAM', 'UNIVERSITY OF CYBERJAYA')
        stpm = self._app(name='THIRD STUDENT', chosen_pathway='stpm', pre_u_track='sains',
                         pre_u_institution='SMK DATUK MANSOR')
        out = self._run()
        self.assertIn('CATALOGUE_GAP (1)', out)
        self.assertIn('CLASH (1)', out)
        self.assertIn('STPM (1)', out)
        for app in (gap, clash, stpm):
            self.assertIn(f'#{app.pk}', out)
        self.assertIn('need a human', out)

    def test_already_filled_rows_are_counted_not_relisted(self):
        self._app(chosen_programme={'course_id': 'TST-ANIM', 'institution': 'UTHM'})
        out = self._run()
        self.assertIn('1 already on file', out)
