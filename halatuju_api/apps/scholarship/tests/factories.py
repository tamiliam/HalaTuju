"""Code health H5 — THE TEST FACTORY. Builds only states the product can reach.

**Why this file exists.** On 2026-09-18 a production defect (BrightPath request #24) came out
of a hand-built fixture that described a state the product cannot produce: it fed
``status='rejected'`` to a check whose live states never include it, so the test could never
reach the branch it named, and a real bug sat behind a green test.

**TWO ROADS REACH QC AND THEY LEAVE DIFFERENT MARKS.** A reviewer who RECOMMENDS goes through
``verify-accept``, which stamps ``verified_at`` / ``verified_by`` / ``verify_checklist`` and
locks ``profile.nric_verified``. A reviewer who DECLINES goes through ``submit-decline``, which
since 2026-07-19 moves the case to ``interviewed`` and stamps **none** of those — a decline has
no identity or completeness gate, because an incomplete applicant is exactly who gets declined.
Asking for ``verified_at`` on the decline road is asking for a mark that is never written.
``make_application(stage='awaiting_qc', outcome=…)`` is the one place that difference is
written down, and ``test_factories.py`` walks BOTH roads through the real endpoints and asserts
the factory agrees with them — which is what stops this file becoming the next stale fixture.

**Not collected by pytest** (no ``test_`` prefix), the same arrangement as
``contract_helpers.py``.

WHAT IS HERE
  * ``make_org`` / ``make_programme`` / ``make_cohort`` / ``make_admin`` / ``make_student`` —
    the supporting rows, each with a unique code/uid/NRIC per call so the suite is safe under
    ``pytest -n auto``.
  * ``auth_token`` / ``authed_client`` — ONE home for the HS256 test JWT that 83 test files
    each used to define for themselves. ``TEST_JWT_SECRET`` is exported so a test class can
    keep writing ``@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)``.
  * ``make_application(stage=…, outcome=…)`` — an application AT A NAMED STAGE, carrying every
    field the product would have set by then and none it would not. ``STAGES`` is the table;
    ``STAGE_FIELDS`` is the set of fields the drift test compares.

SPEED, ON PURPOSE. The stages are built by SETTING FIELDS, not by walking the product: the
suite is 6,760 tests and a factory that ran the whole funnel for every fixture would make every
one of them slower. Correctness comes from ``test_factories.py`` instead, which walks each
stage through the REAL services/endpoints once and asserts the two agree.

WHAT THE FACTORY DELIBERATELY DOES **NOT** BUILD: documents, a ``FundingNeed``, quiz signals —
i.e. the things ``services.application_completeness`` counts. They are PREREQUISITES a student
supplies, not fields the product stamps, and adding them to every fixture would change what
hundreds of existing tests observe. A test that needs a complete application adds them itself
(``test_phase_c.PhaseCBase._complete`` is the pattern). The one exception is the sponsor pool:
from ``recommended`` on, the published ``SponsorProfile`` + the active share consent + the
award amount ARE what makes the stage what it is (``pool.eligible_pool_queryset``), so those
are built.
"""
import datetime
import itertools
import uuid

import jwt
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import requirements
from apps.scholarship.models import (
    Consent, Programme, ScholarshipApplication, ScholarshipCohort, SponsorProfile,
)

# ── The test JWT, in one place ──────────────────────────────────────────────────────────────
#: The secret 86 test files each spelled out for themselves. A test class still has to say
#: ``@override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)`` — the setting is read by the
#: authentication layer, not by this module, so it cannot be set from here.
TEST_JWT_SECRET = 'test-supabase-jwt-secret'

# ── Uniqueness under `pytest -n auto` ───────────────────────────────────────────────────────
#: Each xdist worker is its own process against its own database, so a process-local counter is
#: enough to keep codes/uids/NRICs distinct. The uuid stem additionally keeps two workers'
#: values apart, which matters for anything a test writes to a shared place (storage paths).
#: ⚠ NEVER a fixed literal: two fixtures sharing a uid or a cohort code is a unique-constraint
#: failure that only shows up when the two land in the same test.
_STEM = uuid.uuid4().hex[:8]
_SEQ = itertools.count(1)


