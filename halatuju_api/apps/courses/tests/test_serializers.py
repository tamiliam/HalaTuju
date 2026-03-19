"""
Tests for course serializers.

Covers:
- Grade key passthrough (frontend sends engine keys directly)
- Gender normalization (English/Malay/Tamil → engine format)
- Nationality normalization
- Boolean → Ya/Tidak conversion for colorblind/disability
"""
from django.test import TestCase
from apps.courses.serializers import EligibilityRequestSerializer


class TestGradeKeyPassthrough(TestCase):
    """Test that engine keys pass through the serializer unchanged."""

    def _validate(self, grades_input):
        """Helper: run serializer and return validated grades dict."""
        data = {'grades': grades_input, 'gender': 'male'}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        return s.validated_data['grades']

    def test_core_subjects(self):
        """Core subjects pass through as engine keys."""
        grades = self._validate({
            'bm': 'A', 'eng': 'B+', 'hist': 'C', 'math': 'A-'
        })
        self.assertEqual(grades['bm'], 'A')
        self.assertEqual(grades['eng'], 'B+')
        self.assertEqual(grades['hist'], 'C')
        self.assertEqual(grades['math'], 'A-')

    def test_science_subjects(self):
        """Science subjects pass through as engine keys."""
        grades = self._validate({
            'phy': 'A', 'chem': 'B', 'bio': 'C', 'addmath': 'A+'
        })
        self.assertEqual(grades['phy'], 'A')
        self.assertEqual(grades['chem'], 'B')
        self.assertEqual(grades['bio'], 'C')
        self.assertEqual(grades['addmath'], 'A+')

    def test_arts_subjects(self):
        """Arts subjects pass through as engine keys."""
        grades = self._validate({
            'ekonomi': 'B', 'poa': 'A', 'business': 'C', 'geo': 'B+'
        })
        self.assertEqual(grades['ekonomi'], 'B')
        self.assertEqual(grades['poa'], 'A')
        self.assertEqual(grades['business'], 'C')
        self.assertEqual(grades['geo'], 'B+')

    def test_religious_moral(self):
        """Religious and moral subjects pass through."""
        grades = self._validate({'islam': 'A', 'moral': 'B'})
        self.assertEqual(grades['islam'], 'A')
        self.assertEqual(grades['moral'], 'B')

    def test_science_general(self):
        """General science passes through."""
        grades = self._validate({'sci': 'C'})
        self.assertEqual(grades['sci'], 'C')

    def test_technical_subjects(self):
        """Technical subjects pass through."""
        grades = self._validate({'comp_sci': 'B', 'psv': 'A'})
        self.assertEqual(grades['comp_sci'], 'B')
        self.assertEqual(grades['psv'], 'A')

    def test_full_student_profile(self):
        """A complete 8-subject profile passes through correctly."""
        grades = self._validate({
            'bm': 'A', 'eng': 'B+', 'math': 'A', 'hist': 'C',
            'phy': 'A-', 'chem': 'B',
            'addmath': 'B+', 'moral': 'A'
        })
        self.assertEqual(len(grades), 8)
        self.assertIn('bm', grades)
        self.assertIn('eng', grades)
        self.assertIn('math', grades)
        self.assertIn('hist', grades)
        self.assertIn('phy', grades)
        self.assertIn('chem', grades)
        self.assertIn('addmath', grades)
        self.assertIn('moral', grades)


class TestGenderNormalization(TestCase):
    """Test gender values are normalized to engine format (Lelaki/Perempuan)."""

    def _validate_gender(self, gender_input):
        data = {'grades': {'bm': 'A'}, 'gender': gender_input}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        return s.validated_data['gender']

    def test_english_male(self):
        self.assertEqual(self._validate_gender('male'), 'Lelaki')

    def test_english_female(self):
        self.assertEqual(self._validate_gender('female'), 'Perempuan')

    def test_malay_lelaki(self):
        self.assertEqual(self._validate_gender('Lelaki'), 'Lelaki')

    def test_malay_perempuan(self):
        self.assertEqual(self._validate_gender('Perempuan'), 'Perempuan')

    def test_tamil_male(self):
        self.assertEqual(self._validate_gender('\u0b86\u0ba3\u0bcd'), 'Lelaki')

    def test_tamil_female(self):
        self.assertEqual(self._validate_gender('\u0baa\u0bc6\u0ba3\u0bcd'), 'Perempuan')

    def test_case_insensitive(self):
        self.assertEqual(self._validate_gender('MALE'), 'Lelaki')
        self.assertEqual(self._validate_gender('Female'), 'Perempuan')


class TestNationalityNormalization(TestCase):
    """Test nationality values are normalized to engine format."""

    def _validate_nationality(self, nat_input):
        data = {'grades': {'bm': 'A'}, 'gender': 'male', 'nationality': nat_input}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        return s.validated_data['nationality']

    def test_english_malaysian(self):
        self.assertEqual(self._validate_nationality('malaysian'), 'Warganegara')

    def test_english_non_malaysian_underscore(self):
        self.assertEqual(self._validate_nationality('non_malaysian'), 'Bukan Warganegara')

    def test_english_non_malaysian_hyphen(self):
        self.assertEqual(self._validate_nationality('non-malaysian'), 'Bukan Warganegara')

    def test_malay_warganegara(self):
        self.assertEqual(self._validate_nationality('Warganegara'), 'Warganegara')


class TestBooleanConversion(TestCase):
    """Test colorblind and disability remain as booleans through serializer."""

    def test_colorblind_true(self):
        data = {'grades': {'bm': 'A'}, 'gender': 'male', 'colorblind': True}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['colorblind'], True)

    def test_colorblind_false(self):
        data = {'grades': {'bm': 'A'}, 'gender': 'male', 'colorblind': False}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['colorblind'], False)

    def test_disability_true(self):
        data = {'grades': {'bm': 'A'}, 'gender': 'male', 'disability': True}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['disability'], True)

    def test_disability_false(self):
        data = {'grades': {'bm': 'A'}, 'gender': 'male', 'disability': False}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['disability'], False)

    def test_defaults_when_omitted(self):
        """Colorblind and disability default to False when not sent."""
        data = {'grades': {'bm': 'A'}, 'gender': 'male'}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['colorblind'], False)
        self.assertEqual(s.validated_data['disability'], False)


class TestValidation(TestCase):
    """Test that invalid requests are rejected."""

    def test_missing_grades(self):
        data = {'gender': 'male'}
        s = EligibilityRequestSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('grades', s.errors)

    def test_empty_grades(self):
        """Empty grades dict is valid (The Ghost student in golden master)."""
        data = {'grades': {}, 'gender': 'male'}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_gender_default(self):
        """Gender defaults to Lelaki if not provided."""
        data = {'grades': {'bm': 'A'}}
        s = EligibilityRequestSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['gender'], 'Lelaki')
