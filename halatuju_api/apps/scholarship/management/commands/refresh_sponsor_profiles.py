"""Refresh sponsor profiles onto the CURRENT prompt — both the reviewer DRAFT and, for
already-decided students, the sponsor-facing FINAL.

The older ``backfill_assigned_profiles`` only re-drafts; the final (the profile a sponsor
actually reads) is otherwise only refreshed per-app via the cockpit's Reopen→refine flow.
This command closes that gap so a prompt bump (PROMPT_VERSION) can be rolled across the
fleet — or trialled on ONE student — without touching the cockpit.

Per application (reviewer-ASSIGNED, has a SponsorProfile):
  • skip if the draft was officer-EDITED (never clobber human edits);
  • re-draft on the current prompt (Gemini Flash);
  • if it already HAD a final (a decision was recorded) AND a submitted interview session
    exists, re-finalise on the current prompt (Gemini Pro) from the fresh draft.

Scope + idempotency:
  • Full sweep (default): only profiles whose ``prompt_version`` is stale are touched —
    cheap to re-run.
  • Targeted: set ``PROFILE_REFRESH_APP_IDS`` (csv of ids) and those apps are FORCED
    (refreshed even if already current) — for a single-profile trial/repair.

Argless so it runs via the internal cron endpoint job 'refresh-profiles'. Flag-gated
(``CHECK2_AUTO_GENERATE``) and billable (1 Flash + up to 1 Pro call per application).
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.profile_engine import PROMPT_VERSION, refine_sponsor_profile
from apps.scholarship.services import generate_ready_profile


def _parse_ids(raw):
    ids = set()
    for part in (raw or '').replace(' ', '').split(','):
        if part.isdigit():
            ids.add(int(part))
    return ids


class Command(BaseCommand):
    help = ('Refresh sponsor draft + final profiles onto the current prompt '
            '(flag-gated; version-idempotent unless scoped via PROFILE_REFRESH_APP_IDS).')

    def handle(self, *args, **options):
        if not getattr(settings, 'CHECK2_AUTO_GENERATE', False):
            self.stdout.write('CHECK2_AUTO_GENERATE is off — nothing generated.')
            return

        only = _parse_ids(getattr(settings, 'PROFILE_REFRESH_APP_IDS', ''))
        force = bool(only)   # a targeted run refreshes even if already on the current prompt

        qs = (ScholarshipApplication.objects
              .filter(assigned_to__isnull=False, sponsor_profile__isnull=False)
              .select_related('sponsor_profile', 'profile').order_by('id'))
        if only:
            qs = qs.filter(id__in=only)

        drafted, finalised, skipped_edited, skipped_current = [], [], [], []
        draft_failed, final_failed, final_no_session = [], [], []
        seen = set()

        for app in qs:
            seen.add(app.id)
            sp = app.sponsor_profile
            if sp.edited_markdown:
                skipped_edited.append(app.id)          # never overwrite an officer's edits
                continue
            stale = sp.prompt_version != PROMPT_VERSION
            if not (force or stale):
                skipped_current.append(app.id)
                continue

            had_final = sp.finalised_at is not None     # capture BEFORE the re-draft

            # 1) draft (Flash)
            sp, err = generate_ready_profile(app)
            if err:
                draft_failed.append((app.id, err))
                continue
            drafted.append(app.id)

            # 2) final (Pro) — only for already-decided students, and only with a submitted
            #    interview to fold in (mirrors AdminFinaliseProfileView).
            if not had_final:
                continue
            session = (app.interview_sessions.filter(status='submitted')
                       .order_by('-submitted_at').first())
            if session is None or not sp.current_markdown.strip():
                final_no_session.append(app.id)
                continue
            result = refine_sponsor_profile(app, draft=sp.current_markdown, session=session)
            if 'error' in result:
                final_failed.append((app.id, result['error']))
                continue
            sp.final_markdown = result['markdown']
            sp.final_model_used = result.get('model_used', '')
            sp.prompt_version = result.get('prompt_version', '')
            sp.finalised_at = timezone.now()
            sp.save()
            finalised.append(app.id)

        not_found = sorted(only - seen) if only else []
        self.stdout.write(
            f'Refresh complete (prompt {PROMPT_VERSION}; force={force}). '
            f'drafted={drafted} finalised={finalised} '
            f'skipped_current={skipped_current} skipped_edited={skipped_edited} '
            f'final_no_session={final_no_session} '
            f'draft_failed={draft_failed} final_failed={final_failed} '
            f'requested_not_found={not_found}')
