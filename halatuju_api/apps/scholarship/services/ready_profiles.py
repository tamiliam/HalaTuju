"""
Drafting the sponsor-facing profile at the reviewer handoff.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from ..models import ScholarshipApplication
from .queries_sla import QUERY_SLA_ACTIVE_STATUSES, is_ready_for_assignment


# ── Check 2 STEP 3 — generate the sponsor-facing profile from available info ──

def generate_ready_profile(application, language=None):
    """STEP 3: generate the (claim-gated) sponsor profile from currently-available
    info and store it as the SponsorProfile draft. Returns ``(sponsor_profile, None)``
    or ``(None, error)``. Shared by the admin 'generate' action and the STEP-3
    auto-trigger so both store identically. Unresolved claims are omitted by the
    generator's claim-gating contract (profile_engine §6)."""
    from ..models import SponsorProfile
    from ..profile_engine import generate_sponsor_profile
    result = generate_sponsor_profile(application, language=language)
    if 'error' in result:
        return None, result['error']
    sp, _ = SponsorProfile.objects.get_or_create(application=application)
    sp.draft_markdown = result['markdown']
    sp.model_used = result.get('model_used', '')
    sp.prompt_version = result.get('prompt_version', '')
    sp.generated_at = timezone.now()
    if sp.status == 'published':
        sp.status = 'draft'  # regenerating a published profile reverts it to draft
    sp.save()
    return sp, None


def autogenerate_ready_profiles(now=None):
    """STEP-3 auto-trigger sweep: draft a profile for each submitted application that
    is ready for assignment (no open queries OR SLA lapsed) and has no profile yet.
    **Gated behind ``CHECK2_AUTO_GENERATE`` (default off)** — it makes billable Gemini
    calls, so it stays a manual admin action until deliberately switched on. Idempotent:
    an application with a generated profile is skipped. Returns ``{'generated': n}``."""
    from django.conf import settings as _settings
    if not getattr(_settings, 'CHECK2_AUTO_GENERATE', False):
        return {'generated': 0}
    now = now or timezone.now()
    generated = 0
    qs = (ScholarshipApplication.objects
          .filter(status__in=QUERY_SLA_ACTIVE_STATUSES, profile_completed_at__isnull=False)
          .select_related('cohort', 'profile'))
    for app in qs:
        sp = getattr(app, 'sponsor_profile', None)
        if sp is not None and sp.generated_at is not None:
            continue  # already drafted — never regenerate automatically
        if not is_ready_for_assignment(app, now):
            continue
        _, error = generate_ready_profile(app)
        if error is None:
            generated += 1
    return {'generated': generated}