def _n():
    return next(_SEQ)


def unique_suffix(prefix=''):
    """A short, unique, readable token — ``f7a91c3b-12``. Exposed so a test that needs its own
    unique code (a storage path, a second organisation) uses the same scheme."""
    return f'{prefix}{_STEM}-{_n()}'


# ── Obviously-fake but FORMAT-VALID personal data ───────────────────────────────────────────
#: Malaysian NRIC is ``YYMMDD-PB-###G``; ``services.age_from_nric`` parses the first six digits
#: as a date, so the date has to be real. 2003-03-03 makes every factory student an ADULT (the
#: guardian-consent and guardian-document gates then do not apply unless a test asks for them),
#: and the ``030303-14-`` stem is used by no hand-written fixture in the suite, so a factory
#: student can never collide with one at the soft-NRIC uniqueness check in ``verify-accept``.
_NRIC_STEM = '030303-14-'


def fake_nric(serial=None):
    """A syntactically valid, obviously fake NRIC — ``030303-14-0007``. Unique per call."""
    return f'{_NRIC_STEM}{(serial if serial is not None else _n()) % 10000:04d}'


# ── The stage table ─────────────────────────────────────────────────────────────────────────
#: Every stage ``make_application`` can build, in the order the product reaches them.
#: ⚠ THE CODE WROTE THIS LIST, NOT A GUESS. Two things worth knowing before reading it:
#:   * There is **no 'draft' application**. A row is created at SUBMIT
#:     (``services.create_application``) and its status default is ``submitted``; nothing in
#:     ``ScholarshipApplication.STATUS_CHOICES`` is a draft. ``submitted`` IS the first stage.
#:   * ``scored`` and ``assigned`` are real stages with NO status of their own —
#:     ``services.score_application`` computes the verdict while status stays ``submitted``
#:     (the S8 delayed reveal), and ``services.assign_reviewer`` attaches a reviewer while
#:     status stays ``profile_complete``. Leaving them out would have meant no fixture could
#:     name the state that actually exists in production between the two flips.
STAGES = (
    'submitted',         # the row exists; the engine has not run
    'scored',            # verdict computed silently, status still 'submitted' (S8 delayed reveal)
    'shortlisted',       # the verdict was released to the student
    'profile_complete',  # the student confirmed a complete Step-4 profile
    'assigned',          # a reviewer holds it; status is still 'profile_complete'
    'interviewing',      # the reviewer is working it
    # ⚠ `record-verdict` MOVES NO STATUS. The verdict is on the row and the case is still
    # 'interviewing' until the reviewer takes one of the two roads below, which is the state
    # the cockpit's "Save verdict" leaves and several suites need. REQUIRES an outcome.
    'verdict_recorded',
    'awaiting_qc',       # status 'interviewed' — REQUIRES outcome='recommend' or 'decline'
    'recommended',       # QC accepted; in the sponsor pool
    'awarded',           # a funder committed
    'active',            # the award was accepted / the agreement executed
    'maintenance',       # the first tranche was paid
    'closed',            # terminal archive
    # ── the two terminal BRANCHES (see BRANCHES below) ──────────────────────────────────────
    'rejected',          # declined through QC, email embargoed by the 24h cool-off
    'expired',           # shortlisted, never completed, auto-closed after the R4 grace
)

#: Where each terminal branch LEAVES THE MAIN LINE, which is what stops a branch inheriting
#: stamps it never had. A ``rejected`` case comes off the decline road at AWAITING QC, so it
#: carries the verdict stamps and none of the QC/award ones; an ``expired`` case never got past
#: ``shortlisted``, so it carries no verdict at all. Writing this down is the difference between
#: a stage table and a list of statuses.
BRANCHES = {'rejected': 'awaiting_qc', 'expired': 'shortlisted'}
#: The funnel proper — every stage that is not a branch, in order.
MAIN_LINE = tuple(stage for stage in STAGES if stage not in BRANCHES)

