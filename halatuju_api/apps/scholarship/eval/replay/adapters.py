"""The R2 adapters (design 1, "The adapter"): for each engine, the cases (keys) and the call that turns one
case into a canonical record. Each child imports this module from the harness and runs it against ITS
tree (`resolved`: the engine map's callables for that side); the models and helpers come from that tree.

Rules for every adapter:
  * the record is normalised here (`normalise`): codes as written, free text hashed, amounts as strings;
  * a case is an id (ints under `key`): (application), (application, document), (application, month),
    (profile), (sponsor), (sponsor, programme);
  * application records carry `facts`: non-personal case facts the rulings gate on (stored pathway code,
    stored award, status, degree-bound and start-unknown as THIS side computes them). `facts` is never a
    compared unit (`rulings.units`) and never part of same / differs (`parent.classify`);
  * nothing here writes, sends or reads a file; an engine that tries is refused by the guards and the case
    is `could_not_run`.

`gaps.flags_summary`: `gap_engine.generate_interview_gaps` is a Gemini call (out of scope by rule, 3.2),
so the replay compares the hash of the deterministic flags block it feeds the prompt instead.
"""
import datetime

from . import normalise as N
from . import scrub

scrub.register_codes((
    'verdict', 'facts', 'pathway_code', 'stored_award', 'application_status', 'degree_bound', 'start_unknown',
    'doc_type', 'eligible_courses', 'amount', 'amount_due', 'remaining', 'eligible', 'reasons',
    'paid_to_date', 'balance', 'available_total', 'monthly_amount', 'paid_months', 'row', 'template',
    'variant', 'pathway', 'calendar', 'merit', 'reason', 'bucket', 'category', 'value', 'month',
    'class', 'expected', 'unexplained', 'fields',
))

APPLICATION = 'application'
DOCUMENT = 'document'
PAYABLE = 'payable'
PROFILE_SPM = 'profile_spm'
PROFILE_STPM = 'profile_stpm'
SPONSOR = 'sponsor'
SPONSOR_PROGRAMME = 'sponsor_programme'


# --- cases --------------------------------------------------------------------------------------------

def _apps():
    from apps.scholarship.models import ScholarshipApplication
    return ScholarshipApplication.objects.exclude(status='draft')


def _app(pk):
    from apps.scholarship.models import ScholarshipApplication
    return ScholarshipApplication.objects.get(pk=pk)


def _doc(pk):
    from apps.scholarship.models import ApplicantDocument
    return ApplicantDocument.objects.get(pk=pk)


def _profile(pk):
    from apps.courses.models import StudentProfile
    return StudentProfile.objects.get(pk=pk)


def cases_for(kind, *, doc_types=None, months=()):
    """Sorted keys for one case family (design 3.1)."""
    if kind == APPLICATION:
        return [(pk,) for pk in _apps().order_by('pk').values_list('pk', flat=True)]
    if kind == DOCUMENT:
        from apps.scholarship.models import ApplicantDocument
        qs = ApplicantDocument.objects.filter(superseded_at__isnull=True, application__in=_apps())
        if doc_types:
            qs = qs.filter(doc_type__in=sorted(doc_types))
        return [tuple(r) for r in qs.order_by('application_id', 'pk').values_list('application_id', 'pk')]
    if kind == PAYABLE:
        from apps.scholarship.maintenance_scope import PAYABLE_STATUSES
        from apps.scholarship.models import ScholarshipApplication
        pks = ScholarshipApplication.objects.filter(status__in=PAYABLE_STATUSES).order_by('pk')
        return [(pk, m) for pk in pks.values_list('pk', flat=True) for m in months]
    if kind in (PROFILE_SPM, PROFILE_STPM):
        from apps.courses.models import StudentProfile
        col = 'grades' if kind == PROFILE_SPM else 'stpm_grades'
        qs = StudentProfile.objects.exclude(**{f'{col}__isnull': True}).exclude(**{col: {}})
        return [(pk,) for pk in qs.order_by('pk').values_list('pk', flat=True)]
    if kind == SPONSOR:
        from apps.scholarship.models import Sponsor
        return [(pk,) for pk in Sponsor.objects.order_by('pk').values_list('pk', flat=True)]
    if kind == SPONSOR_PROGRAMME:
        from apps.scholarship.models import Donation, Sponsorship
        pairs = set(Donation.objects.values_list('sponsor_id', 'programme_id'))
        pairs |= set(Sponsorship.objects.values_list('sponsor_id', 'application__programme_id'))
        return sorted(p for p in pairs if None not in p)
    raise ValueError(kind)


# --- facts --------------------------------------------------------------------------------------------

def app_facts(app):
    """Non-personal case facts, as THIS side reads them (a helper this tree lacks gives None)."""
    facts = {'pathway_code': N.code(getattr(app, 'chosen_pathway', None)),
             'stored_award': N.amt(getattr(app, 'award_amount', None)),
             'application_status': N.code(getattr(app, 'status', None))}
    try:
        from apps.scholarship.results_route import degree_bound
    except ImportError:
        facts['degree_bound'] = None
    else:
        facts['degree_bound'] = bool(degree_bound(app))
    from apps.scholarship.award import course_start_unknown
    facts['start_unknown'] = bool(course_start_unknown(app))
    return facts


