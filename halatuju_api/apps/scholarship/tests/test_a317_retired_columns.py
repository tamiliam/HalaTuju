"""A3.17 (TD-084 / TD-226): the new code INSERTs without three retired columns.

`earner_work_status` and `bucket_b_margin` are NOT NULL, and scholarship 0211 removes them from the
Django state only (the columns stay until a later 0212). The new code therefore omits them on INSERT.
These tests create a cohort and an application through the ORM against the migrated test database,
where the columns still exist: they pass only because 0211 gave the two NOT NULL columns a DATABASE
default. Without `db_default`, the cohort INSERT fails on `bucket_b_margin` and the application INSERT
fails on `earner_work_status`.
"""
from django.db import connection
from django.test import TestCase

from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.factories import make_application, make_cohort


class RetiredColumnsInsertTest(TestCase):

    def test_state_no_longer_has_the_retired_fields(self):
        app_fields = {f.name for f in ScholarshipApplication._meta.get_fields()}
        cohort_fields = {f.name for f in ScholarshipCohort._meta.get_fields()}
        self.assertFalse({'earner_work_status', 'household_other_earners'} & app_fields)
        self.assertNotIn('bucket_b_margin', cohort_fields)
        self.assertIn('funding_envelope', cohort_fields)   # kept: the owner has not ruled

    def test_a_cohort_can_be_created_without_bucket_b_margin(self):
        cohort = make_cohort()
        self.assertIsNotNone(cohort.pk)
        self.assertTrue(ScholarshipCohort.objects.filter(pk=cohort.pk).exists())

    def test_an_application_can_be_created_without_earner_work_status(self):
        app = make_application()
        self.assertIsNotNone(app.pk)
        self.assertTrue(ScholarshipApplication.objects.filter(pk=app.pk).exists())

    def test_the_columns_still_exist_with_a_database_default(self):
        with connection.cursor() as cur:
            cols = {}
            for table in ('scholarship_applications', 'scholarship_cohorts'):
                cols.update({
                    (table, c.name): c for c in connection.introspection.get_table_description(cur, table)})
        self.assertIn(('scholarship_applications', 'earner_work_status'), cols)
        self.assertIn(('scholarship_applications', 'household_other_earners'), cols)
        self.assertIn(('scholarship_cohorts', 'bucket_b_margin'), cols)
        self.assertIsNotNone(cols[('scholarship_applications', 'earner_work_status')].default)
        self.assertIsNotNone(cols[('scholarship_cohorts', 'bucket_b_margin')].default)