#: The stage(s) that take an ``outcome``. Any other stage + an outcome is a ValueError: the two
#: roads exist at exactly one point in the funnel and pretending otherwise is the #24 mistake.
OUTCOME_STAGES = frozenset({'verdict_recorded', 'awaiting_qc'})
OUTCOMES = ('recommend', 'decline')

#: Stages ``test_factories.py`` cannot walk through real product code, with the reason.
#: EMPTY, and it must stay empty unless a reason is written beside the name: a stage nobody can
#: reach through the product is a stage the factory can quietly invent.
UNVERIFIED_STAGES = {}

#: The fields ``test_factories.py`` compares between a factory-built application and one walked
#: to the same stage through the real code. Timestamps are compared for NULL-ness (the two runs
#: happen at different instants); everything else for equality.
STAGE_FIELDS = (
    'status',
    'verdict', 'bucket',
    'decision_due_at', 'decision_released_at', 'shortlisted_at', 'reminder_anchor_at',
    'profile_completed_at',
    'assigned_to_id', 'assigned_at',
    'reporting_date',
    'verdict_decided_at', 'verdict_decided_by',
    'verified_at', 'verified_by',
    'ai_verdict_engine_version',
    'recommended_at', 'recommended_by',
    'awarded_at', 'active_at', 'maintenance_at', 'maintenance_substate',
    'rejected_at', 'rejected_by', 'rejection_category', 'rejection_comments',
    'pre_decline_status', 'pre_decline_award_amount',
    'decline_due_at', 'pending_rejection_category', 'pending_decline_by',
    'decline_email_sent_at',
    'closed_at', 'closed_by', 'closure_reason',
    'expired_at', 'reminder_stage', 'last_reminder_at',
    'award_amount',
    'programme_id', 'owning_organisation_id',
)
#: Members of STAGE_FIELDS compared by NULL-ness rather than by value.
NULLNESS_ONLY = frozenset({
    'decision_due_at', 'decision_released_at', 'shortlisted_at', 'reminder_anchor_at',
    'profile_completed_at', 'assigned_at', 'verdict_decided_at', 'verified_at',
    'recommended_at', 'awarded_at', 'active_at', 'maintenance_at', 'rejected_at',
    'decline_due_at', 'decline_email_sent_at', 'closed_at', 'expired_at', 'last_reminder_at',
})

#: What ``verify-accept`` records when the reviewer ticks every box.
VERIFY_CHECKLIST = {'nric': True, 'name': True, 'results': True, 'document': True}
#: What ``record-verdict`` stores for each road. ``audit.FACTS`` is the key set; ``overall`` is
#: what ``submit-decline`` and ``AdminQcDecisionView`` both branch on.
RECOMMEND_VERDICT = {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                     'income': 'pass', 'overall': 'accept'}
DECLINE_VERDICT = {'identity': 'pass', 'academic': 'fail', 'pathway': 'pass',
                   'income': 'fail', 'overall': 'decline'}
#: QC refuses a case with no reporting date (owner 2026-07-23) — it sizes the bursary. A
#: fresh-entrant date inside the cohort year, so ``award.proposed_award_amount`` is unaffected.
REPORTING_DATE = datetime.date(2026, 6, 8)
#: ``award.proposed_award_amount`` for a non-STPM pathway (the factory default), applied
#: automatically by ``record-verdict`` on an APPROVE.
STANDARD_AWARD = 2000


class _StageError(ValueError):
    """A ValueError, so callers may keep catching ValueError; named for readable tracebacks."""


def stage_reaches(stage, name):
    """Does the funnel pass ``name`` on the way to ``stage``? Branch-aware: ``expired`` never
    reaches ``assigned`` even though it sorts after it in ``STAGES``."""
    _stage_index(stage)
    return name in MAIN_LINE[:MAIN_LINE.index(BRANCHES.get(stage, stage)) + 1]


