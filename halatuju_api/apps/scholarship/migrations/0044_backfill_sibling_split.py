from django.db import migrations


def backfill_sibling_split(apps, schema_editor):
    """P2 (Check 2): make the school/tertiary split authoritative by backfilling the
    UNAMBIGUOUS legacy case. A legacy ``siblings_studying_count == 0`` means nobody is
    studying → both split counters are 0. Positive legacy counts can't be broken down
    (we don't know school-vs-tertiary), so they're left null → a Check-2 clarify-query.
    Rows that already have the split set are untouched."""
    Application = apps.get_model('scholarship', 'ScholarshipApplication')
    Application.objects.filter(
        siblings_studying_count=0,
        siblings_in_school__isnull=True,
        siblings_in_tertiary__isnull=True,
    ).update(siblings_in_school=0, siblings_in_tertiary=0)


def noop_reverse(apps, schema_editor):
    """Irreversible-by-design: we can't tell backfilled zeros from genuine ones."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0043_sponsor_is_trusted'),
    ]

    operations = [
        migrations.RunPython(backfill_sibling_split, noop_reverse),
    ]
