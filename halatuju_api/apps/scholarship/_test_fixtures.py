"""Transient fixture builder for the document-recognition eval harness (and its tests).

Builds an ApplicantDocument — with a throwaway profile/cohort/application — loaded with
a captured Vision snapshot, so Layer B (the matchers + `doc_match_verdict`) can be
replayed offline without Gemini. Eval/test only; never imported by production paths.
Always call inside a transaction that is rolled back — these rows are disposable.
"""
import contextlib
import uuid
from datetime import datetime

from django.db import transaction
from django.utils import timezone

_SNAPSHOT_FIELDS = ['vision_nric', 'vision_name', 'vision_address', 'vision_error', 'vision_fields']


class _Rollback(Exception):
    """Internal sentinel used to force a transaction rollback (disposable fixtures)."""


@contextlib.contextmanager
def rolled_back():
    """Run a block inside a transaction that is ALWAYS rolled back, so eval fixtures
    never persist (works against the dev DB and inside a test's savepoint alike).
    Assign anything you need to keep to a variable in the enclosing scope."""
    try:
        with transaction.atomic():
            yield
            raise _Rollback
    except _Rollback:
        pass


def build_doc_fixture(doc_type, snap=None, ctx=None):
    """Create a saved ApplicantDocument of ``doc_type`` whose Vision fields come from
    ``snap`` (a captured Layer-A snapshot) and whose linked profile/application come from
    ``ctx`` (the gitignored per-doc context: profile_name/profile_nric/income_route/…)."""
    from apps.courses.models import StudentProfile
    from .models import ScholarshipApplication, ScholarshipCohort, ApplicantDocument
    ctx = ctx or {}
    cohort = ScholarshipCohort.objects.create(code=f'eval-{uuid.uuid4().hex[:8]}', name='eval', year=2026)
    profile = StudentProfile.objects.create(
        supabase_user_id=f'eval-{uuid.uuid4()}',
        nric=ctx.get('profile_nric', '') or '',
        name=ctx.get('profile_name', '') or '',
    )
    app = ScholarshipApplication.objects.create(
        cohort=cohort, profile=profile, status='shortlisted',
        income_route=ctx.get('income_route', '') or '',
        income_earner=ctx.get('income_earner', '') or '',
    )
    doc = ApplicantDocument(
        application=app, doc_type=doc_type,
        household_member=ctx.get('household_member', '') or '',
        storage_path=f'eval/{doc_type}/{uuid.uuid4().hex[:8]}',
    )
    if snap:
        for fld in _SNAPSHOT_FIELDS:
            if fld in snap and snap[fld] is not None:
                setattr(doc, fld, snap[fld])
        run_at = snap.get('vision_run_at')
        if run_at:
            doc.vision_run_at = _parse_dt(run_at)
        elif snap.get('vision_name') or snap.get('vision_fields'):
            doc.vision_run_at = timezone.now()   # a captured read implies the scan ran
    doc.save()
    return doc


def _set_safe(obj, fields):
    """setattr only concrete, coercion-safe fields (text/JSON/bool/int) that exist on the model
    — skips pk, relations, dates, decimals — so a faithful declared record loads without
    save-time coercion errors. Lets the verdict engine see real grades/family/etc."""
    if not fields:
        return
    from django.db import models as dm
    ok = (dm.CharField, dm.TextField, dm.JSONField, dm.BooleanField, dm.IntegerField)
    by_name = {f.name: f for f in obj._meta.get_fields() if hasattr(f, 'attname') and not f.is_relation}
    for k, v in fields.items():
        f = by_name.get(k)
        if f is None or f.primary_key or not isinstance(f, ok):
            continue
        try:
            setattr(obj, k, v)
        except (ValueError, TypeError):
            pass


def build_application_with_docs(app_ctx, docs, profile_fields=None, app_fields=None):
    """Faithful multi-document fixture: one profile/application + ALL its documents, so the
    matchers that cross-check siblings (e.g. a payslip against the member's parent IC) see the
    real context. ``app_ctx`` = {profile_name, profile_nric, income_route, income_earner};
    ``profile_fields``/``app_fields`` = the applicant's full DECLARED record (grades, family, …)
    loaded so checks compare against real data; ``docs`` = list of {doc_type, household_member,
    snapshot}. Returns the saved docs in order."""
    from apps.courses.models import StudentProfile
    from .models import ScholarshipApplication, ScholarshipCohort, ApplicantDocument
    app_ctx = app_ctx or {}
    cohort = ScholarshipCohort.objects.create(code=f'eval-{uuid.uuid4().hex[:8]}', name='eval', year=2026)
    profile = StudentProfile(
        supabase_user_id=f'eval-{uuid.uuid4()}',
        nric=app_ctx.get('profile_nric', '') or '', name=app_ctx.get('profile_name', '') or '')
    _set_safe(profile, profile_fields)            # declared grades / guardians / address / …
    profile.save()
    app = ScholarshipApplication(
        cohort=cohort, profile=profile, status='shortlisted',
        income_route=app_ctx.get('income_route', '') or '', income_earner=app_ctx.get('income_earner', '') or '')
    _set_safe(app, app_fields)                    # declared family roster / income answers / …
    app.save()
    built = []
    for d in docs:
        doc = ApplicantDocument(application=app, doc_type=d['doc_type'],
                                household_member=d.get('household_member', '') or '',
                                storage_path=f"eval/{d['doc_type']}/{uuid.uuid4().hex[:8]}")
        snap = d.get('snapshot') or {}
        for fld in _SNAPSHOT_FIELDS:
            if fld in snap and snap[fld] is not None:
                setattr(doc, fld, snap[fld])
        run_at = snap.get('vision_run_at')
        if run_at:
            doc.vision_run_at = _parse_dt(run_at)
        elif snap.get('vision_name') or snap.get('vision_fields'):
            doc.vision_run_at = timezone.now()
        doc.save()
        built.append(doc)
    return built


def _parse_dt(value):
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if timezone.is_aware(dt) else timezone.make_aware(dt)
    except (ValueError, TypeError):
        return timezone.now()
