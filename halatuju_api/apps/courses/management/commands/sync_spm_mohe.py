"""
Sync the MOHE-coded (UA/Asasi) subset of the post-SPM course catalogue from a scraped CSV.

Mirrors sync_stpm_mohe, but for the SPM-side `Course` catalogue — with one critical restriction.

WHY THE RESTRICTION: only the post-SPM courses whose ``course_id`` IS a MOHE/UPU KOD PROGRAM
(two letters + seven digits, e.g. ``UK0010001`` — the UA/Asasi programmes) can be diffed against
an ePanduan ``jenprog=spm`` scrape. The rest of the `courses` catalogue uses INTERNAL synthetic
schemes the portal never emits — ``POLY-*`` (Politeknik), ``KKOM-*`` (Kolej Komuniti), ``IKBN-*``
/ ``ILP-*`` (TVET), numeric ``50PD…`` (PISMP). If those were compared against the scrape they
would ALL look "removed" and trip the mass-deactivation guard. So this command EXCLUDES them
from the comparison entirely — they are never matched, never deactivated, never touched. Bridging
them needs a name/institution crosswalk (a separate, riskier sprint — see the course-data roadmap).

What it does on the MOHE-coded subset (both sides filtered to KOD PROGRAM):
1. Reports new programmes (in the scrape, not in DB) — NOT auto-added (requirements must be
   parsed first; same policy as sync_stpm_mohe).
2. Reports + (on --apply) deactivates removed programmes / reactivates returned ones,
   behind the same mass-deactivation safety guard.
3. Reports + (on --apply) updates the merit cut-off (CourseRequirement.merit_cutoff) when it moves.

It does NOT touch any read path — deactivated SPM courses still render until a later sprint
wires an is_active filter (see the Course.is_active docstring), so the golden master is unaffected.

Usage:
    python manage.py scrape_mohe_stpm --jenprog spm --category A --output data/spm/mohe_latest.csv
    python manage.py sync_spm_mohe --csv data/spm/mohe_latest.csv            # dry run
    python manage.py sync_spm_mohe --csv data/spm/mohe_latest.csv --apply
"""
import csv
import re

from django.core.management.base import BaseCommand, CommandError

from apps.courses.models import Course

# A MOHE/UPU KOD PROGRAM: two uppercase letters then seven digits (e.g. UK0010001, UR4521002).
MOHE_CODE_RE = re.compile(r'^[A-Z]{2}[0-9]{7}$')

# Safety guard for --apply (mirrors sync_stpm_mohe): refuse a mass deactivation that almost
# always signals a partial/failed scrape rather than real removals. Scoped to the MOHE-coded
# subset, since that is the only set this command can deactivate.
GUARD_MIN_ACTIVE = 50           # below this the subset is too small to guard (tests / fresh DB)
MAX_DEACTIVATE_FRACTION = 0.10  # abort --apply if it would deactivate more than this share


def is_mohe_coded(course_id):
    """True when course_id is a MOHE/UPU KOD PROGRAM the ePanduan scrape can match."""
    return bool(MOHE_CODE_RE.match(course_id or ''))


