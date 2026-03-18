"""Tests for StpmCourse and StpmRequirement models."""
import pytest
from apps.courses.models import MascoOccupation, StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmCourseCreation:

    def test_stpm_course_creation(self):
        course = StpmCourse.objects.create(
            course_id='UM-CS-001',
            course_name='Bachelor of Computer Science',
            university='Universiti Malaya',
            stream='science',
            field_key_id='it-perisian',
        )
        course.refresh_from_db()
        assert course.course_id == 'UM-CS-001'
        assert course.course_name == 'Bachelor of Computer Science'
        assert course.university == 'Universiti Malaya'
        assert course.stream == 'science'
        assert str(course) == 'UM-CS-001: Bachelor of Computer Science'


@pytest.mark.django_db
class TestStpmRequirementCreation:

    def test_stpm_requirement_creation(self):
        course = StpmCourse.objects.create(
            course_id='USM-ENG-010',
            course_name='Bachelor of Engineering',
            university='Universiti Sains Malaysia',
            stream='science',
            field_key_id='kejuruteraan-am',
        )
        req = StpmRequirement.objects.create(
            course=course,
            min_cgpa=3.0,
            stpm_min_subjects=3,
            stpm_min_grade='B',
            stpm_req_math_t=True,
            stpm_req_physics=True,
            spm_credit_bm=True,
            spm_credit_math=True,
            no_colorblind=True,
            min_muet_band=3,
        )
        req.refresh_from_db()
        assert req.course_id == 'USM-ENG-010'
        assert req.min_cgpa == 3.0
        assert req.stpm_min_subjects == 3
        assert req.stpm_min_grade == 'B'
        assert req.stpm_req_math_t is True
        assert req.stpm_req_physics is True
        assert req.stpm_req_pa is False  # default
        assert req.spm_credit_bm is True
        assert req.spm_credit_math is True
        assert req.spm_pass_sejarah is False  # default
        assert req.no_colorblind is True
        assert req.min_muet_band == 3
        assert str(req) == 'STPM Requirements for USM-ENG-010'

    def test_stpm_requirement_subject_group_json(self):
        course = StpmCourse.objects.create(
            course_id='UKM-SCI-005',
            course_name='Bachelor of Science',
            university='Universiti Kebangsaan Malaysia',
            field_key_id='sains-hayat',
        )
        group_data = {
            'min_count': 2,
            'min_grade': 'C',
            'subjects': ['physics', 'chemistry', 'biology'],
        }
        req = StpmRequirement.objects.create(
            course=course,
            stpm_subject_group=group_data,
            spm_subject_group={'min_count': 1, 'subjects': ['science']},
        )
        req.refresh_from_db()
        assert req.stpm_subject_group == group_data
        assert req.stpm_subject_group['min_count'] == 2
        assert 'chemistry' in req.stpm_subject_group['subjects']
        assert req.spm_subject_group['min_count'] == 1


@pytest.mark.django_db
class TestStpmCourseMeritScore:

    def test_stpm_course_merit_score(self):
        """StpmCourse stores merit_score as nullable float."""
        course = StpmCourse.objects.create(
            course_id='MERIT001',
            course_name='Test Merit Programme',
            university='Test University',
            stream='science',
            merit_score=96.04,
            field_key_id='umum',
        )
        course.refresh_from_db()
        assert course.merit_score == 96.04

    def test_stpm_course_merit_score_null(self):
        """StpmCourse merit_score can be null (Tiada)."""
        course = StpmCourse.objects.create(
            course_id='MERIT002',
            course_name='No Merit Programme',
            university='Test University',
            stream='arts',
            field_key_id='umum',
        )
        course.refresh_from_db()
        assert course.merit_score is None


@pytest.mark.django_db
class TestStpmCourseMetadata:

    def test_stpm_course_metadata_fields(self):
        """StpmCourse has field and description columns."""
        course = StpmCourse.objects.create(
            course_id='TEST-META-001',
            course_name='Test Programme',
            university='Test University',
            stream='science',
            field='Engineering',
            description='A test programme in engineering.',
            field_key_id='kejuruteraan-am',
        )
        course.refresh_from_db()
        assert course.field == 'Engineering'
        assert course.description == 'A test programme in engineering.'

    def test_stpm_course_metadata_defaults_blank(self):
        """Metadata fields default to empty string."""
        course = StpmCourse.objects.create(
            course_id='TEST-META-002',
            course_name='Test Programme 2',
            university='Test University',
            field_key_id='umum',
        )
        assert course.field == ''
        assert course.description == ''


@pytest.mark.django_db
class TestStpmCourseCareerOccupations:
    """Test M2M relationship between StpmCourse and MascoOccupation."""

    def setUp(self):
        self.course = StpmCourse.objects.create(
            course_id='test-stpm-career',
            course_name='Test Programme',
            university='Universiti Test',
            field_key_id='umum',
        )
        self.occ = MascoOccupation.objects.create(
            masco_code='2512-03',
            job_title='Jurutera Perisian',
            emasco_url='https://emasco.mohr.gov.my/masco/2512-03',
        )

    def test_can_add_career_occupation(self):
        self.setUp()
        self.course.career_occupations.add(self.occ)
        assert self.course.career_occupations.count() == 1

    def test_reverse_relation(self):
        self.setUp()
        self.course.career_occupations.add(self.occ)
        assert self.course in self.occ.stpm_courses.all()

    def test_multiple_occupations(self):
        self.setUp()
        occ2 = MascoOccupation.objects.create(
            masco_code='2513-01',
            job_title='Pembangun Web',
            emasco_url='https://emasco.mohr.gov.my/masco/2513-01',
        )
        self.course.career_occupations.add(self.occ, occ2)
        assert self.course.career_occupations.count() == 2


@pytest.mark.django_db
class TestStpmCourseIsActive:

    def test_is_active_defaults_true(self):
        course = StpmCourse(
            course_id='TEST_ACTIVE_001',
            course_name='Test Active Course',
            university='Test University',
            field_key_id='it-perisian',
        )
        assert course.is_active is True

    def test_can_set_inactive(self):
        course = StpmCourse.objects.create(
            course_id='TEST_INACTIVE_001',
            course_name='Inactive Course',
            university='Test University',
            field_key_id='it-perisian',
            is_active=False,
        )
        course.refresh_from_db()
        assert course.is_active is False