def _stage_index(stage):
    try:
        return STAGES.index(stage)
    except ValueError:
        raise _StageError(
            f'unknown stage {stage!r}. make_application builds only states the product can '
            f'reach; the stages are: {", ".join(STAGES)}. If you need a state that is not '
            f'here, either it is not reachable (which is the bug this factory exists to stop '
            f'a test from asserting) or the factory needs extending — extend it, with a test '
            f'in test_factories.py that walks the new stage through the real code.')


# ── The supporting rows ─────────────────────────────────────────────────────────────────────
def make_org(code=None, **kw):
    """A tenant ``PartnerOrganisation``. Unique code per call unless one is given."""
    kw.setdefault('name', f'Test Organisation {code or ""}'.strip())
    return PartnerOrganisation.objects.create(code=code or unique_suffix('org-'), **kw)


def make_programme(organisation=None, code=None, **kw):
    """A gift ``Programme`` under ``organisation`` (one is made when omitted)."""
    kw.setdefault('name_en', 'Test Bursary Programme')
    return Programme.objects.create(
        organisation=organisation if organisation is not None else make_org(),
        code=code or unique_suffix('prog-'), **kw)


#: Distinguishes "the caller said nothing" from "the caller said None on purpose".
_UNSET = object()


def make_cohort(*, programme=_UNSET, **kw):
    """An intake round.

    ⚠ THE DEFAULT COHORT ALWAYS HAS A PROGRAMME, and that is not tidiness. Since TD-258
    ``sponsorship.fund_student`` refuses an application whose ``programme_id`` is NULL
    ('programme_required') — the NULL wallet is not a wallet — so a cohort with no programme
    builds applications that can never be funded, and a money test written on one would prove
    nothing. ``ScholarshipApplication.save()`` denormalises the cohort's programme onto the
    application, so the application's ``programme`` matches this cohort's by construction.

    ``owning_organisation`` is taken from the programme's organisation, because the drift guard
    asserts the two agree (see ``ScholarshipCohort.programme``). Pass ``programme=None``
    explicitly for the deliberately programme-less cohort a tenancy test may need.
    """
    if programme is _UNSET:
        # A caller who named the owning organisation gets the gift made INSIDE it, so the two
        # agree by construction — the invariant the fence leans on and `test_programme_layer`
        # guards. A caller who named neither gets a fresh organisation of its own.
        programme = make_programme(organisation=kw.get('owning_organisation'))
    kw.setdefault('code', unique_suffix('cohort-'))
    kw.setdefault('name', 'Test Bursary Programme 2026')
    kw.setdefault('year', 2026)
    if programme is not None:
        kw.setdefault('owning_organisation', programme.organisation)
    return ScholarshipCohort.objects.create(programme=programme, **kw)


def make_admin(role='reviewer', *, org=None, owning_org=None, super_admin=False, uid=None, **kw):
    """A ``PartnerAdmin``. ``role`` is any of ``PartnerAdmin.ROLE_CHOICES``; ``super_admin=True``
    sets the platform-super flag (which most permission code reads instead of the role).

    ⚠ ``org`` AND ``owning_org`` ARE DIFFERENT THINGS AND THE FENCE READS THE SECOND.
    ``org`` is the REFERRING organisation (attribution); ``owning_organisation`` is the B40
    ACCESS-CONTROL boundary — ``_AdminBase._org_allows`` compares it with the application's
    own ``owning_organisation`` and answers 404 when they differ. So a non-super admin who is
    to act on a ``make_cohort()`` application needs ``owning_org=cohort.owning_organisation``;
    without it the admin sits in the NULL bucket and every request 404s. A super is global and
    needs neither.

    ⚠ A super admin is BOTH things in this codebase — ``is_super_admin`` is the live flag and
    ``role='super'`` is the newer column that was backfilled from it — so passing
    ``super_admin=True`` sets the flag and leaves ``role`` as given, exactly as the live rows
    are shaped. Pass ``role='super'`` as well if the code under test reads the column.
    """
    if role not in dict(PartnerAdmin.ROLE_CHOICES):
        raise _StageError(
            f'unknown admin role {role!r}; PartnerAdmin.ROLE_CHOICES are: '
            f'{", ".join(code for code, _ in PartnerAdmin.ROLE_CHOICES)}')
    n = _n()
    kw.setdefault('name', f'Test {role.replace("_", " ").title()} {n}')
    kw.setdefault('email', f'{role}{n}@example.test')
    kw.setdefault('is_active', True)
    kw.setdefault('owning_organisation', owning_org)
    return PartnerAdmin.objects.create(
        supabase_user_id=uid or unique_suffix(f'{role}-uid-'),
        role=role, is_super_admin=bool(super_admin), org=org, **kw)


