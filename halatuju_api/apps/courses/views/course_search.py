"""The catalogue search: the field taxonomy and the browse / search page."""
from django.apps import apps
from django.db.models import Count, OuterRef, Subquery
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..bumiputera import search_bumiputera
from ..models import (
    Course,
    CourseInstitution,
    CourseRequirement,
    FieldTaxonomy,
    Institution,
    StpmCourse,
)
from ..pismp_taxonomy import ALIRAN_LABELS, aliran_of, ALIRAN_VALUES, classify_pismp
from ..ranking_engine import get_credential_priority
from ..serializers import FieldTaxonomySerializer
from ..tvet_families import TVET_PATHWAYS


# Sort priority for source types in search results (higher = sorted first)
SOURCE_TYPE_ORDER = {
    'ua': 5, 'matric': 4, 'stpm': 4, 'pismp': 3, 'poly': 2, 'kkom': 1,
}


def _tvet_pick_list(spm_visible, pathway_map):
    """The search filter's TVET pathways: iljtm + ilkbs always, mara / tvet_other only when a visible
    course has that pathway (Bumi Sprint F1)."""
    tvet_ids = spm_visible.filter(requirement__source_type='tvet').values_list('course_id', flat=True)
    present = {pathway_map.get(cid) for cid in tvet_ids}
    return [p for p in TVET_PATHWAYS if p in ('iljtm', 'ilkbs') or p in present]


