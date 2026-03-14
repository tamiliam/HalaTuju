"""Tests for StpmCourse and StpmRequirement models."""
import pytest
from apps.courses.models import StpmCourse, StpmRequirement


@pytest.mark.django_db
class TestStpmCourseCreation:

    def test_stpm_course_creation(self):
        course = StpmCourse.objects.create(
            course_id='UM-CS-001',
            course_name='Bachelor of Computer Science',
            university='Universiti Malaya',
            stream='science',
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
        )
        course.refresh_from_db()
        assert course.merit_score is None


@pytest.mark.django_db
class TestStpmCourseMetadata:

    def test_stpm_course_metadata_fields(self):
        """StpmCourse has field, category, and description columns."""
        course = StpmCourse.objects.create(
            course_id='TEST-META-001',
            course_name='Test Programme',
            university='Test University',
            stream='science',
            field='Engineering',
            category='Kejuruteraan',
            description='A test programme in engineering.',
        )
        course.refresh_from_db()
        assert course.field == 'Engineering'
        assert course.category == 'Kejuruteraan'
        assert course.description == 'A test programme in engineering.'

    def test_stpm_course_metadata_defaults_blank(self):
        """Metadata fields default to empty string."""
        course = StpmCourse.objects.create(
            course_id='TEST-META-002',
            course_name='Test Programme 2',
            university='Test University',
        )
        assert course.field == ''
        assert course.category == ''
        assert course.description == ''
