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

from apps.courses import theme_tokens, theme_versions
from apps.courses.models import PartnerOrganisation

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

        existing = theme_versions.active_for(org)

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

        # ⚠ THE COMMAND PUBLISHES IMMEDIATELY; THE SCREEN DOES NOT (Layer 1 A3). A3 made the screen
        # a draft-then-publish flow so a colour change is never a live experiment on applicants.
        # This is the operator's path — run deliberately, from a shell, by somebody who has just
        # read the ten shades printed above — so it does what it has always done and sets the live
        # colour in one step. The previous version is ARCHIVED, not overwritten, so
        # `--clear` (a revert) still puts it back.
        theme_versions.save_draft(org, colour, tokens)
        theme_versions.publish(org, by_email='set_organisation_theme', allowed=True)
        self.stdout.write(self.style.SUCCESS(f'Theme published for {org.code}.'))

    def _clear(self, org, existing, apply_it):
        """`--clear` is now a REVERT, not a delete (Layer 1 A3).

        Deleting the live row would throw away the history that makes Revert work at all. A revert
        archives what is live and re-activates whatever was live before it — which for an
        organisation on its FIRST colour means the platform stylesheet, the same outcome the delete
        used to give.
        """
        if existing is None:
            self.stdout.write(f'{org.code} has no live theme — nothing to clear.')
            return
        previous = theme_versions.previous_for(org)
        goes_to = (previous.source_colour if previous else '') or 'the platform colours'
        self.stdout.write(f'{org.code} would go back from '
                          f'{existing.source_colour or "hand-set"} to {goes_to}.')
        if not apply_it:
            self.stdout.write(self.style.WARNING('Report only. Re-run with --apply to write.'))
            return
        theme_versions.revert(org, by_email='set_organisation_theme', allowed=True)
        self.stdout.write(self.style.SUCCESS(f'{org.code} reverted to {goes_to}.'))
