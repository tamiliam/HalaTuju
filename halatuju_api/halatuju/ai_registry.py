"""Every job on this platform that calls an AI model, and which model it is set to.

⚠ **THIS RESOLVES; IT NEVER RECORDS.** An entry names the JOB and HOW its model is chosen — a
Django setting, a named cascade, or a literal in the source — and `resolve` reads that source
live at the moment of asking. A registry that stored its own copy of "gemini-2.5-pro" would be a
second source of truth, and it would be wrong the first time somebody changed the setting without
opening this file. The screen may only ever show what the engine would actually use.

⚠ **IT IS AN UPGRADE CHECKLIST, NOT A SNAPSHOT**, and `test_ai_registry.py` is what keeps it one:
that test COUNTS the AI seams in the codebase and fails if a job meters a model without appearing
here. Written as a count rather than a name-grep on purpose — a guard that greps for a module name
is satisfied by the import line (lessons.md, 2026-09-07).

⚠ **NOTHING HERE CHOOSES A MODEL.** This module is read-only reporting. Changing what a job runs on
still means changing its setting or its cascade, exactly as before. An organisation cannot pick its
own model, and that is a decision rather than an omission — see `docs/decisions.md`, 2026-09-11.

Lives at project level rather than in an app because the jobs span `apps.scholarship`,
`apps.reports` and `apps.courses`; importing it from any one of them would be a cycle.
"""
from django.conf import settings

#: How a job's model is decided. Presentation reads this to say WHY a model is what it is.
BY_SETTING = 'setting'      # a Django setting, overridable per deployment by an env var
BY_CASCADE = 'cascade'      # a named list; the first model that answers wins
BY_LITERAL = 'literal'      # written into the source — changing it needs a deploy

#: Which shared seam a job reaches the provider through. Two of these carry most of the platform,
#: which is why an upgrade is usually two edits rather than fourteen.
SEAM_JSON = 'vision._call_gemini_json'
SEAM_TEXT = 'profile_engine._call_gemini_text'
SEAM_OWN = 'own client'

GEMINI = 'gemini'
OPENAI = 'openai'


def _cascade(dotted):
    """Read a cascade list live, by dotted path. Lazy: importing these at module load would
    drag half of `apps.scholarship` into every `manage.py` invocation."""
    if dotted == 'profile_engine.MODEL_CASCADE':
        from apps.scholarship.profile_engine import MODEL_CASCADE
        return list(MODEL_CASCADE)
    if dotted == 'profile_engine.PRO_CASCADE':
        from apps.scholarship.profile_engine import PRO_CASCADE
        return list(PRO_CASCADE)
    if dotted == 'report_engine.MODEL_CASCADE':
        from apps.reports.report_engine import MODEL_CASCADE
        return list(MODEL_CASCADE)
    raise KeyError(dotted)


