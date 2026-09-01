"""Set (or clear) an organisation's stored colour theme — Layer 1 A1.

The WRITER for `OrganisationTheme` until A2 puts a picker in front of it. It exists so this sprint
ships no storage that nothing fills: the standing constraint on arc A is that forward-compatibility
must never take the shape of a reserved key waiting for a screen.

Report-only unless `--apply`, like every data command in this repo.

    python manage.py set_organisation_theme --org inspire --colour '#a21caf'
    python manage.py set_organisation_theme --org inspire --colour '#a21caf' --apply
    python manage.py set_organisation_theme --org inspire --clear --apply

⚠ IT REFUSES THE PLATFORM ORGANISATION. BrightPath's light ramp in `globals.css` is the seeded
brand hexes rather than `brand_ramp()`'s output, so a derived row would shift BrightPath's own
colours by a channel or two — a change nobody asked for, on the one tenant that is live.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.courses import theme_tokens
from apps.courses.models import OrganisationTheme, PartnerOrganisation

PLATFORM_ORG_CODE = 'brightpath'


class Command(BaseCommand):
    help = "Store an organisation's colour theme, derived from one brand colour."

    def add_arguments(self, parser):
        parser.add_argument('--org', required=True, help='Organisation code, e.g. inspire')
        parser.add_argument('--colour', help="Brand colour as 6-digit hex, e.g. '#a21caf'")
        parser.add_argument('--clear', action='store_true',
                            help='Remove the theme so the organisation falls back to the platform')
        parser.add_argument('--apply', action='store_true', help='Write. Default is report-only.')

    def handle(self, *args, **opts):
        code = (opts['org'] or '').strip()
        if code == PLATFORM_ORG_CODE:
            raise CommandError(
                'Refusing the platform organisation. Its ramp is the seeded hexes in globals.css, '
                'not a derived one — a row here would move BrightPath\'s own colours.'
            )
        org = PartnerOrganisation.objects.filter(code=code).first()
        if org is None:
            raise CommandError(f'No organisation with code {code!r}')

        existing = OrganisationTheme.objects.filter(organisation=org).first()

        if opts['clear']:
            return self._clear(org, existing, opts['apply'])

        colour = (opts.get('colour') or '').strip()
        if not colour:
            raise CommandError('Give --colour, or --clear')
        try:
            tokens = theme_tokens.tokens_from_colour(colour)
        except theme_tokens.ThemeTokenError as exc:
            raise CommandError(str(exc))

        self.stdout.write(f'{org.name} ({org.code})')
        self.stdout.write(f'  was: {existing.source_colour or "no theme" if existing else "no theme"}')
        self.stdout.write(f'  now: {colour}')
        for mode in theme_tokens.MODES:
            row = ', '.join(f'{k.split("-")[1]}={v}' for k, v in sorted(
                tokens[mode].items(), key=lambda kv: int(kv[0].split('-')[1])))
            self.stdout.write(f'  {mode}: {row}')

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('Report only. Re-run with --apply to write.'))
            return

        OrganisationTheme.objects.update_or_create(
            organisation=org, defaults={'source_colour': colour, 'tokens': tokens})
        self.stdout.write(self.style.SUCCESS(f'Theme stored for {org.code}.'))

    def _clear(self, org, existing, apply_it):
        if existing is None:
            self.stdout.write(f'{org.code} has no theme — nothing to clear.')
            return
        self.stdout.write(f'{org.code} would lose its theme (was {existing.source_colour or "hand-set"}) '
                          'and fall back to the platform colours.')
        if not apply_it:
            self.stdout.write(self.style.WARNING('Report only. Re-run with --apply to write.'))
            return
        existing.delete()
        self.stdout.write(self.style.SUCCESS(f'Theme cleared for {org.code}.'))
