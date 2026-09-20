"""Intake years — the admin endpoints, moved verbatim from `views_admin.py` at H11.
The readers they share with the gift screens are in `gifts.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from ..models import ScholarshipApplication
from .gift_programmes import CODE_RE, _ProgrammeScopedBase
from .gifts import REQUIREMENT_FIELDS, _cohort_row, _window_from

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
        try:
            out[f] = float(v) if f in ('min_stpm_pngk', 'min_merit_score') else int(v)
        except (TypeError, ValueError):
            bad = f
            break
        if out[f] < 0:
            bad = f
            break
    return out, bad


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
        c = ScholarshipCohort.objects.create(
            programme=p, owning_organisation=p.organisation,
            code=code, name=name, year=year, is_active=True, is_open=False, **reqs, **window,
        )
        logger.info('AUDIT intake_year_created cohort=%s programme=%s by=%s',
                    c.code, p.code, admin.email or '')
        return Response(_cohort_row(c), status=status.HTTP_201_CREATED)


class AdminIntakeYearDetailView(_ProgrammeScopedBase):
    """PATCH one intake year — its name, its requirements, and whether it is taking applications."""

    def _cohort_or_404(self, admin, pk):
        from ..models import ScholarshipCohort
        c = (ScholarshipCohort.objects
             .select_related('programme', 'programme__organisation')
             .filter(pk=pk, programme__in=self._programmes_for(admin)).first())
        if c is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return c, None

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        c, err = self._cohort_or_404(admin, pk)
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
        # ⚠ CAPTURE THE OLD VALUE BEFORE WRITING. A threshold decides who is shortlisted, and
        # `shortlisting.evaluate()` reads these columns LIVE — unlike the documents and questions,
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
