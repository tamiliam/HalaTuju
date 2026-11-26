"""Pre-U sprint: `pre_u_studied_at` is NOT NULL, so it needs a DATABASE default (courses 0102, as 0084 / 0088).

The old image serves between the hand migration and the deploy; its profile inserts do not name the column.
"""
from django.db.models import NOT_PROVIDED

from apps.courses.models import StudentProfile


def test_pre_u_studied_at_has_a_database_default():
    field = StudentProfile._meta.get_field('pre_u_studied_at')
    assert field.db_default == ''
    assert field.db_default is not NOT_PROVIDED
    assert not field.null


def test_held_results_cleared_at_stays_nullable():
    assert StudentProfile._meta.get_field('held_results_cleared_at').null


def test_migration_0102_adds_the_column_with_the_database_default():
    import importlib
    mig = importlib.import_module('apps.courses.migrations.0102_angka_giliran_11_pre_u_studied_at')
    add = next(op for op in mig.Migration.operations if getattr(op, 'name', '') == 'pre_u_studied_at')
    assert add.field.db_default == ''
