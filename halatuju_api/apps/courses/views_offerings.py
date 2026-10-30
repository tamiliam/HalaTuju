"""GET /api/v1/courses/offerings/?pathway=<key> — WHERE each course of one pathway is taught.

Scholarship "My Plans" redesign, 2026-10-30 (owner rulings). The scholarship pickers ask the
student to NAME the place she holds an offer for, institution first, then course — so the browser
needs, for one pathway, the institutions (id, name, state) and the courses each one offers. No
other endpoint returns that: `/courses/search/` is course-level (one "primary" institution and a
count), and `/stpm/search/` hides inactive degrees.

⚠ UNFILTERED ON PURPOSE, AND READ-ONLY. Every course of the pathway is served — Bumiputera-only
ones included (Option A, decisions.md 2026-10-28) and inactive ones included (a student already
enrolled may hold a place on a course MOHE no longer lists). Nothing here reads a student, a token
or a result: it is public catalogue data, the same rows `/courses/search/?bumiputera=1` already
serves. Narrowing to "courses I qualify for" is the browser's opt-in switch, built on the
eligibility endpoints, never this one. The course guide does not call this.

Shape (one pathway per call, so a picker downloads only what it draws):

    {"pathway": "poly",
     "institutions": [{"id", "institution_id", "name", "state", "course_ids": [...]}],
     "courses": [{"course_id", "course_name", "field_key", "aliran"}]}

`id` is the grouping key the browser uses; `institution_id` is the real `Institution` key ('' for
an STPM degree whose university is not linked). `name` is the CATALOGUE spelling — exactly what
`offer_pathway._campus_rows` compares an offer letter against (`Institution.institution_name` for
the SPM catalogue, `StpmCourse.university` for degrees, e.g. "Universiti Teknologi MARA").
`aliran` is set for PISMP rows only (school type, `pismp_taxonomy`).
"""
from django.apps import apps
from django.utils.cache import patch_cache_control
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .pismp_taxonomy import aliran_of

#: The SPM-entry pathways a programme picker asks for (pre-U `matric` / `stpm` use fixed college
#: and school lists in the browser), plus `degree`: the STPM degree catalogue, for STPM and
#: third-route holders.
SPM_PATHWAYS = ('asasi', 'university', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs', 'mara', 'tvet_other')
DEGREE = 'degree'
OFFERING_PATHWAYS = SPM_PATHWAYS + (DEGREE,)

#: Catalogue data changes only on an ingest; a browser may keep an answer for an hour.
MAX_AGE_SECONDS = 3600


def _spm_offerings(pathway):
    """The SPM catalogue's courses whose pathway is `pathway`, and where each is taught."""
    from .models import Course, CourseInstitution
    config = apps.get_app_config('courses')
    config.ensure_data()   # TD-047: a failed boot load leaves the pathway map empty; retry it once
    pathway_map = getattr(config, 'course_pathway_map', {}) or {}
    ids = [cid for cid, pt in pathway_map.items() if pt == pathway]
    courses = []
    for cid, name, field_key in (Course.objects.filter(course_id__in=ids)
                                 .order_by('course').values_list('course_id', 'course', 'field_key')):
        courses.append({
            'course_id': cid, 'course_name': name, 'field_key': field_key or '',
            'aliran': aliran_of(name, cid) if pathway == 'pismp' else None,
        })
    by_inst = {}
    rows = (CourseInstitution.objects.filter(course_id__in=[c['course_id'] for c in courses])
            .order_by('institution__institution_name', 'course_id')
            .values_list('institution_id', 'institution__institution_name', 'institution__state',
                         'course_id'))
    for iid, name, state, cid in rows:
        inst = by_inst.setdefault(iid, {'id': iid, 'institution_id': iid, 'name': (name or '').strip(),
                                        'state': state or '', 'course_ids': []})
        inst['course_ids'].append(cid)
    return list(by_inst.values()), courses


def _degree_offerings():
    """Every STPM degree — inactive included — grouped by the university the catalogue names."""
    from .models import StpmCourse
    courses, by_uni = [], {}
    rows = (StpmCourse.objects.select_related('institution').order_by('course_name', 'course_id'))
    for sc in rows:
        uni = (sc.university or '').strip()
        courses.append({'course_id': sc.course_id, 'course_name': sc.course_name,
                        'field_key': sc.field_key_id or '', 'aliran': None})
        if not uni:
            continue
        inst = by_uni.setdefault(uni, {
            'id': sc.institution_id or uni, 'institution_id': sc.institution_id or '', 'name': uni,
            'state': sc.institution.state if sc.institution else '', 'course_ids': []})
        inst['course_ids'].append(sc.course_id)
    institutions = sorted(by_uni.values(), key=lambda i: i['name'])
    return institutions, courses


class PathwayOfferingsView(APIView):
    """GET /api/v1/courses/offerings/?pathway=poly — see the module docstring."""
    permission_classes = [AllowAny]

    def get(self, request):
        pathway = (request.query_params.get('pathway') or '').strip().lower()
        if pathway not in OFFERING_PATHWAYS:
            return Response({'error': 'unknown_pathway', 'pathways': list(OFFERING_PATHWAYS)},
                            status=status.HTTP_400_BAD_REQUEST)
        institutions, courses = _degree_offerings() if pathway == DEGREE else _spm_offerings(pathway)
        response = Response({'pathway': pathway, 'institutions': institutions, 'courses': courses})
        # An empty list is a fault (every pathway has courses), never an answer worth keeping for an
        # hour: a public cache would serve a student nothing to pick long after the data came back.
        if courses:
            patch_cache_control(response, public=True, max_age=MAX_AGE_SECONDS)
        else:
            patch_cache_control(response, no_store=True)
        return response
