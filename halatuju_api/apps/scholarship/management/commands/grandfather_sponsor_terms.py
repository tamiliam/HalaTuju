# -*- coding: utf-8 -*-
"""Record that existing sponsors were deliberately NOT asked to accept a terms version.

The owner's eight are friends and family who gave before any terms existed, so asking them to
accept retrospectively would be theatre. But one or two should go through it for real, to see how
it feels — hence `--except`.

⚠ This writes `basis='grandfathered'`, which means *we did not ask this person*. It is the OPPOSITE
of an acceptance and every surface must say so: `accepted_at` stays NULL and `signed_name` stays
blank. TD-186 exists because a consent record once claimed more than it could show; this must not
repeat that.

The gate rule stays single — *an active version exists and this sponsor has no row for it* — so
grandfathering is data rather than a branch, and it is reversible in one row: delete a
grandfather row and that sponsor is asked on their next sign-in. No deploy, no flag.

⚠ Publishing a NEW version re-asks EVERYONE, grandfathered included, because a new version has no
rows at all. That is the right default for a material change, but it means grandfathering must be
re-granted deliberately — run this again — rather than being inherited.
"""
from django.core.management.base import BaseCommand

from apps.scholarship import sponsor_terms
from apps.scholarship.models import Sponsor, SponsorTermsAcceptance, SponsorTermsVersion


class Command(BaseCommand):
    help = 'Grandfather existing sponsors past a terms version (they are never asked).'

    def add_arguments(self, parser):
        # NOT --version: Django's BaseCommand already defines that, and argparse raises on the
        # collision rather than shadowing it.
        parser.add_argument('--terms-version', dest='terms_version', default='',
                            help='Version string. Defaults to the currently ACTIVE version.')
        parser.add_argument('--reason', default='Pre-dates the terms.',
                            help='Recorded on every row, so a later reader knows why.')
        parser.add_argument('--by', default='', help='Admin email granting the exemption.')
        parser.add_argument('--except', dest='excluded', default='',
                            help='Comma-separated emails to LEAVE OUT — the pilot testers, who '
                                 'will meet the wizard on their next sign-in.')
        parser.add_argument('--apply', action='store_true',
                            help='Actually write. Without this it is a dry run.')

    def handle(self, *args, **opts):
        if opts['terms_version']:
            terms = SponsorTermsVersion.objects.filter(version=opts['terms_version']).first()
        else:
            terms = sponsor_terms.active_version()
        if terms is None:
            self.stdout.write(self.style.ERROR(
                'No such version (and no active version). Publish one first, or pass --version.'))
            return

        excluded = {e.strip().lower() for e in opts['excluded'].split(',') if e.strip()}
        already = set(SponsorTermsAcceptance.objects
                      .filter(terms=terms).values_list('sponsor_id', flat=True))

        exempt, pilot, skipped = [], [], []
        for sponsor in Sponsor.objects.order_by('id'):
            if sponsor.id in already:
                skipped.append(sponsor)
            elif (sponsor.email or '').strip().lower() in excluded:
                pilot.append(sponsor)
            else:
                exempt.append(sponsor)

        self.stdout.write(f'Version {terms.version} ({terms.status}).')
        self.stdout.write(f'  Would grandfather : {len(exempt)}')
        for s in exempt:
            self.stdout.write(f'      {s.id:>4}  {s.email}  {s.name}')
        self.stdout.write(self.style.WARNING(
            f'  WILL BE ASKED     : {len(pilot)}   <- the pilot'))
        for s in pilot:
            self.stdout.write(f'      {s.id:>4}  {s.email}  {s.name}')
        if skipped:
            self.stdout.write(f'  Already has a row : {len(skipped)}')

        # An --except address that matches nobody is almost certainly a typo, and the cost of
        # missing it is that the person you wanted to pilot with is silently exempted instead.
        unmatched = excluded - {(s.email or '').strip().lower() for s in pilot}
        if unmatched:
            self.stdout.write(self.style.ERROR(
                '  --except matched no sponsor: ' + ', '.join(sorted(unmatched))))

        if not opts['apply']:
            self.stdout.write(self.style.WARNING(
                'DRY RUN — nothing written. Re-run with --apply once the two lists look right.'))
            return

        written = 0
        for sponsor in exempt:
            _row, created = sponsor_terms.grandfather(
                sponsor, terms, by_email=opts['by'], reason=opts['reason'])
            written += 1 if created else 0
        self.stdout.write(self.style.SUCCESS(
            f'Wrote {written} grandfather rows. {len(pilot)} sponsors will be asked.'))
        self.stdout.write('Delete a row to add someone to the pilot; no deploy needed.')
