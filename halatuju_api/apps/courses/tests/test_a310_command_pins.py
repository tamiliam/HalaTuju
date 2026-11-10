"""A3.10 pins: the three long command functions give the same answers after being split.

Written BEFORE the split and run against the old code (the corpus and the golden were
generated from it), so a refactor that moves a branch, reorders a rule or changes a write
fails here.

* `classify_course` / `classify_stpm_course`: a corpus of (inputs -> key) rows, one to three
  inputs for EVERY distinct executed path through the old code (251 and 97 paths).
* `sync_stpm_mohe`: the full report text and the database after a dry run and an apply, over a
  catalogue that exercises every branch of the report (new, removed, already-inactive removed,
  reactivated, merit change, bad merit, url change, blank url, blank id row).
"""
import csv
import json
import os
import tempfile
from io import StringIO

import pytest
from django.core.management import call_command

from apps.courses.management.commands.backfill_spm_field_key import classify_course
from apps.courses.management.commands.classify_stpm_fields import classify_stpm_course
from apps.courses.models import FieldTaxonomy, StpmCourse

_FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fixtures')


def _corpus():
    with open(os.path.join(_FIX, 'a310_classifier_pins.json'), encoding='utf-8') as fh:
        return json.load(fh)


class TestClassifierPins:
    def test_classify_course_unchanged(self):
        rows = _corpus()['spm']
        assert len(rows) > 500
        bad = [(r[:3], r[3], classify_course(*r[:3])) for r in rows
               if classify_course(*r[:3]) != r[3]]
        assert bad == []

    def test_classify_stpm_course_unchanged(self):
        rows = _corpus()['stpm']
        assert len(rows) > 200
        bad = [(r[:3], r[3], classify_stpm_course(*r[:3])) for r in rows
               if classify_stpm_course(*r[:3]) != r[3]]
        assert bad == []


# --------------------------------------------------------------------------- sync_stpm_mohe

_GOLDEN = os.path.join(_FIX, 'a310_sync_stpm_mohe_golden.json')
_FIELDS = ['course_id', 'course_name', 'university', 'merit', 'stream', 'mohe_url', 'badges', 'year']


def _csv(rows):
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8')
    w = csv.DictWriter(f, fieldnames=_FIELDS)
    w.writeheader()
    w.writerows(rows)
    f.close()
    return f.name


def _row(cid, name='X', uni='U', merit='', url=''):
    return {'course_id': cid, 'course_name': name, 'university': uni, 'merit': merit,
            'stream': 'science', 'mohe_url': url, 'badges': '', 'year': '2026'}


@pytest.fixture
def catalogue():
    ft, _ = FieldTaxonomy.objects.get_or_create(
        key='a310_pin', defaults={'name_en': 'P', 'name_ms': 'P', 'name_ta': 'P',
                                  'image_slug': 'a310-pin', 'sort_order': 1})

    def mk(cid, name, merit, url='', active=True):
        StpmCourse.objects.create(course_id=cid, course_name=name, university='UNI', field_key=ft,
                                  merit_score=merit, mohe_url=url, is_active=active)
    mk('K01', 'Kept same', 70.0, 'https://x/K01')
    mk('K02', 'Kept merit moved', 70.0, 'https://x/K02')
    mk('K03', 'Kept url moved', 60.0, 'https://x/old')
    mk('K04', 'Kept bad merit', 65.0, '')
    mk('K05', 'Kept no merit in db', None, '')
    mk('K06', 'Kept blank csv url', 55.0, 'https://x/K06')
    mk('R01', 'Removed active one', 50.0)
    mk('R02', 'Removed active two', 50.0)
    mk('R03', 'Removed already inactive', 50.0, active=False)
    mk('B01', 'Back from inactive', 40.0, 'https://x/B01', active=False)
    mk('B02', 'Back with new url', 41.0, '', active=False)
    mk('M01', 'Merit tiny change', 70.0)


def _scenario_csv():
    return _csv([
        _row('K01', merit='70.0', url='https://x/K01'),
        _row('K02', merit='72.5', url='https://x/K02'),
        _row('K03', merit='60.0', url='https://x/new'),
        _row('K04', merit='abc', url=''),
        _row('K05', merit='55.5', url=''),
        _row('K06', merit='55.0', url=''),
        _row('B01', merit='40.0', url='https://x/B01'),
        _row('B02', merit='41.0', url='https://x/B02-new'),
        _row('M01', merit='70.005'),
        _row('N02', 'New two', 'UM', '80.0'),
        _row('N01', 'New one', 'USM', '75.0'),
        _row('  ', 'Blank id', 'UM'),
        _row(' K01 ', merit='70.0', url='https://x/K01'),
    ])


def _snapshot():
    return {c.course_id: [c.is_active, c.mohe_url, c.merit_score]
            for c in StpmCourse.objects.order_by('course_id')}


def _run(**kw):
    out = StringIO()
    call_command('sync_stpm_mohe', csv=_scenario_csv(), stdout=out, **kw)
    return out.getvalue()


@pytest.mark.django_db
class TestSyncStpmMoheGolden:
    def test_dry_run_and_apply_unchanged(self, catalogue):
        before = _snapshot()
        dry_out = _run()
        assert _snapshot() == before      # a dry run writes nothing
        apply_out = _run(apply=True)
        got = {'dry_out': dry_out, 'apply_out': apply_out, 'after_apply': _snapshot()}
        if not os.path.exists(_GOLDEN):
            with open(_GOLDEN, 'w', encoding='utf-8') as fh:
                json.dump(got, fh, ensure_ascii=False, indent=1, sort_keys=True)
            pytest.fail('golden written from the current code; commit it and re-run')
        with open(_GOLDEN, encoding='utf-8') as fh:
            want = json.load(fh)
        assert got == want
