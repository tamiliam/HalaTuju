"""One-off / occasional backfill: generate the DRAFT sponsor profile for applications
that have been handed off to a reviewer (``assigned_to`` set) but whose draft never got
generated — e.g. students assigned BEFORE ``CHECK2_AUTO_GENERATE`` was switched on, since
the auto-draft fires only at the moment of first assignment.

Billable (one Gemini Flash call per student). Dry-run by default; pass --apply to write.
Never overwrites an officer-edited draft unless --force.

    python manage.py backfill_assigned_profiles            # dry run — show what would generate
    python manage.py backfill_assigned_profiles --apply    # generate the missing ones
    python manage.py backfill_assigned_profiles --apply --regenerate   # also refresh existing (non-edited) drafts
    python manage.py backfill_assigned_profiles --apply --ids 4,9,10   # only these application ids
"""
from django.core.management.base import BaseCommand

from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.services import generate_ready_profile


class Command(BaseCommand):
    help = 'Generate the draft sponsor profile for assigned applications that lack one.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write (else dry run).')
        parser.add_argument('--regenerate', action='store_true',
                            help='Also regenerate existing (non-edited) drafts.')
        parser.add_argument('--force', action='store_true',
                            help='Regenerate even an officer-EDITED draft (default: skip).')
        parser.add_argument('--ids', default='', help='Comma-separated application ids to limit to.')

    def handle(self, *args, **opts):
        qs = (ScholarshipApplication.objects
              .filter(assigned_to__isnull=False)
              .select_related('sponsor_profile', 'profile')
              .order_by('id'))
        if opts['ids']:
            ids = [int(x) for x in opts['ids'].split(',') if x.strip()]
            qs = qs.filter(id__in=ids)

        targets, skipped = [], []
        for app in qs:
            sp = getattr(app, 'sponsor_profile', None)
            has_content = bool(sp and (sp.draft_markdown or sp.final_markdown))
            edited = bool(sp and sp.edited_markdown)
            if has_content and not opts['regenerate']:
                skipped.append((app.id, 'already has a profile'))
            elif edited and not opts['force']:
                skipped.append((app.id, 'officer-edited — use --force to overwrite'))
            else:
                targets.append(app)

        self.stdout.write(f'Assigned apps scanned: {qs.count()}')
        for aid, why in skipped:
            self.stdout.write(f'  skip #{aid}: {why}')
        self.stdout.write(f'To generate: {[a.id for a in targets]}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('DRY RUN — pass --apply to generate (billable).'))
            return

        ok, fail = [], []
        for app in targets:
            sp, err = generate_ready_profile(app)
            if err:
                fail.append((app.id, err))
                self.stdout.write(self.style.ERROR(f'  #{app.id}: {err}'))
            else:
                ok.append(app.id)
                self.stdout.write(self.style.SUCCESS(f'  #{app.id}: generated ({sp.model_used})'))
        self.stdout.write(self.style.SUCCESS(f'Done. Generated {len(ok)}: {ok}. Failed {len(fail)}: {fail}'))