def row_record(row):
    """A schedule row: which row (a template row's id, or 'default'), pathway, variant and rate."""
    if row is None:
        return {'row': None}
    return {'row': 'template' if getattr(row, 'pk', None) else 'default',
            'template_id': getattr(row, 'template_id', None), 'pathway': N.code(getattr(row, 'pathway', None)),
            'variant': N.code(getattr(row, 'variant', None)) if getattr(row, 'variant', None) else None,
            'monthly_amount': N.amt(getattr(row, 'monthly_amount', None))}


# --- the adapter --------------------------------------------------------------------------------------

class Adapter:
    """One engine. ``call(fn, case, months, resolved)`` returns the canonical record."""

    def __init__(self, name, family, kind, call, *, doc_types=None, facts=False):
        self.name, self.family, self.kind, self.call = name, family, kind, call
        self.doc_types, self.facts = doc_types, facts

    def bind(self, resolved):
        bound = Adapter(self.name, self.family, self.kind, self.call, doc_types=self.doc_types, facts=self.facts)
        bound.resolved = resolved
        return bound

    def cases(self, months=()):
        return cases_for(self.kind, doc_types=self.doc_types, months=months)

    def run(self, key, *, months=()):
        fn = self.resolved[self.name]
        record = self.call(fn, key, self.resolved)
        if not isinstance(record, dict):
            record = {'value': record}
        if self.facts:
            record['facts'] = app_facts(_app(key[0]))
        return record


def _verdict(fn, key, r):
    return {'verdict': [N.fact(f) for f in fn(_app(key[0]))]}


def _disqualifier(fn, key, r):
    return N.code(fn(r['verdict.build_verdict'](_app(key[0]))))


def _award(fn, key, r):
    return {'amount': N.amt(fn(_app(key[0])))}


def _bool_app(fn, key, r):
    return bool(fn(_app(key[0])))


def _code_doc(fn, key, r):
    return N.code(fn(_doc(key[1])))


def _dict_doc(fn, key, r):
    return N.canon(fn(_doc(key[1])))


def _gap_flags(fn, key, r):
    return scrub.text_hash(fn(_app(key[0])))


def _shortlist(fn, key, r):
    app = _app(key[0])
    res = fn(app, app.cohort)
    return {'verdict': N.code(res.verdict), 'bucket': N.code(res.bucket), 'category': N.code(res.category),
            'reason': scrub.text_hash(res.reason)}


def _code_set_app(fn, key, r):
    return {'value': N.codes(fn(_app(key[0])))}


def _code_app(fn, key, r):
    return N.code(fn(_app(key[0])))


def _estimate(fn, key, r):
    est = fn(_app(key[0])) or {}
    return {k: (N.amt(v) if k in ('monthly', 'total') else N.canon(v, k)) for k, v in est.items()
            if isinstance(k, str) and scrub.is_code(k)}


def _schedule_row(fn, key, r):
    return row_record(fn(_app(key[0])))


def _pick_row(fn, key, r):
    from apps.scholarship import contract_scope
    app = _app(key[0])
    template = contract_scope.template_for_application(app)
    return row_record(fn(template.schedule_rows.all(), app)) if template is not None else {'row': None}


def _calendar(fn, key, r):
    app = _app(key[0])
    row = r['payments.schedule_row'](app)
    months = fn(row, app.cohort.year)
    return {'calendar': N.canon(months, 'calendar')}


def _month_dates(month):
    y, m = (int(p) for p in month.split('-'))
    return datetime.date(y, m, 1)


def _eligibility(fn, key, r):
    app, day = _app(key[0]), _month_dates(key[1])
    res = fn(app, day, day) or {}
    return {'eligible': bool(res.get('eligible')), 'reasons': N.codes(res.get('reasons')),
            'remaining': N.amt(res.get('remaining'))}


def _amount_app(fn, key, r):
    return {'amount': N.amt(fn(_app(key[0])))}


def _sponsor_total(fn, key, r):
    from apps.scholarship.models import Sponsor
    return {'available_total': N.amt(fn(Sponsor.objects.get(pk=key[0])))}


def _sponsor_balance(fn, key, r):
    from apps.scholarship.models import Donation, Sponsor
    programme_model = Donation._meta.get_field('programme').related_model
    return {'balance': N.amt(fn(Sponsor.objects.get(pk=key[0]), programme_model.objects.get(pk=key[1])))}


def _engine_student(profile):
    """The course engine's student. The Bumiputera answer is course-guide only (owner ruling 2026-10-28):
    the scholarship app never reads it, so the replay leaves the engine's default (False) on BOTH sides
    and Bumiputera-only courses are compared as for a non-Bumiputera student."""
    from apps.courses.engine import StudentProfile as EngineStudent
    nationality = getattr(profile, 'nationality', '') or 'Warganegara'
    return EngineStudent(grades=profile.grades or {}, gender=profile.gender or 'Lelaki', nationality=nationality,
                         colorblind=bool(getattr(profile, 'colorblind', False)),
                         disability=bool(getattr(profile, 'disability', False)),
                         other_tech=bool(getattr(profile, 'other_tech', False)),
                         other_voc=bool(getattr(profile, 'other_voc', False)))