def make_student(**kw):
    """A ``StudentProfile`` — a unique uid, an obviously fake but FORMAT-VALID NRIC, a name.

    ⚠ DELIBERATELY MINIMAL, and this is the opposite of the application factory's rule for a
    reason. What the product stamps on an APPLICATION is the product's own business and the
    factory must get it right; what a STUDENT has told us is the student's, and a profile with
    no grades, no income and no address is an ordinary early state. Filling those in by default
    would silently change what every engine test observes — the income engine, the shortlisting
    engine and the completeness gate all read this row — and a fixture that quietly acquires a
    household income is exactly the kind of invention this sprint exists to stop.

    Use ``make_shortlistable_student`` when the test needs a profile the engine will pass.
    """
    kw.setdefault('nric', fake_nric())
    kw.setdefault('name', f'Test Student {_n()}')
    return StudentProfile.objects.create(
        supabase_user_id=kw.pop('supabase_user_id', None) or unique_suffix('student-uid-'), **kw)


#: What a student has to have told us to clear the default cohort's thresholds AND the parts of
#: `services.application_completeness` that live on the profile (quiz signals, address).
SHORTLISTABLE_PROFILE = {
    'school': 'SMK Test',
    'grades': {f'subject{i}': 'A' for i in range(10)},
    'household_income': 2500,
    'household_size': 5,
    'receives_str': True,
    'student_signals': {'field_interest': {'it': 5}},
    'address': 'No. 1 Jalan Test',
    'postal_code': '62100',
    'city': 'Putrajaya',
}


def make_shortlistable_student(**kw):
    """A student the real engine SHORTLISTS — strong SPM grades, a B40 income, an STR
    household — and whose profile half of the completeness gate is satisfied. What
    ``test_factories.py`` walks, and what a test needs when it drives the product end to end."""
    for field, value in SHORTLISTABLE_PROFILE.items():
        kw.setdefault(field, value)
    kw.setdefault('contact_email', f'student{_n()}@example.test')
    return make_student(**kw)


# ── Authentication ──────────────────────────────────────────────────────────────────────────
def auth_token(uid):
    """The HS256 bearer token the API's Supabase authentication accepts in tests. ``uid`` is a
    ``supabase_user_id`` (a student's or an admin's) or an object carrying one."""
    uid = getattr(uid, 'supabase_user_id', uid)
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def authed_client(admin_or_uid, client=None):
    """An ``APIClient`` carrying ``admin_or_uid``'s bearer token. Pass an existing ``client`` to
    re-credential it in place (what a ``_auth(uid)`` helper used to do)."""
    client = client if client is not None else APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {auth_token(admin_or_uid)}')
    return client


