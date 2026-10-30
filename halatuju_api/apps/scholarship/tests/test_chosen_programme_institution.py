"""`chosen_programme` names the INSTITUTION the student picked (Scholarship My Plans redesign,
owner rulings 2026-10-30).

The web now sends ``{course_id, course_name, field_key, institution, institution_id}`` — the
institution's CATALOGUE spelling (``Institution.institution_name``; ``StpmCourse.university`` for a
degree), the same spelling ``offer_pathway`` compares an offer letter against. Lessons 2026-10-29
("a new shape in a shared JSON field is a change to EVERY reader"): every server reader of the
field is walked here with the new shape —

  write   the apply submit (serializer → ``create_application`` → intake snapshot) and the
          two-way pathway sync (application → profile on submit, profile → open application on a
          /profile edit, through ``family.copy_pathway``'s provenance guard);
  read    ``card_display.resolve_institution`` (sponsor card), ``pathway_engine._declared_pathway``
          ("you told us X"), ``offer_pathway.institution_agreement`` (the offer comparison),
          ``offer_sync.sync_institution_from_catalogue`` (must not overwrite her pick),
          ``funding_estimate._classify_programme`` and ``results_route.destination`` (the extra
          keys change nothing they read).
"""
import pytest

from apps.courses.models import (Course, CourseInstitution, CourseRequirement, FieldTaxonomy,
                                 Institution, StudentProfile)
from apps.courses.serializers import ProfileUpdateSerializer
from apps.scholarship import card_display, family, offer_pathway, results_route
from apps.scholarship.funding_estimate import _classify_programme
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.pathway_engine import _declared_pathway
from apps.scholarship.serializers import ApplicationCreateSerializer
from apps.scholarship.services import create_application
from apps.scholarship.services.offer_sync import sync_institution_from_catalogue
from apps.scholarship.tests.factories import make_application, make_student

PICK = {'course_id': 'P-ELEK', 'course_name': 'Diploma Kejuruteraan Elektrik', 'field_key': 'eng',
        'institution': 'Politeknik Ungku Omar', 'institution_id': 'POLY-PUO'}


@pytest.fixture
def catalogue(db):
    """One diploma at TWO polytechnics — the multi-campus case where her pick is the only answer."""
    FieldTaxonomy.objects.get_or_create(key='eng', defaults={
        'name_en': 'Engineering', 'name_ms': 'Kejuruteraan', 'name_ta': 'Eng', 'image_slug': 'eng',
        'sort_order': 1})
    course = Course.objects.create(course_id='P-ELEK', course='Diploma Kejuruteraan Elektrik',
                                   level='Diploma', department='-', field='-', field_key_id='eng')
    CourseRequirement.objects.create(course=course, source_type='poly')
    for iid, name, acr, state in (('POLY-PUO', 'Politeknik Ungku Omar', 'PUO', 'Perak'),
                                  ('POLY-PKB', 'Politeknik Kota Bharu', 'PKB', 'Kelantan')):
        inst = Institution.objects.create(institution_id=iid, institution_name=name, acronym=acr,
                                          type='Politeknik', state=state)
        CourseInstitution.objects.create(course=course, institution=inst)
    return course


@pytest.mark.django_db
class TestWrite:
    def test_the_submit_serializer_keeps_both_institution_keys(self):
        ser = ApplicationCreateSerializer(data={'consent_to_contact': True, 'chosen_programme': PICK})
        assert ser.is_valid(), ser.errors
        assert ser.validated_data['chosen_programme'] == PICK

    def test_submit_stores_it_on_the_application_and_the_snapshot_then_the_profile(self):
        cohort = ScholarshipCohort.objects.create(code='b40-inst', name='B40', year=2026,
                                                  is_active=True, is_open=True)
        profile = StudentProfile.objects.create(supabase_user_id='inst-user', nric='050505-05-5055',
                                                name='Pick Student')
        app = create_application(profile=profile, cohort=cohort, to_email='x@y.com', lang='en',
                                 validated_data={'consent_to_contact': True, 'pathway_certainty': 'sure',
                                                 'chosen_pathway': 'poly', 'chosen_programme': PICK})
        app.refresh_from_db()
        assert app.chosen_programme == PICK
        assert app.intake_snapshot['application']['chosen_programme'] == PICK
        # The submit mirrors the pathway onto the profile (its durable home) — keys and all.
        family.copy_pathway(app, profile)
        assert profile.chosen_programme == PICK

    def test_a_profile_edit_carries_it_to_the_open_application(self):
        app = make_application('submitted', chosen_pathway='poly',
                               chosen_programme={'course_id': 'P-ELEK', 'course_name': 'Diploma Kejuruteraan Elektrik'})
        profile = app.profile
        ser = ProfileUpdateSerializer(profile, data={'chosen_programme': PICK}, partial=True)
        assert ser.is_valid(), ser.errors
        ser.save()
        family.copy_pathway(profile, app)
        assert app.chosen_programme == PICK

    def test_a_plain_pick_never_overwrites_an_offer_confirmed_programme(self):
        confirmed = {**PICK, 'institution': 'Politeknik Kota Bharu', 'source': 'offer_letter_confirmed'}
        app = make_application('submitted', chosen_programme=confirmed)
        student = make_student()
        student.chosen_programme = PICK
        family.copy_pathway(student, app)
        assert app.chosen_programme == confirmed      # the #117 guard holds for the new keys too


@pytest.mark.django_db
class TestReaders:
    def test_the_sponsor_card_shows_the_picked_institution(self):
        app = make_application('submitted', chosen_programme=PICK)
        assert card_display.resolve_institution(app) == 'Politeknik Ungku Omar'

    def test_the_declaration_names_the_picked_institution(self):
        app = make_application('submitted', chosen_programme=PICK)
        assert _declared_pathway(app) == ('Diploma Kejuruteraan Elektrik', 'Politeknik Ungku Omar')

    def test_the_offer_comparison_reads_the_pick_on_a_multi_campus_course(self, catalogue):
        # Before 2026-10-30 a multi-campus pick stored no institution, so this read 'unknown'.
        assert offer_pathway.institution_agreement('P-ELEK', PICK['institution'],
                                                   'POLITEKNIK UNGKU OMAR, IPOH, PERAK') == 'match'
        assert offer_pathway.institution_agreement('P-ELEK', PICK['institution'],
                                                   'Politeknik Kota Bharu') == 'clash'
        assert offer_pathway.institution_agreement('P-ELEK', '', 'Politeknik Kota Bharu') == 'unknown'

    def test_the_catalogue_fill_never_overwrites_her_pick(self, catalogue):
        app = make_application('submitted', chosen_programme=PICK)
        assert sync_institution_from_catalogue(app, offer_check={}) is False
        app.refresh_from_db()
        assert app.chosen_programme['institution'] == 'Politeknik Ungku Omar'

    def test_the_extra_keys_change_nothing_the_funding_estimate_reads(self):
        three = {k: PICK[k] for k in ('course_id', 'course_name', 'field_key')}
        assert _classify_programme(PICK) == _classify_programme(three)

    def test_the_extra_keys_change_nothing_the_results_route_reads(self, catalogue):
        three = {k: PICK[k] for k in ('course_id', 'course_name', 'field_key')}
        with_inst = make_application('submitted', chosen_pathway='poly', chosen_programme=PICK)
        without = make_application('submitted', chosen_pathway='poly', chosen_programme=three)
        assert results_route.destination(with_inst) == results_route.destination(without)