def _catalogue_ids(df):
    return set(df['course_id'].astype(str)) if df is not None and 'course_id' in df else set()


def _spm_courses(fn, key, r):
    """Every SPM catalogue course the profile is eligible for. Only the catalogue frame's own ids are
    written under `eligible_courses` (scrub.COURSE_KEYS)."""
    from django.apps import apps
    df = apps.get_app_config('courses').requirements_df
    student = _engine_student(_profile(key[0]))
    ids = _catalogue_ids(df)
    out = {str(row['course_id']) for _, row in df.iterrows() if fn(student, row.to_dict())[0]}
    return {'eligible_courses': sorted(out & ids)}


def _merit(fn, key, r):
    p = _profile(key[0])
    return {'merit': N.amt(fn({'grades': p.grades or {}, 'coq_score': getattr(p, 'coq_score', None)}))}


def _stpm_courses(fn, key, r):
    from apps.courses.models import StpmCourse
    p = _profile(key[0])
    res = fn(p.stpm_grades or {}, p.grades or {}, float(p.stpm_cgpa or 0), int(p.muet_band or 0),
             gender=p.gender or '', nationality=p.nationality or 'Warganegara',
             colorblind=bool(getattr(p, 'colorblind', False)))
    ids = set(StpmCourse.objects.values_list('course_id', flat=True))
    got = {str(c.get('course_id')) for c in res or () if isinstance(c, dict)}
    return {'eligible_courses': sorted(got & {str(i) for i in ids})}


A = Adapter
_ALL = (
    A('verdict.build_verdict', 'verdict', APPLICATION, _verdict, facts=True),
    A('award.verdict_disqualifier', 'verdict', APPLICATION, _disqualifier),
    A('gaps.flags_summary', 'verdict', APPLICATION, _gap_flags),
    A('resolution.doc_match_verdict', 'per_document', DOCUMENT, _code_doc),
    A('help.verdict_for_document', 'per_document', DOCUMENT, _code_doc),
    A('higher.match_verdict', 'per_document', DOCUMENT, _code_doc, doc_types={'higher_results'}),
    A('higher.student_higher_check', 'per_document', DOCUMENT, _dict_doc, doc_types={'higher_results'}),
    A('academic.student_slip_check', 'per_document', DOCUMENT, _dict_doc, doc_types={'results_slip'}),
    A('academic.semester_check', 'per_document', DOCUMENT, _dict_doc, doc_types={'semester_result'}),
    A('academic.student_school_leaving_check', 'per_document', DOCUMENT, _dict_doc,
      doc_types={'school_leaving_cert'}),
    A('shortlist.evaluate', 'programme_eligibility', APPLICATION, _shortlist, facts=True),
    A('requirements.required_documents', 'programme_eligibility', APPLICATION, _code_set_app),
    A('requirements.required_questions', 'programme_eligibility', APPLICATION, _code_set_app),
    A('courses.check_eligibility', 'course_eligibility', PROFILE_SPM, _spm_courses),
    A('courses.compute_student_merit', 'course_eligibility', PROFILE_SPM, _merit),
    A('courses.check_stpm_eligibility', 'course_eligibility', PROFILE_STPM, _stpm_courses),
    A('award.proposed_award_amount', 'award', APPLICATION, _award, facts=True),
    A('award.course_start_unknown', 'award', APPLICATION, _bool_app, facts=True),
    A('funding.classify_pathway', 'funding_estimate', APPLICATION, _code_app, facts=True),
    A('funding.estimate_funding', 'funding_estimate', APPLICATION, _estimate, facts=True),
    A('payments.schedule_row', 'schedule', PAYABLE, _schedule_row, facts=True),
    A('schedule.row_for', 'schedule', PAYABLE, _schedule_row, facts=True),
    A('contracts.pick_schedule_row', 'schedule', PAYABLE, _pick_row, facts=True),
    A('contracts.schedule_calendar', 'schedule', PAYABLE, _calendar, facts=True),
    A('payments.eligibility', 'payment', PAYABLE, _eligibility),
    A('payments.default_amount', 'payment', PAYABLE, _amount_app),
    A('payments.paid_to_date', 'payment', PAYABLE, _amount_app),
    A('sponsor.sponsor_balance', 'sponsor_balance', SPONSOR_PROGRAMME, _sponsor_balance),
    A('sponsor.sponsor_available_total', 'sponsor_balance', SPONSOR, _sponsor_total),
)
FAMILY = {a.name: a.family for a in _ALL}
#: name -> factory(resolved) -> a bound adapter (engine_map.ADAPTERS).
ADAPTERS = {a.name: a.bind for a in _ALL}
