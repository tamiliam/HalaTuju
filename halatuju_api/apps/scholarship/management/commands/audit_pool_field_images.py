"""Read-only coverage audit for the sponsor-pool field artwork (redesign deliverable).

For the current pool + recently-pooled applications it resolves each card's
``field_image_slug`` via the SAME catalogue-first chain the serializer uses, records which
branch (a)/(b)/(c) resolved it, and HEAD-checks each DISTINCT slug's URL in the public
``field-images`` bucket. NO writes, NO image generation — art gaps are reported for an
owner-approved follow-up.

    python manage.py audit_pool_field_images
"""
import urllib.request

from django.core.management.base import BaseCommand

from apps.scholarship import pool
from apps.scholarship.models import ScholarshipApplication

BUCKET = 'https://pbrrlyoyyiftckqvzvvo.supabase.co/storage/v1/object/public/field-images'
GENERIC = 'umum-kemanusiaan'


def _resolve_with_branch(app, tax, course_fk):
    """Return (slug, branch) — branch in {'a','b','c'} — mirroring
    serializers._resolve_field_image_slug but reporting which rule fired."""
    from apps.courses.models import Course
    cp = getattr(app, 'chosen_programme', None)
    if isinstance(cp, dict):
        course_id = (cp.get('course_id') or '').strip()
        if course_id:
            if course_id not in course_fk:
                course_fk[course_id] = (Course.objects.filter(course_id=course_id)
                                        .values_list('field_key_id', flat=True).first())
            fk = course_fk[course_id]
            if fk and tax.get(fk):
                return tax[fk], 'a'
    fos = (app.field_of_study or '').strip()
    if fos and tax.get(fos):
        return tax[fos], 'b'
    return '', 'c'


class Command(BaseCommand):
    help = 'Read-only: audit sponsor-pool field-image slug coverage (no writes).'

    def handle(self, *args, **opts):
        from apps.courses.models import FieldTaxonomy
        tax = dict(FieldTaxonomy.objects.values_list('key', 'image_slug'))
        course_fk = {}

        # Current pool ∪ anyone ever pooled (has a generated anon profile).
        ids = set(pool.eligible_pool_queryset(ScholarshipApplication).values_list('id', flat=True))
        ids |= set(ScholarshipApplication.objects
                   .filter(sponsor_profile__isnull=False)
                   .values_list('id', flat=True))
        apps = (ScholarshipApplication.objects.filter(id__in=ids)
                .select_related('profile'))

        branch_counts = {'a': 0, 'b': 0, 'c': 0}
        slug_usage = {}   # resolved slug (or '' → generic) -> count
        for app in apps:
            slug, branch = _resolve_with_branch(app, tax, course_fk)
            branch_counts[branch] += 1
            effective = slug or GENERIC   # frontend falls back to the generic art
            slug_usage[effective] = slug_usage.get(effective, 0) + 1

        self.stdout.write(f'Applications audited: {len(apps)}')
        self.stdout.write(f'Resolved via (a) course→field_key: {branch_counts["a"]}')
        self.stdout.write(f'Resolved via (b) field_of_study key: {branch_counts["b"]}')
        self.stdout.write(f'Fell through to (c) generic art:     {branch_counts["c"]}')
        self.stdout.write(f'Distinct effective slugs: {len(slug_usage)}')

        missing = []
        for slug in sorted(slug_usage):
            url = f'{BUCKET}/{slug}.png'
            ok = self._head_ok(url)
            mark = 'OK ' if ok else '404'
            self.stdout.write(f'  [{mark}] {slug}  (x{slug_usage[slug]})')
            if not ok:
                missing.append(slug)

        if missing:
            self.stdout.write(self.style.WARNING(
                f'MISSING artwork ({len(missing)}): ' + ', '.join(missing)))
        else:
            self.stdout.write(self.style.SUCCESS('All resolved slugs exist in the bucket.'))

    def _head_ok(self, url):
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req, timeout=15) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False
