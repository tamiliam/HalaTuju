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