#: The jobs. `key` is stable (an i18n key and a test anchor); `label` is English fallback prose
#: for a reader with no translation loaded.
JOBS = [
    # ── the structured-read seam ────────────────────────────────────────────────────────
    {'key': 'doc_read', 'label': 'Reading a document',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/vision.py'},
    {'key': 'ic_genuine', 'label': 'Is this MyKad genuine',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/genuineness/ic.py'},
    {'key': 'results_genuine', 'label': 'Is this results slip genuine',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/genuineness/results_doc.py'},
    {'key': 'doc_genuine', 'label': 'Is this supporting document genuine',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/genuineness/supporting_doc.py'},
    {'key': 'interview_gaps', 'label': 'What to ask at the interview',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/gap_engine.py'},
    {'key': 'answer_relevance', 'label': 'Does this answer the question',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/help_engine.py'},
    {'key': 'spend_category', 'label': 'What kind of shop is this',
     'seam': SEAM_JSON, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/spend_category.py'},

    # ── the prose seam ──────────────────────────────────────────────────────────────────
    {'key': 'student_profile', 'label': 'Writing the student profile',
     'seam': SEAM_TEXT, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/profile_engine.py'},
    {'key': 'profile_refine', 'label': 'The final polish of that profile',
     'seam': SEAM_TEXT, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.PRO_CASCADE',
     'module': 'apps/scholarship/profile_engine.py'},
    {'key': 'doc_help', 'label': 'Telling a student why a document failed',
     'seam': SEAM_TEXT, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/help_engine.py'},
    {'key': 'verdict_narrative', 'label': 'Wording the case summary',
     'seam': SEAM_TEXT, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/verdict_narrative.py'},
    {'key': 'spend_summary', 'label': 'Wording the spending report',
     'seam': SEAM_TEXT, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'profile_engine.MODEL_CASCADE',
     'module': 'apps/scholarship/spend_summary.py'},

    # ── jobs with their own client ──────────────────────────────────────────────────────
    {'key': 'contract_quiz', 'label': 'Writing the agreement quiz',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_SETTING, 'from': 'CONTRACT_QUIZ_MODEL',
     'module': 'apps/scholarship/contracts.py'},
    {'key': 'sponsor_terms', 'label': 'Reading and quizzing the benefactor terms',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_SETTING, 'from': 'CONTRACT_QUIZ_MODEL',
     'module': 'apps/scholarship/sponsor_terms.py'},
    {'key': 'apply_copy', 'label': 'Drafting apply-page copy in Malay or Tamil',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_SETTING, 'from': 'APPLY_COPY_DRAFT_MODEL',
     'module': 'apps/scholarship/apply_copy_draft.py'},
    {'key': 'request_triage', 'label': 'First read of a bug report or request',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_SETTING, 'from': 'REQUESTS_TRIAGE_MODEL',
     'module': 'apps/scholarship/org_requests.py'},
    {'key': 'counsellor_report', 'label': 'The course-guide counsellor report',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_CASCADE, 'from': 'report_engine.MODEL_CASCADE',
     'module': 'apps/reports/report_engine.py',
     # ⚠ THE ONLY JOB WITH A SECOND PROVIDER. When every Gemini in the cascade fails it falls
     # through to OpenAI, which has its own key, its own bill and its own model — and has never
     # fired on production. Named here so an upgrade pass cannot walk past it.
     'fallback_provider': OPENAI, 'fallback_model': 'gpt-4o-mini'},

    # ── batch commands, run by hand ─────────────────────────────────────────────────────
    # ⚠ FIXED means the model is written into the source: changing it needs a code change and a
    # deploy, not a setting. Shown as such rather than hidden, because "this one is different"
    # is exactly what an upgrade checklist owes its reader.
    {'key': 'course_careers', 'label': 'Mapping a course to careers (batch)',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_LITERAL, 'from': 'gemini-2.5-flash',
     'module': 'apps/courses/management/commands/map_course_careers.py', 'fixed': True},
    {'key': 'stpm_headlines', 'label': 'Writing STPM course headlines (batch)',
     'seam': SEAM_OWN, 'provider': GEMINI,
     'source': BY_LITERAL, 'from': 'gemini-2.0-flash',
     'module': 'apps/courses/management/commands/generate_stpm_headlines.py', 'fixed': True},
]


def resolve(job):
    """The model(s) this job would use RIGHT NOW, newest-preferred first.

    A cascade returns every model in order — the second and later entries are the fallbacks, and
    knowing they exist is half of what makes this list useful for an upgrade. A setting returns
    one. Never a stored value.
    """
    src = job['source']
    if src == BY_SETTING:
        return [getattr(settings, job['from'], '') or '']
    if src == BY_CASCADE:
        return _cascade(job['from'])
    return [job['from']]


def snapshot():
    """Every job with its model(s) resolved — the payload the screen renders.

    Read-only and cheap: a few `getattr`s over Django settings plus three lazy imports.
    """
    out = []
    for job in JOBS:
        models = resolve(job)
        out.append({
            'key': job['key'],
            'label': job['label'],
            'module': job['module'],
            'seam': job['seam'],
            'provider': job['provider'],
            'source': job['source'],
            # What the model is read FROM — a setting name, a cascade name, or the literal itself.
            'source_name': job['from'],
            'fixed': bool(job.get('fixed')),
            'model': models[0] if models else '',
            # The rest of the cascade. Empty for a single-model job; NEVER a repeat of `model`.
            'fallbacks': models[1:],
            'fallback_provider': job.get('fallback_provider', ''),
            'fallback_model': job.get('fallback_model', ''),
        })
    return out


def models_in_use():
    """Every distinct model any job could reach today, sorted. The set an upgrade pass covers."""
    seen = set()
    for job in JOBS:
        seen.update(m for m in resolve(job) if m)
        if job.get('fallback_model'):
            seen.add(job['fallback_model'])
    return sorted(seen)
