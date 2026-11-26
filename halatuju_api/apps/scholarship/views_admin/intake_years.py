"""Intake years — the admin endpoints, moved verbatim from `views_admin.py` at H11.
The readers they share with the gift screens are in `gifts.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import logging
import math

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from ..birth_state import normalise_states
from ..models import ScholarshipApplication
from ..start_year import FIELD as START_YEARS_FIELD, normalise_years
from .gift_programmes import CODE_RE, _ProgrammeScopedBase
from .gifts import BIRTH_STATES_FIELD, REQUIREMENT_FIELDS, _cohort_row, _window_from

#: The package's logger name, spelled out — see the note in `requests.py`.
logger = logging.getLogger('apps.scholarship.views_admin')


def _requirements_from(data):
    """Read the tick boxes. A key that is ABSENT is left alone; a key that is present and null
    UNTICKS that requirement. Both matter: a PATCH sends only what changed, and clearing a value is
    how a test is switched off (S2a — the value IS the switch)."""
    out, bad = {}, None
    for f in REQUIREMENT_FIELDS:
        if f not in data:
            continue
        v = data.get(f)
        if v in (None, ''):
            out[f] = None
            continue
        out[f] = _requirement_value(f, v)
        if out[f] is None or out[f] < 0:
            bad = f
            break
    # Request #31: the birth-state list. Absent = left alone; null or [] = not applied; anything
    # but a list of known state keys is refused WHOLE (`bad_requirement`) — never trimmed to the
    # keys it does know, which would save a different rule from the one sent.
    if not bad and BIRTH_STATES_FIELD in data:
        states, ok = normalise_states(data.get(BIRTH_STATES_FIELD))
        if ok:
            out[BIRTH_STATES_FIELD] = states
        else:
            bad = BIRTH_STATES_FIELD
    # H3: the course-start years, the same list rule (`start_year.normalise_years` refuses whole).
    if not bad and START_YEARS_FIELD in data:
        years, ok = normalise_years(data.get(START_YEARS_FIELD))
        if ok:
            out[START_YEARS_FIELD] = years
        else:
            bad = START_YEARS_FIELD
    return out, bad


def _rebuild_criteria(c):
    """Set ``c.criteria`` to the tree its columns mean (`criteria.from_legacy`) - ONLY when the row
    already HAS a stored tree. Returns `criteria.validate_tree`'s problems (nothing set when there
    are any). Never saves.

    ⚠ A NULL ROW STAYS NULL (adversarial review R1, 2026-11-26). The gate reads NULL as TODAY'S
    meaning of the columns (`criteria.tree_of`), and storing `from_legacy` here would switch the
    CGPA trap off on a save (intake 5: a PNGK floor and no SPM bar) - a decision change the owner
    ruled belongs to `build_criteria_trees --apply` alone, with its own yes. So a save on an
    intake not yet built keeps reading the columns live (they are always current). A NEW year is
    different: it stores its tree at create (`criteria_new.stamp_new`, Sprint 3b)."""
    from .. import criteria
    if c.criteria is None:
        return []
    tree = criteria.from_legacy(c)
    problems = criteria.validate_tree(tree)
    if not problems:
        c.criteria = tree
    return problems


def _stored_tree_refused(c):
    """True when the intake's STORED tree is one `criteria.tree_of` refuses (`StoredTreeRefused`,
    TD-774): a dict that `validate_tree` finds problems in. Such an intake must not have its
    requirements saved nor be opened (adversarial review R2, 2026-11-27): the list shows its row
    with every value null, and a save from those blank boxes would rebuild a tree from nulled
    columns - a nearly OPEN rule set, saved quietly. Its rules need a technical correction first.

    TD-774 (criteria Sprint 3): a stored value that is not a dict at all (a hand-edited list or
    string) is refused too, as `tree_of` refuses it - `validate_tree` refuses every non-dict."""
    from .. import criteria
    return c.criteria is not None and bool(criteria.validate_tree(c.criteria))


def _tree_beyond_columns(c):
    """True when the intake's STORED tree is not the tree its columns mean (`criteria.from_legacy`)
    - it says something the columns cannot (an 'all' income join, a post-SPM merit, a grade count
    at another grade; saved through the criteria API), or the columns were changed under it.
    TD-774 (criteria Sprint 3): the old form's save would rebuild the tree from the columns and
    silently drop that part, so it is refused (409 ``rules_beyond_columns``) instead."""
    from .. import criteria
    return isinstance(c.criteria, dict) and c.criteria != criteria.from_legacy(c)


def _rules_error(c, admin, action):
    logger.error('AUDIT intake_year_rules_error_refused cohort=%s action=%s by=%s',
                 c.code, action, admin.email or '')
    return Response({'error': 'rules_error', 'code': 'rules_error'}, status=status.HTTP_409_CONFLICT)


#: The requirements that are a FLOAT (a PNGK, a merit point). Every other one is a whole count.
_FLOAT_REQUIREMENTS = ('min_stpm_pngk', 'min_merit_score')


def _requirement_value(field, v):
    """One requirement value, or None when it must be refused (`bad_requirement`).

    ⚠ A COUNT IS A WHOLE NUMBER OR NOTHING (request #30 review). `int(6.9)` is 6 and `int(True)` is
    1, so a fractional count was silently floored and a JSON boolean became a requirement — a
    different bar from the one sent, on a rule that decides who gets money. 6.0 is accepted as 6.
    ⚠ A FLOAT MUST BE FINITE: `float('nan')` / `float('inf')` parse, and a NaN floor compares False
    against every PNGK. The browser forwards a typo as the text typed (`intakeYears.num`), so
    'nan' and 'Infinity' are reachable from a box."""
    if isinstance(v, bool):
        return None
    try:
        if field in _FLOAT_REQUIREMENTS:
            n = float(v)
            return n if math.isfinite(n) else None
        if isinstance(v, float):
            return int(v) if v.is_integer() else None
        return int(v)
    except (TypeError, ValueError, OverflowError):
        return None


class AdminIntakeYearListView(_ProgrammeScopedBase):
    """GET one gift's intake years · POST open a new one."""

    def get(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err
        from ..models import ScholarshipCohort
        years = ScholarshipCohort.objects.filter(programme=p).order_by('-year', 'code')
        return Response({
            'programme': {'id': p.id, 'code': p.code, 'name_en': p.name_en,
                          'is_active': p.is_active},
            'years': [_cohort_row(c) for c in years],
        })

    def post(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        p, err = self._programme_or_404(admin, pk)
        if err:
            return err

        from ..models import ScholarshipCohort
        code = (request.data.get('code') or '').strip().lower()
        name = (request.data.get('name') or '').strip()
        year = request.data.get('year')
        if not CODE_RE.match(code):
            return Response({'error': 'bad_code', 'code': 'bad_code'}, status=status.HTTP_400_BAD_REQUEST)
        if not name:
            return Response({'error': 'name_required', 'code': 'name_required'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(year)
        except (TypeError, ValueError):
            return Response({'error': 'bad_year', 'code': 'bad_year'}, status=status.HTTP_400_BAD_REQUEST)
        if ScholarshipCohort.objects.filter(code=code).exists():
            return Response({'error': 'code_taken', 'code': 'code_taken'},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ EVERY REQUIREMENT KEY MUST BE SENT ON CREATE (adversarial review, Sprint 3b; owner rule:
        # a blank or missing value never silently becomes a permissive default). The new year's tree
        # is built from the boxes sent (`stamp_new` below), so a key left OUT would mean "no rule"
        # without anyone having said so - an empty POST would make an open intake. An explicit null
        # still means "no rule" (that IS a statement); a missing key is refused, naming the keys.
        # The web create form always sends all of them (`intakeYears.draftToRequirements`).
        missing = [f for f in (*REQUIREMENT_FIELDS, BIRTH_STATES_FIELD, START_YEARS_FIELD)
                   if f not in request.data]
        if missing:
            return Response({'error': 'missing_requirement', 'code': 'missing_requirement',
                             'fields': missing}, status=status.HTTP_400_BAD_REQUEST)

        reqs, bad = _requirements_from(request.data)
        if bad:
            return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': bad},
                            status=status.HTTP_400_BAD_REQUEST)

        window, bad_window = _window_from(request.data)
        if bad_window:
            return Response({'error': bad_window, 'code': bad_window},
                            status=status.HTTP_400_BAD_REQUEST)

        # ⚠ BOTH THE PROGRAMME AND THE ORGANISATION ARE SET, and they must agree. The application
        # denormalises `owning_organisation` from its cohort, so a cohort carrying one and not the
        # other files students under the wrong fence (TD-177 is exactly this, in a test fixture).
        # It is DERIVED, never asked for.
        #
        # ⚠ CREATED CLOSED, ALWAYS. `is_open` defaults to True on the model, which would mean
        # creating a year opens applications in the same press. Opening is what lets real students
        # in; it gets its own deliberate action below.
        c = ScholarshipCohort(
            programme=p, owning_organisation=p.organisation,
            code=code, name=name, year=year, is_active=True, is_open=False, **reqs, **window,
        )
        # Criteria Sprint 3b (TD-774, decisions.md 2026-11-26 "A new intake year stores its tree
        # when it is created"): the tree is built HERE from the boxes sent (`criteria_new.stamp_new`;
        # a box left blank is no rule - the model has no silent bars any more), so a year created
        # after `build_criteria_trees --apply` is never left NULL with the old meaning by accident.
        from .. import criteria_new
        problems = criteria_new.stamp_new(c)
        if problems:
            return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': 'criteria'},
                            status=status.HTTP_400_BAD_REQUEST)
        c.save(force_insert=True)
        logger.info('AUDIT intake_year_created cohort=%s programme=%s by=%s',
                    c.code, p.code, admin.email or '')
        return Response(_cohort_row(c), status=status.HTTP_201_CREATED)


class AdminIntakeYearDetailView(_ProgrammeScopedBase):
    """PATCH one intake year — its name, its requirements, and whether it is taking applications."""

    def _cohort_or_404(self, admin, pk, lock=False):
        from ..models import ScholarshipCohort
        qs = ScholarshipCohort.objects.select_related('programme', 'programme__organisation')
        if lock:
            # TD-774 (Sprint 3b): the row this save rewrites is LOCKED for the transaction, so
            # `build_criteria_trees --apply` (which locks the rows it fills) and this save run one
            # after the other - a tree can no longer be built from values read before the other
            # one wrote. `of=('self',)`: only the intake row, never its gift or organisation.
            qs = qs.select_for_update(of=('self',))
        c = qs.filter(pk=pk, programme__in=self._programmes_for(admin)).first()
        if c is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return c, None

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        with transaction.atomic():
            return self._patch(request, admin, pk)

    def _patch(self, request, admin, pk):
        c, err = self._cohort_or_404(admin, pk, lock=True)
        if err:
            return err

        changed = []
        if 'name' in request.data:
            name = (request.data.get('name') or '').strip()
            if not name:
                return Response({'error': 'name_required', 'code': 'name_required'},
                                status=status.HTTP_400_BAD_REQUEST)
            c.name = name; changed.append('name')

        window, bad_window = _window_from(request.data, (c.opens_on, c.closes_on))
        if bad_window:
            return Response({'error': bad_window, 'code': bad_window},
                            status=status.HTTP_400_BAD_REQUEST)
        for f, v in window.items():
            setattr(c, f, v); changed.append(f)

        reqs, bad = _requirements_from(request.data)
        if bad:
            return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': bad},
                            status=status.HTTP_400_BAD_REQUEST)
        if reqs and _stored_tree_refused(c):
            # TD-774 (adversarial review R2): refused WHOLE, nothing saved - the name and window
            # in the same body included. A body without requirement keys still goes through.
            return _rules_error(c, admin, 'requirements')
        if reqs and _tree_beyond_columns(c):
            # TD-774 item 1: refused WHOLE, nothing saved, like the refusal above. The tree is
            # edited through the criteria API (`criteria_tree`), which keeps it whole.
            logger.error('AUDIT intake_year_rules_beyond_columns_refused cohort=%s by=%s',
                         c.code, admin.email or '')
            return Response({'error': 'rules_beyond_columns', 'code': 'rules_beyond_columns'},
                            status=status.HTTP_409_CONFLICT)
        # ⚠ CAPTURE THE OLD VALUE BEFORE WRITING. A threshold decides who is shortlisted, and
        # `shortlisting.evaluate()` reads them LIVE (through the criteria tree rebuilt below) — unlike the documents and questions,
        # which are frozen per application at submit (`requirements_snapshot`). So a change here
        # moves the bar for everybody still to be judged, and "which fields changed" does not
        # answer the only question anybody will ask afterwards: FROM WHAT, TO WHAT.
        #
        # This is TD-203's lesson applied before it bites twice: `award_amount` had no audit line
        # either, and when three production rows had to be corrected on 2026-07-30 there was no
        # system record of who set them or to what — it came down to the owner's memory.
        moved = {f: (getattr(c, f), v) for f, v in reqs.items() if getattr(c, f) != v}
        for f, v in reqs.items():
            setattr(c, f, v); changed.append(f)
        if reqs and c.criteria is not None:
            # Criteria Sprint 2: this form is still the only editor, so a save of its boxes
            # REBUILDS a STORED tree from the columns (`criteria.from_legacy`) - otherwise the gate,
            # which reads the tree, would keep the old bar while the screen shows the new one.
            # A NULL tree is left NULL: the gate already reads the new boxes live (R1 fix).
            if _rebuild_criteria(c):
                return Response({'error': 'bad_requirement', 'code': 'bad_requirement', 'field': 'criteria'},
                                status=status.HTTP_400_BAD_REQUEST)
            changed.append('criteria')

        if 'is_open' in request.data:
            want = bool(request.data.get('is_open'))
            # ⚠⚠ FINISHED IS TERMINAL (owner, 2026-09-08: *"when an application is finished, can it
            # be opened again? I don't think it should be"*). The refusal lives HERE, on the
            # endpoint, not only in the browser — a screen that merely hides the control is a
            # suggestion, and this one has to be a rule. Nothing in the product clears
            # `finished_at`; reversing it is a deliberate database correction.
            if want and c.finished_at:
                return Response({'error': 'round_finished', 'code': 'round_finished'},
                                status=status.HTTP_400_BAD_REQUEST)
            if want and not c.is_open and _stored_tree_refused(c):
                # TD-774: never start taking applications on rules nobody can read. Closing stays.
                return _rules_error(c, admin, 'open')
            if want:
                # ⚠⚠ ONE OPEN ROUND PER **GIFT PROGRAMME** — NOT PER ORGANISATION (owner,
                # 2026-09-06: *"Only one round is open for a gift programme. But if the org has two
                # programmes, there could be two open applications."*).
                #
                # This filter said `owning_organisation=` until 2026-09-06, which refused to open
                # Sabah's round while the flagship's was open — an organisation running two gifts
                # could only ever take applications for one of them. Do not put it back.
                #
                # ⚠ WHAT THE NARROWER RULE COSTS, so nobody re-widens it to "fix" the symptom:
                # `services.resolve_open_cohort` counts ambiguity across ALL open rounds
                # platform-wide, deliberately — *"which round?"* is equally unanswerable between
                # two intakes of the same organisation. So with two rounds open, a student who
                # arrives on a bare `/scholarship/apply` (no `?p=<code>`) gets refused. That
                # refusal is CORRECT and must stay: guessing once filed a student under the wrong
                # foundation, funded from the wrong money, with no error anywhere.
                #
                # What was wrong was WHEN it arrived — after the student had filled in the whole
                # form. The apply page now ASKS which gift before the form (PF-1's own rule, moved
                # earlier), and the 409 stays as an unreachable backstop.
                #
                # The refusal below still arrives at the moment the admin creates the ambiguity,
                # which is where it can still be undone.
                from ..models import ScholarshipCohort
                clash = (ScholarshipCohort.objects
                         .filter(programme=c.programme, is_open=True, is_active=True)
                         .exclude(pk=c.pk).values_list('code', flat=True).first())
                if clash:
                    return Response({'error': 'another_year_open', 'code': 'another_year_open',
                                     'open_code': clash}, status=status.HTTP_400_BAD_REQUEST)
                if not c.programme.is_active:
                    return Response({'error': 'programme_not_active', 'code': 'programme_not_active'},
                                    status=status.HTTP_400_BAD_REQUEST)
            c.is_open = want; changed.append('is_open')

        if changed:
            c.save(update_fields=changed)
            logger.info('AUDIT intake_year_updated cohort=%s fields=%s by=%s',
                        c.code, ','.join(changed), admin.email or '')
            # A SECOND line, only when a threshold actually moved, carrying old -> new. Kept
            # separate from the line above rather than widening it: that one records that an
            # intake year was edited, this one records that the bar changed, and the two are read
            # by different people asking different questions.
            if moved:
                logger.info(
                    'AUDIT intake_year_requirements_set cohort=%s changes=%s by=%s',
                    c.code,
                    ';'.join('%s:%s->%s' % (f, old, new) for f, (old, new) in sorted(moved.items())),
                    admin.email or '')
        return Response(_cohort_row(c))


class AdminIntakeYearFinishView(_ProgrammeScopedBase):
    """POST — close an intake round FOR GOOD. Terminal.

    ⚠ ITS OWN ENDPOINT, NOT A FIELD ON THE PATCH, and the reason is the typed confirmation. This is
    the one action on this screen with no way back, so it takes the same shape as deleting a gift:
    the round's own code has to be typed. Folding it into the PATCH would make an irreversible act
    reachable by the same request that renames a round.

    ⚠ THE ROUND MUST BE CLOSED FIRST. Two deliberate steps, the same reasoning as "creating never
    opens": stopping new applicants and ending the grace period are different decisions, taken at
    different times, and collapsing them would have shut out the thirty students who submitted
    between 1 and 7 July 2026.

    ⚠ THE DIALOG NAMES THE UNSUBMITTED COUNT, and this endpoint is why it can: finishing REFUSES a
    late submission, so anybody still part-way through is shut out. That number is the one thing the
    reader cannot see from the dialog, so it is served on the row.
    """

    def post(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        from ..models import ScholarshipApplication, ScholarshipCohort
        c = (ScholarshipCohort.objects
             .select_related('programme', 'programme__organisation')
             .filter(pk=pk, programme__in=self._programmes_for(admin)).first())
        if c is None:
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        if c.finished_at:
            return Response({'error': 'already_finished', 'code': 'already_finished'},
                            status=status.HTTP_400_BAD_REQUEST)
        if c.is_open:
            return Response({'error': 'still_open', 'code': 'still_open'},
                            status=status.HTTP_400_BAD_REQUEST)

        # The typed phrase is the round's own code — printed on the row and in the dialog's label,
        # so typing it is closer to copying than to deciding. Same shape as `delete <code>`.
        typed = (request.data.get('confirm') or '').strip().lower()
        if typed != c.code.lower():
            return Response({'error': 'confirm_mismatch', 'code': 'confirm_mismatch'},
                            status=status.HTTP_400_BAD_REQUEST)

        c.finished_at = timezone.now()
        c.finished_by = admin.email or ''
        c.save(update_fields=['finished_at', 'finished_by'])

        # ⚠ `shortlisted`, NOT `submitted_at__isnull` — that column is `auto_now_add` and is never
        # null. See the same note on `_cohort_row`.
        #
        # ⚠ THE PRAGMA SITS DIRECTLY ABOVE THE QUERY, and it has to: the static guard looks within
        # 200 characters, so an explanation wedged between the two makes it fail — correctly.
        # org-fence: `c` came through `_programmes_for(admin)`, so this is already the caller's org.
        stranded = ScholarshipApplication.objects.filter(cohort=c, status='shortlisted').count()
        # ⚠ THE COUNT IS ON THE AUDIT LINE because it is the part nobody can reconstruct later: the
        # round's own row says it is finished either way, but "and it shut out two half-finished
        # applications" is the fact a reader would otherwise have to guess at. TD-203's lesson.
        logger.info('AUDIT intake_year_finished cohort=%s unsubmitted=%s by=%s',
                    c.code, stranded, admin.email or '')
        return Response(_cohort_row(c))