# ── The application ─────────────────────────────────────────────────────────────────────────
def make_application(stage='submitted', *, outcome=None, cohort=None, student=None,
                     reviewer=None, **overrides):
    """An application AT ``stage``, carrying what the product would have stamped by then.

    ``outcome`` is required at — and permitted only at — the two stages that have roads,
    ``verdict_recorded`` and ``awaiting_qc``: ``'recommend'`` is the verify-accept road
    (verified_at / verified_by / verify_checklist set, ``nric_verified`` locked) and
    ``'decline'`` is the submit-decline road, which stamps NONE of those. See the module
    docstring; ``test_factories.py`` asserts both against the live endpoints.

    ``**overrides`` sets any field explicitly and always wins, so a test that needs one odd
    value says so in one line instead of going back to ``objects.create``.

    Raises ``ValueError`` on an unknown stage, on an outcome at a stage that has none, and on a
    missing outcome at a stage that needs one.
    """
    _stage_index(stage)
    if outcome is not None:
        if stage not in OUTCOME_STAGES:
            raise _StageError(
                f'stage {stage!r} takes no outcome (got {outcome!r}). The stages with two '
                f'roads are: {", ".join(sorted(OUTCOME_STAGES))} — recommend leaves the verify '
                f'stamps, decline leaves none.')
        if outcome not in OUTCOMES:
            raise _StageError(
                f'unknown outcome {outcome!r}; the two roads to QC are: {", ".join(OUTCOMES)}.')
    elif stage in OUTCOME_STAGES:
        raise _StageError(
            f"stage {stage!r} needs an outcome: outcome='recommend' (the verify-accept road, "
            f"which stamps verified_at/verified_by/verify_checklist and locks nric_verified) or "
            f"outcome='decline' (the submit-decline road, which stamps none of them). They are "
            f'different states and a fixture must say which one it means.')

    cohort = cohort if cohort is not None else make_cohort()
    student = student if student is not None else make_student()

    # ⚠ A BRANCH DOES NOT INHERIT THE REST OF THE MAIN LINE. `rejected` leaves the funnel at
    # AWAITING QC and `expired` at `shortlisted`, so each one's cumulative prefix stops where it
    # actually left — otherwise a rejected fixture would carry `recommended_at` and an expired
    # one a recorded verdict, which is the class of invention this whole file exists to prevent.
    def reached(name):
        """Has the funnel passed ``name`` on the way to ``stage``?"""
        return stage_reaches(stage, name)

    declined_road = (stage in OUTCOME_STAGES and outcome == 'decline') or stage == 'rejected'
    now = timezone.now()

    fields = {
        'cohort': cohort,
        'profile': student,
        'status': 'submitted',
        'locale': 'en',
        'notify_email': student.contact_email or f'{unique_suffix("app-")}@example.test',
        'consent_to_contact': True,      # nobody submits without it (shortlisting.evaluate)
        'intends_tertiary_2026': True,
        'declaration_name': student.name,
        'declared_at': now,
    }

    # scored — the engine ran silently; status is STILL 'submitted' (S8 delayed reveal).
    if reached('scored'):
        fields.update(verdict='shortlisted', bucket='A',
                      shortlist_reason='STR household', decision_due_at=now)
    # shortlisted — the verdict was released and the completion-reminder clock started.
    if reached('shortlisted'):
        fields.update(status='shortlisted', decision_released_at=now, shortlisted_at=now,
                      reminder_anchor_at=now)
    # profile_complete — the student confirmed; what the programme asked for is frozen.
    if reached('profile_complete'):
        fields.update(status='profile_complete', profile_completed_at=now)
    # assigned — a reviewer holds it. Status does NOT move (services.assign_reviewer).
    if reached('assigned'):
        reviewer = reviewer if reviewer is not None else make_admin('reviewer')
        fields.update(assigned_to=reviewer, assigned_at=now)
    elif reviewer is not None:
        fields.update(assigned_to=reviewer, assigned_at=now)
    # interviewing — the reviewer is working the case and has settled the reporting date.
    if reached('interviewing'):
        fields.update(status='interviewing', reporting_date=REPORTING_DATE)
    # verdict_recorded — `record-verdict` writes the verdict and MOVES NO STATUS. On an
    # APPROVE it also auto-applies the standardised award amount; on a DECLINE it clears one.
    if reached('verdict_recorded'):
        from apps.scholarship.verdict_engine import VERDICT_ENGINE_VERSION
        verdict_by = (reviewer.email if reviewer is not None else 'reviewer@example.test')
        fields.update(
            officer_verdict=dict(DECLINE_VERDICT if declined_road else RECOMMEND_VERDICT),
            verdict_decided_by=verdict_by,
            verdict_decided_at=now,
            ai_verdict_engine_version=VERDICT_ENGINE_VERSION,
            award_amount=None if declined_road else STANDARD_AWARD,
        )
    # awaiting_qc — the reviewer took ONE of the two roads, and they leave different marks.
    if reached('awaiting_qc'):
        fields.update(status='interviewed')
        if not declined_road:
            fields.update(verified_at=now, verified_by=fields['verdict_decided_by'],
                          verify_checklist=dict(VERIFY_CHECKLIST))
        # ⚠ THE DECLINE ROAD STAMPS NOTHING ELSE. `submit-decline` moves the status and saves
        # one field. No verified_at, no verified_by, no checklist, no NRIC lock.
    # recommended — QC accepted. The case is now in the sponsor pool (built below).
    if reached('recommended'):
        fields.update(status='recommended', recommended_at=now,
                      recommended_by='qc@example.test')
    if reached('awarded'):
        fields.update(status='awarded', awarded_at=now)
    if reached('active'):
        fields.update(status='active', active_at=now)
    if reached('maintenance'):
        fields.update(status='maintenance', maintenance_at=now,
                      maintenance_substate='on_track')
    if reached('closed'):
        fields.update(status='closed', closure_reason='graduated', closed_at=now,
                      closed_by='admin@example.test')
    # expired — the branch off `shortlisted`: the student never completed, the four reminders
    # all went, the 5-day grace lapsed and the daily sweep auto-closed the case
    # (`services.send_application_reminders`). No verdict, no reviewer, nothing else.
    if stage == 'expired':
        from apps.scholarship.services import REMINDER_THRESHOLDS_DAYS
        fields.update(status='expired', expired_at=now,
                      reminder_stage=len(REMINDER_THRESHOLDS_DAYS), last_reminder_at=now)
    # rejected — the QC confirmed the DECLINE. `_record_reject` snapshots the status it was
    # declined FROM and `admin_reject` embargoes the student email for the 24h QC cool-off.
    if stage == 'rejected':
        fields.update(
            status='rejected', rejection_category='interview',
            rejected_at=now, rejected_by='qc@example.test',
            pre_decline_status='interviewed',
            # No snapshot: the decline verdict already cleared award_amount, so
            # `_record_reject` found nothing to save.
            pre_decline_award_amount=None, award_amount=None,
            pending_rejection_category='interview',
            decline_due_at=now + datetime.timedelta(hours=24),
            pending_decline_by='qc@example.test',
        )

    fields.update(overrides)
    application = ScholarshipApplication.objects.create(**fields)

    # ── The bits that are not columns ───────────────────────────────────────────────────────
    if reached('profile_complete'):
        # What the programme asked for, frozen at the Step-4 Submit (services.confirm_profile).
        requirements.freeze(application)
    if reached('awaiting_qc') and not declined_road:
        # verify-accept locks the NRIC. The decline road does not — see the module docstring.
        if not student.nric_verified:
            student.nric_verified = True
            student.save(update_fields=['nric_verified'])
    if reached('recommended'):
        # What makes a student POOL-ELIGIBLE, and it is all three of these together
        # (`pool.eligible_pool_queryset`): an anon-published sponsor profile, an ACTIVE
        # share_with_sponsors consent, and status 'recommended'. `is_fundable` adds a positive
        # award_amount. Drop any one and the student silently vanishes from the pool — which is
        # exactly what the bite-check for this factory removes.
        SponsorProfile.objects.create(
            application=application,
            anon_markdown='A determined SPM leaver hoping to read engineering.',
            anon_blurb='A determined SPM leaver.',
            anon_published=True, anon_published_at=now)
        Consent.objects.create(application=application,
                               consent_type='share_with_sponsors', version='t', is_active=True)
    return application
