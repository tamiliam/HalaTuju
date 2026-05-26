"""S7: new Plans + Support intake fields persist on the application, snapshot, and read back."""
import pytest

from apps.courses.models import StudentProfile
from apps.scholarship.models import ScholarshipCohort
from apps.scholarship.services import create_application
from apps.scholarship.serializers import ApplicationReadSerializer


@pytest.mark.django_db
class TestApplicationIntakeFields:
    def test_create_persists_and_reads_new_fields(self):
        cohort = ScholarshipCohort.objects.create(
            code='b40-test', name='B40 Test', year=2026, is_active=True, is_open=True)
        profile = StudentProfile.objects.create(
            supabase_user_id='intake-user', nric='040815-01-2022', name='Test Student')
        validated = {
            'consent_to_contact': True,
            'field_of_study': 'engineering',
            'pathways_considered': ['matrik', 'asasi', 'stpm'],
            'top_choices': [{'rank': 1, 'course_id': 'C1', 'course_name': 'Eng'}],
            'upu_status': 'public_other',
            'other_scholarships': ['jpa', 'mara'],
            'other_scholarships_text': 'Foo Foundation',
            'help_university': 'yes',
            'help_scholarship': 'unsure',
            'anything_else': 'I am the eldest of five.',
        }
        app = create_application(
            profile=profile, cohort=cohort, validated_data=validated,
            to_email='x@y.com', lang='en')
        app.refresh_from_db()

        # Persisted on the application row.
        assert app.field_of_study == 'engineering'
        assert app.pathways_considered == ['matrik', 'asasi', 'stpm']
        assert app.top_choices[0]['course_id'] == 'C1'
        assert app.upu_status == 'public_other'
        assert app.other_scholarships == ['jpa', 'mara']
        assert app.other_scholarships_text == 'Foo Foundation'
        assert app.help_university == 'yes'
        assert app.help_scholarship == 'unsure'
        assert app.anything_else == 'I am the eldest of five.'
        assert app.mentoring_candidate is False   # coordinator-set, not from the form

        # Frozen in the immutable audit snapshot.
        snap = app.intake_snapshot['application']
        assert snap['field_of_study'] == 'engineering'
        assert snap['upu_status'] == 'public_other'
        assert snap['other_scholarships'] == ['jpa', 'mara']

        # Surfaced by the read serializer.
        data = ApplicationReadSerializer(app).data
        assert data['upu_status'] == 'public_other'
        assert data['pathways_considered'] == ['matrik', 'asasi', 'stpm']
        assert data['mentoring_candidate'] is False

    def test_create_persists_plans_redesign_sure_branch(self):
        cohort = ScholarshipCohort.objects.create(
            code='b40-sure', name='B40 Test', year=2026, is_active=True, is_open=True)
        profile = StudentProfile.objects.create(
            supabase_user_id='plans-sure', nric='050202-02-2022', name='Sure Student')
        validated = {
            'consent_to_contact': True,
            'pathway_certainty': 'sure',
            'chosen_pathway': 'poly',
            'chosen_programme': {
                'course_id': 'P1', 'course_name': 'Diploma Hortikultur',
                'institution': 'Politeknik Nilai', 'source': 'spm',
            },
            'field_of_study': 'engineering',
        }
        app = create_application(
            profile=profile, cohort=cohort, validated_data=validated,
            to_email='x@y.com', lang='en')
        app.refresh_from_db()

        assert app.pathway_certainty == 'sure'
        assert app.chosen_pathway == 'poly'
        assert app.chosen_programme['course_id'] == 'P1'
        # Omitted fields fall back to model defaults (not None).
        assert app.uncertainty_reasons == []
        assert app.uncertainty_note == ''
        assert app.pre_u_track == ''
        # Frozen in the snapshot + surfaced by the read serializer.
        assert app.intake_snapshot['application']['chosen_programme']['course_id'] == 'P1'
        data = ApplicationReadSerializer(app).data
        assert data['chosen_pathway'] == 'poly'
        assert data['chosen_programme']['course_id'] == 'P1'

    def test_create_persists_plans_redesign_uncertain_branch(self):
        cohort = ScholarshipCohort.objects.create(
            code='b40-unsure', name='B40 Test', year=2026, is_active=True, is_open=True)
        profile = StudentProfile.objects.create(
            supabase_user_id='plans-unsure', nric='050202-02-3033', name='Unsure Student')
        validated = {
            'consent_to_contact': True,
            'pathway_certainty': 'uncertain',
            'pathways_considered': ['stpm', 'asasi'],
            'uncertainty_reasons': ['waiting', 'financial'],
            'uncertainty_note': 'Waiting for UPU placement; depends on funding.',
        }
        app = create_application(
            profile=profile, cohort=cohort, validated_data=validated,
            to_email='x@y.com', lang='en')
        app.refresh_from_db()

        assert app.pathway_certainty == 'uncertain'
        assert app.uncertainty_reasons == ['waiting', 'financial']
        assert app.uncertainty_note.startswith('Waiting')
        assert app.pathways_considered == ['stpm', 'asasi']
        assert app.chosen_pathway == ''  # sure-only field stays at default
        assert app.intake_snapshot['application']['uncertainty_reasons'] == ['waiting', 'financial']
