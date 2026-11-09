"""T2 review (round 2): EVERY footprint source is read alike by the table path and the one-person path.

`test_t2_review.py` checks the two paths on a hand-picked fixture. This one builds ONE row per source
straight from the tuples themselves (`FK_TRACES`, `MENTOR_TRACES`, `CORE_EMAIL_STAMPS`, `EMAIL_STAMPS`),
so a source added later is covered the day it is added, and asserts that:

  * every key appears, in both paths, for the one person every row names;
  * `footprints([a])[a.pk] == footprint(a)`.

Each row is filled generically from its model's own fields (`_Builder.build`): a required column gets a
plain value (its first choice, a number, a date, an address), a required foreign key gets a row of
its own, built the same way. Where a model's own `save()` fence or a unique constraint needs more,
`_given()` hands it exactly that, with the reason; a source that cannot be built at all goes in
`NOT_BUILT` with the reason (today there are none).
"""
import datetime
import decimal
import uuid

from django.apps import apps
from django.db import models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.courses.models import PartnerAdmin
from apps.scholarship import staff_footprint
from apps.scholarship.models import Mentor, ScholarshipApplication
from apps.scholarship.qc_separation import REVIEW_VERBS
from apps.scholarship.tests.factories import make_admin, make_application, make_org

#: `key: reason` for a source whose row the generic builder cannot make. Kept explicit and short.
NOT_BUILT = {}


def _given():
    """`model label: (reason, callable -> extra values)`: what a model needs beyond the generic fill."""
    from apps.courses import theme_tokens
    from apps.scholarship import overview_layout
    return {
        'courses.OrganisationTheme': (
            '`save()` validates the token set', lambda: {'tokens': theme_tokens.tokens_from_colour('#a21caf')}),
        'scholarship.OrganisationOverviewLayout': (
            '`save()` refuses a layout missing a widget', lambda: {'sections': overview_layout.default()}),
        'scholarship.ProgrammeOverviewLayout': (
            '`save()` refuses a layout missing a widget', lambda: {'sections': overview_layout.default()}),
        'scholarship.MentorAssignment': (
            'one assignment per application: the second source needs its own case',
            lambda: {'application': make_application('submitted')}),
    }

#: The filter each StaffActivity trace narrows to (`_narrow`), turned into a value the row carries.
_EXTRA_VALUES = {'review': {'verb': REVIEW_VERBS[0]}, 'other': {'verb': 'contract_countersigned'}}


def _plain_value(field):
    if field.choices:
        return field.choices[0][0]
    if isinstance(field, models.EmailField):
        return f'someone-{uuid.uuid4().hex[:8]}@example.com'
    if isinstance(field, (models.CharField, models.TextField)):
        return ('x' + uuid.uuid4().hex)[:field.max_length or 20]
    if isinstance(field, models.BooleanField):
        return False
    if isinstance(field, models.DecimalField):
        return decimal.Decimal('1')
    if isinstance(field, (models.IntegerField, models.FloatField)):
        return 1
    if isinstance(field, models.DateTimeField):
        return timezone.now()
    if isinstance(field, models.DateField):
        return datetime.date.today()
    if isinstance(field, models.DurationField):
        return datetime.timedelta(minutes=1)
    if isinstance(field, models.UUIDField):
        return uuid.uuid4()
    if isinstance(field, models.JSONField):
        return {}
    if isinstance(field, models.FileField):
        return 'x.pdf'
    raise TypeError(f'no plain value for {field!r}')


class _Builder:
    """A row of any model, with every required column filled. A required foreign key reuses one
    shared row per model (a one-to-one gets its own), and never points at the person under test."""

    def __init__(self, seeds):
        self.shared = dict(seeds)

    def related(self, model, unique):
        if not unique and model in self.shared:
            return self.shared[model]
        row = self.build(model)
        if not unique:
            self.shared[model] = row
        return row

    def build(self, model, **given):
        values = {}
        for f in model._meta.concrete_fields:
            if f.primary_key or f.name in given or f.attname in given:
                continue
            if getattr(f, 'auto_now', False) or getattr(f, 'auto_now_add', False):
                continue
            if f.is_relation:
                if not f.null:
                    values[f.name] = self.related(f.related_model, f.one_to_one or f.unique)
                continue
            if f.null or f.has_default():
                continue
            if f.blank and f.empty_strings_allowed and not f.choices:
                continue
            values[f.name] = _plain_value(f)
        return model._base_manager.create(**{**values, **given})


class TestEverySourceReadsAlikeOnBothPaths(TestCase):

    def test_one_row_per_source(self):
        org = make_org()
        person = make_admin('mentor', owning_org=org)
        other = make_admin('admin', owning_org=org)
        app = make_application('submitted')
        builder = _Builder({PartnerAdmin: other, ScholarshipApplication: app,
                            Mentor: make_admin('mentor', owning_org=org).mentor,
                            type(org): org})
        address = person.email.upper()          # stamps match whatever the case of the address
        built, failed = set(), {}

        extras = _given()

        def make(key, model, **given):
            if key in NOT_BUILT:
                return
            _why, more = extras.get(model._meta.label, ('', dict))
            given = {**more(), **given}
            try:
                with transaction.atomic():
                    builder.build(model, **given)
                built.add(key)
            except Exception as exc:  # the failure is reported below, with the source's key
                failed[key] = f'{type(exc).__name__}: {exc}'[:160]

        for key, label, name, fields, extra in staff_footprint.FK_TRACES:
            narrowing = _EXTRA_VALUES.get(extra, extra) if isinstance(extra, str) else (extra or {})
            make(key, apps.get_model(label, name), **{fields[0]: person}, **narrowing)
        for key, label, name, extra in staff_footprint.MENTOR_TRACES:
            make(key, apps.get_model(label, name), mentor=person.mentor, **(extra or {}))
        for key, label, name, fields in staff_footprint.CORE_EMAIL_STAMPS + staff_footprint.EMAIL_STAMPS:
            make(key, apps.get_model(label, name), **{fields[0]: address})

        self.assertEqual(failed, {}, 'A source could not be built generically. Fix the builder, or '
                         'list it in NOT_BUILT with the reason.')
        every = set(staff_footprint._keys()) - set(NOT_BUILT)
        self.assertEqual(built, every)
        one = staff_footprint.footprint(person)
        self.assertEqual(sorted(every - set(one)), [], 'a source built for this person is not counted')
        self.assertEqual(staff_footprint.footprints([person])[person.pk], one)
        self.assertEqual(staff_footprint.footprint(other), staff_footprint.footprints([other])[other.pk])