class FieldListView(APIView):
    """
    GET /api/v1/fields/

    Returns the field taxonomy tree: 10 parent groups, each with child fields.
    Public endpoint for search filter dropdowns.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        groups = FieldTaxonomy.objects.filter(
            parent_key__isnull=True
        ).order_by('sort_order')
        serializer = FieldTaxonomySerializer(groups, many=True)
        return Response({
            'groups': serializer.data,
        })


class CourseSearchView(APIView):
    """
    GET /api/v1/courses/search/

    Browse and search the full course catalogue with filters.
    Public endpoint — no auth required.

    Query params:
      ?q=kejuruteraan          (text search on course name)
      &level=Diploma           (Course.level)
      &field=Teknologi Maklumat (Course.field / StpmCourse.field)
      &field_key=it-perisian   (FieldTaxonomy key — preferred over field)
      &source_type=poly        (CourseRequirement.source_type)
      &state=Selangor          (Institution.state via CourseInstitution)
      &qualification=SPM|STPM  (filter by qualification; empty = both)
      &bumiputera=1            (Bumi-only courses shown; `search_bumiputera`, Sprint B)
      &limit=24&offset=0       (pagination)
    """
    permission_classes = [AllowAny]

    def get(self, request):
        p = self._parse_params(request)
        pathway_map = getattr(apps.get_app_config('courses'), 'course_pathway_map', {})

        # Bumi Sprint D1: Bumiputera-only SPM courses only for a Bumi student — results and pick-lists.
        spm_visible = Course.objects.all()
        if not search_bumiputera(request.query_params):
            spm_visible = spm_visible.exclude(requirement__req_bumiputera=True)

        spm_results, spm_count = self._spm_rows(p, spm_visible, pathway_map)
        stpm_results, stpm_count = self._stpm_rows(request, p)

        # ── Merge, sort, paginate ─────────────────────────────────────
        total_count = spm_count + stpm_count
        all_results = spm_results + stpm_results

        # Sort: credential > source_type > merit > name
        all_results.sort(key=lambda r: (
            -get_credential_priority(r['course_name'], r.get('source_type', '')),
            -SOURCE_TYPE_ORDER.get(r['source_type'], 0),
            -(r['merit_cutoff'] or 0),
            r['course_name'],
        ))

        # Paginate the merged, sorted list
        paginated = all_results[p['offset']:p['offset'] + p['limit']]

        return Response({
            'courses': paginated,
            'total_count': total_count,
            'filters': self._filter_options(request, spm_visible, pathway_map),
        })

    @staticmethod
    def _parse_params(request):
        """The query string as a dict: the text filters, the qualification, the aliran and the page window."""
        params = request.query_params
        # Pagination
        try:
            limit = int(params.get('limit', 0)) or 10000
        except (ValueError, TypeError):
            limit = 24
        try:
            offset = max(int(params.get('offset', 0)), 0)
        except (ValueError, TypeError):
            offset = 0
        return {
            'q': params.get('q', '').strip(),
            'level': params.get('level', '').strip(),
            'field': params.get('field', '').strip(),
            'field_key': params.get('field_key', '').strip(),
            'source_type': params.get('source_type', '').strip(),
            'state': params.get('state', '').strip(),
            'qualification': params.get('qualification', '').strip().upper(),
            # PISMP-only facet: Aliran (school type). Applies to source_type='pismp' rows.
            'aliran': params.get('aliran', '').strip().lower(),
            'limit': limit,
            'offset': offset,
        }

    @staticmethod
    def _spm_rows(p, spm_visible, pathway_map):
        """The SPM-entry rows for the filters, and their count (after any post-query filter)."""
        q, level, field, field_key = p['q'], p['level'], p['field'], p['field_key']
        source_type, state, aliran = p['source_type'], p['state'], p['aliran']
        include_spm = p['qualification'] in ('', 'SPM')
        spm_results = []
        spm_count = 0

        # A level=="Ijazah Sarjana Muda" filter used to be treated as STPM-only,
        # which wrongly hid the SPM-entry PISMP degrees (also "Ijazah Sarjana Muda").
        # Only skip the SPM branch when the source_type filter is the STPM-university
        # one ('ua'); otherwise keep it so PISMP (source_type='pismp') still appears.
        if include_spm and level and level.lower() == 'ijazah sarjana muda' and source_type == 'ua':
            include_spm = False

        if include_spm:
            qs = spm_visible.select_related('requirement')

            if q:
                qs = qs.filter(course__icontains=q)
            if level:
                qs = qs.filter(level__iexact=level)
            if field_key:
                qs = qs.filter(field_key=field_key)
            elif field:
                qs = qs.filter(field__iexact=field)
            if source_type:
                # Map a TVET pathway filter (iljtm/ilkbs/mara/tvet_other) to tvet + post-filter
                if source_type in TVET_PATHWAYS:
                    qs = qs.filter(requirement__source_type='tvet')
                else:
                    qs = qs.filter(requirement__source_type=source_type)
            if state:
                qs = qs.filter(
                    offerings__institution__state__iexact=state
                ).distinct()

            spm_count = qs.count()

            # Subquery: primary institution (alphabetically first offering)
            first_offering = CourseInstitution.objects.filter(
                course=OuterRef('pk')
            ).order_by('institution__institution_name')

            courses_list = list(qs.annotate(
                institution_count=Count('offerings'),
                primary_institution_name=Subquery(
                    first_offering.values('institution__institution_name')[:1]
                ),
                primary_institution_state=Subquery(
                    first_offering.values('institution__state')[:1]
                ),
            ).order_by('course'))

            for c in courses_list:
                req = getattr(c, 'requirement', None)
                st = req.source_type if req else 'poly'
                merit_cutoff = req.merit_cutoff if req else None
                # Resolve TVET → iljtm/ilkbs using pathway map
                pt = pathway_map.get(c.course_id, st)
                # If filtering by a TVET pathway, skip courses that don't match
                if source_type in TVET_PATHWAYS and pt != source_type:
                    continue
                # PISMP facets (Aliran / Elektif) derived at read-time.
                pismp = classify_pismp(c.course_id, c.course) if st == 'pismp' else None
                # Aliran filter narrows PISMP rows only (no-op for other source types).
                if aliran and (pismp is None or pismp['aliran'] != aliran):
                    continue
                spm_results.append({
                    'course_id': c.course_id,
                    'course_name': c.course,
                    'level': c.level,
                    'field': c.field,
                    'field_key': c.field_key_id or '',
                    'source_type': st,
                    'pathway_type': pt,
                    'merit_cutoff': merit_cutoff,
                    'institution_count': c.institution_count,
                    'institution_name': c.primary_institution_name or '',
                    'institution_state': c.primary_institution_state or '',
                    'qualification': 'SPM',
                    'aliran': pismp['aliran'] if pismp else None,
                    'is_elektif': pismp['is_elektif'] if pismp else False,
                })

            # Adjust count if a post-query filter (iljtm/ilkbs or aliran) removed rows
            if source_type in TVET_PATHWAYS or aliran:
                spm_count = len(spm_results)
        return spm_results, spm_count

    @staticmethod
    def _stpm_rows(request, p):
        """The STPM degree rows for the filters, and their count."""
        q, level, field, field_key = p['q'], p['level'], p['field'], p['field_key']
        source_type, state, aliran = p['source_type'], p['state'], p['aliran']
        include_stpm = p['qualification'] in ('', 'STPM')
        stpm_results = []
        stpm_count = 0

        # Aliran is a PISMP-only facet — an aliran filter excludes STPM degrees.
        if include_stpm and aliran:
            include_stpm = False
        # Skip STPM if level filter doesn't match
        if include_stpm and level and level.lower() != 'ijazah sarjana muda':
            include_stpm = False
        # Skip STPM if source_type filter doesn't match
        if include_stpm and source_type and source_type.lower() != 'ua':
            include_stpm = False
        if include_stpm:
            stpm_qs = StpmCourse.objects.select_related('requirement', 'institution').filter(is_active=True)

            # Bumiputera-only courses: only for a student who says they are Bumi (Sprint B).
            if not search_bumiputera(request.query_params):
                stpm_qs = stpm_qs.exclude(requirement__req_bumiputera=True)

            if q:
                stpm_qs = stpm_qs.filter(course_name__icontains=q)
            if field_key:
                stpm_qs = stpm_qs.filter(field_key=field_key)
            elif field:
                stpm_qs = stpm_qs.filter(field__iexact=field)
            if state:
                stpm_qs = stpm_qs.filter(institution__state__iexact=state)

            stpm_count = stpm_qs.count()

            for sc in stpm_qs.order_by('course_name'):
                stpm_results.append({
                    'course_id': sc.course_id,
                    'course_name': sc.course_name,
                    'level': 'Ijazah Sarjana Muda',
                    'field': sc.field or '',
                    'field_key': sc.field_key_id or '',
                    'source_type': 'ua',
                    'merit_cutoff': sc.merit_score,
                    'institution_count': 1,
                    'institution_name': sc.university,
                    'institution_state': sc.institution.state if sc.institution else '',
                    'qualification': 'STPM',
                })
        return stpm_results, stpm_count

    @staticmethod
    def _filter_options(request, spm_visible, pathway_map):
        """The dynamic filter pick-lists, built from the full catalogue this student can see."""
        spm_levels = list(
            spm_visible.values_list('level', flat=True)
            .distinct().order_by('level')
        )
        # Sprint B: the STPM pick-lists offer only what this student's search can return.
        stpm_visible = StpmCourse.objects.filter(is_active=True)
        if not search_bumiputera(request.query_params):
            stpm_visible = stpm_visible.exclude(requirement__req_bumiputera=True)
        stpm_levels = ['Ijazah Sarjana Muda'] if stpm_visible.exists() else []
        all_levels = sorted(set(spm_levels + stpm_levels))

        spm_field_keys = list(
            spm_visible.exclude(field_key__isnull=True)
            .values_list('field_key', flat=True)
            .distinct()
        )
        stpm_field_keys = list(
            stpm_visible.exclude(field_key__isnull=True)
            .values_list('field_key', flat=True)
            .distinct()
        )
        all_field_keys = sorted(set(spm_field_keys + stpm_field_keys))

        # Legacy: keep fields list for backward compatibility
        spm_fields = list(
            spm_visible.exclude(field='')
            .values_list('field', flat=True)
            .distinct().order_by('field')
        )
        stpm_fields = list(
            stpm_visible.exclude(field='')
            .values_list('field', flat=True)
            .distinct().order_by('field')
        )
        all_fields = sorted(set(spm_fields + stpm_fields))

        spm_source_types = list(
            CourseRequirement.objects.filter(course__in=spm_visible).values_list('source_type', flat=True)
            .distinct().order_by('source_type')
        )
        if 'tvet' in spm_source_types:   # shown as its pathways (Bumi Sprint F1)
            spm_source_types.remove('tvet')
            spm_source_types.extend(_tvet_pick_list(spm_visible, pathway_map))
        stpm_source_types = []
        all_source_types = sorted(set(spm_source_types + stpm_source_types))

        # PISMP Aliran options (derived) — only the school types actually present.
        pismp_names = spm_visible.filter(
            requirement__source_type='pismp'
        ).values_list('course_id', 'course')
        present_alirans = {aliran_of(name, cid) for cid, name in pismp_names}
        alirans = [
            {'value': a, 'label': ALIRAN_LABELS[a]}
            for a in ALIRAN_VALUES if a in present_alirans
        ]

        return {
            'levels': all_levels,
            'fields': all_fields,
            'field_keys': all_field_keys,
            'source_types': all_source_types,
            'alirans': alirans,
            'states': sorted(
                Institution.objects.exclude(state='')
                .values_list('state', flat=True)
                .distinct().order_by('state')
            ),
            'qualifications': ['SPM', 'STPM'],
        }