class Command(BaseCommand):
    help = 'Sync the MOHE-coded (UA/Asasi) subset of the SPM course catalogue from a scraped CSV'

    def add_arguments(self, parser):
        parser.add_argument('--csv', type=str, required=True, help='Path to scraped CSV')
        parser.add_argument('--apply', action='store_true', help='Apply changes (default: report only)')
        parser.add_argument(
            '--force', action='store_true',
            help='Override the mass-deactivation safety guard (only after verifying a large removal is real).')

    def handle(self, *args, **options):
        csv_path = options['csv']
        apply = options['apply']
        force = options['force']

        # Load scraped data, keeping ONLY MOHE-coded rows (the rest of the spm scrape is
        # Poly/KK programmes whose codes we don't store under KOD PROGRAM — out of scope here).
        scraped = {}
        scraped_total = 0
        scraped_dropped = 0
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                cid = (row.get('course_id') or '').strip()
                if not cid:
                    continue
                scraped_total += 1
                if is_mohe_coded(cid):
                    scraped[cid] = row
                else:
                    scraped_dropped += 1

        # Load the DB catalogue, restricting to the MOHE-coded subset (filtered in Python so we
        # don't depend on a DB-specific regex operator). Pull the requirement for merit compare.
        db_courses = {
            c.course_id: c
            for c in Course.objects.select_related('requirement').all()
            if is_mohe_coded(c.course_id)
        }

        db_ids = set(db_courses.keys())
        mohe_ids = set(scraped.keys())

        new_ids = mohe_ids - db_ids
        removed_ids = db_ids - mohe_ids
        common_ids = db_ids & mohe_ids

        active_removed = [cid for cid in removed_ids if db_courses[cid].is_active]
        active_before = sum(1 for c in db_courses.values() if c.is_active)
        inactive_count = sum(1 for c in db_courses.values() if not c.is_active)

        self.stdout.write('\n=== SPM MOHE Sync Report (MOHE-coded UA/Asasi subset only) ===')
        self.stdout.write(f'Scraped rows (total):        {scraped_total}')
        self.stdout.write(
            f'  of which MOHE-coded:       {len(mohe_ids)} '
            f'(dropped {scraped_dropped} non-MOHE-coded Poly/KK rows — out of scope, see docstring)'
        )
        self.stdout.write(f'DB MOHE-coded courses:       {len(db_ids)}')
        self.stdout.write(f'Matched:                     {len(common_ids)}')
        self.stdout.write(f'Currently inactive (subset): {inactive_count}')

        # New programmes (report only — never auto-added; requirements must be parsed first).
        if new_ids:
            self.stdout.write(self.style.WARNING(f'\n--- NEW ({len(new_ids)}) — reported, NOT added ---'))
            for cid in sorted(new_ids):
                row = scraped[cid]
                self.stdout.write(f'  + {cid}: {row.get("course_name", "")} ({row.get("university", "")})')

        # Removed programmes (MOHE-coded, in DB, no longer in the scrape).
        if removed_ids:
            already_inactive = [cid for cid in removed_ids if not db_courses[cid].is_active]
            if active_removed:
                self.stdout.write(self.style.ERROR(
                    f'\n--- REMOVED — will deactivate ({len(active_removed)}) ---'
                ))
                for cid in sorted(active_removed):
                    self.stdout.write(f'  - {cid}: {db_courses[cid].course}')
            if already_inactive:
                self.stdout.write(f'\n  ({len(already_inactive)} already inactive, unchanged)')

        # Reactivation candidates (MOHE-coded, back in the scrape, currently inactive).
        reactivate_ids = [cid for cid in common_ids if not db_courses[cid].is_active]
        if reactivate_ids:
            self.stdout.write(self.style.SUCCESS(f'\n--- REACTIVATE ({len(reactivate_ids)}) ---'))
            for cid in sorted(reactivate_ids):
                self.stdout.write(f'  ↑ {cid}: {db_courses[cid].course}')

        # Merit changes (SPM merit lives in CourseRequirement.merit_cutoff, not on Course).
        merit_changes = []
        for cid in common_ids:
            new_merit = self._parse_merit(scraped[cid].get('merit'))
            if new_merit is None:
                continue
            req = getattr(db_courses[cid], 'requirement', None)
            old_merit = req.merit_cutoff if req else None
            if old_merit is None or abs(new_merit - old_merit) > 0.01:
                merit_changes.append((cid, old_merit, new_merit))

        if merit_changes:
            self.stdout.write(self.style.WARNING(f'\n--- MERIT CHANGES ({len(merit_changes)}) ---'))
            for cid, old, new in sorted(merit_changes):
                old_s = f'{old:.2f}%' if old is not None else '(none)'
                self.stdout.write(f'  ~ {cid}: {old_s} -> {new:.2f}%')

        # --- Apply ---
        if not apply:
            self.stdout.write(self.style.NOTICE('\nDry run. Use --apply to write changes to DB.'))
            return

        # SAFETY GUARD — block a catalogue-wiping apply from a partial/failed scrape.
        if not force and active_before >= GUARD_MIN_ACTIVE and active_removed:
            frac = len(active_removed) / active_before
            if frac > MAX_DEACTIVATE_FRACTION:
                raise CommandError(
                    f'Refusing to apply: this would deactivate {len(active_removed)} of '
                    f'{active_before} active MOHE-coded courses ({frac:.0%}), from a scrape of only '
                    f'{len(mohe_ids)} MOHE-coded programmes. That looks like a partial or failed '
                    f'scrape (e.g. a MOHE site change), not real removals. Re-scrape and verify, '
                    f'or pass --force if the removals are genuinely correct.'
                )

        # Deactivate removed.
        if active_removed:
            deactivated = Course.objects.filter(course_id__in=active_removed).update(is_active=False)
            self.stdout.write(self.style.WARNING(f'\nDeactivated {deactivated} removed courses'))

        # Reactivate returned.
        if reactivate_ids:
            reactivated = Course.objects.filter(course_id__in=reactivate_ids).update(is_active=True)
            self.stdout.write(self.style.SUCCESS(f'Reactivated {reactivated} returned courses'))

        # Apply merit updates (the one field a refresh genuinely changes for these courses).
        merit_applied = 0
        for cid, _old, new in merit_changes:
            req = getattr(db_courses[cid], 'requirement', None)
            if req is not None:
                req.merit_cutoff = new
                req.save(update_fields=['merit_cutoff'])
                merit_applied += 1
        if merit_applied:
            self.stdout.write(self.style.SUCCESS(f'Updated {merit_applied} merit cut-offs'))

        if new_ids:
            self.stdout.write(self.style.WARNING(
                f'\n{len(new_ids)} new programmes detected. These need manual review — '
                'requirements must be parsed before adding to DB (not auto-added).'
            ))

    @staticmethod
    def _parse_merit(raw):
        """Parse the scraped merit string ('85.50') to a float, or None if absent/unparseable."""
        if not raw:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None
