"""`GET /api/v1/health/` — is this instance able to answer an eligibility check? (TD-047)

⚠ DELIBERATELY TINY. No authentication, no data beyond two fields, no database query, no new
dependency. It reads the in-process course frame the startup load (and the lazy retry in
`CoursesConfig.ensure_data`) fill, and says whether it is there:

    200 {"status": "ok",       "course_data_loaded": true}
    503 {"status": "degraded", "course_data_loaded": false}

It does NOT itself retry the load: an unauthenticated route must never be a way to make the
service hit the database. The retry is the eligibility request's job.

⚠ Nothing calls it yet. Wiring it into a Cloud Run startup/liveness probe is a production step.
"""
from django.apps import apps
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def health(request):
    loaded = apps.get_app_config('courses').data_loaded()
    return JsonResponse({'status': 'ok' if loaded else 'degraded', 'course_data_loaded': loaded},
                        status=200 if loaded else 503)
