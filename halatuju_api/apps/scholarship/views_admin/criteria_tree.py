"""The intake's criteria tree - read and save it whole (criteria editor Sprint 3, the admin API).

Two routes, one behaviour:

* ``admin/scholarship/intake-years/<pk>/criteria/`` - one intake year (the Intake year tab);
* ``admin/scholarship/programmes/<pk>/criteria/`` - the gift's RULE YEAR (the Rules tab): the
  year taking applications, else the newest (`rule_year`, the web's `ruleYear` exactly). Its PATCH
  names the year it means (``intake_id``), so a year opened in between is never edited by mistake.

Same gate and fence as the intake-year screens (`_ProgrammeScopedBase`: `programmes.edit`, the
caller's own organisation's gifts, another tenant's year is a 404). PATCH replaces the WHOLE tree.

HOW THE COLUMNS STAY CONSISTENT. A saved tree is the source of truth (the gate reads it); the old
requirement columns are rewritten in the same save to the values that say it
(`criteria_write.columns_for`, the reader the Rules tab uses), so the old form shows the new rules.
When the columns cannot say the tree (`says_more_than_columns`), the old form's requirement save is
refused (409 ``rules_beyond_columns``, `intake_years._tree_beyond_columns`) rather than rebuilding a
different tree from them.

Refusals: 400 ``bad_criteria`` (with ``problems``) for any tree `criteria_write.write_problems`
refuses; 409 ``rules_error`` when the STORED tree is refused (a technical correction, never an edit
from blank boxes); 409 ``criteria_not_built`` on an intake whose tree is not stored yet (its first
tree is `build_criteria_trees --apply`'s, with its own owner yes - it may switch the CGPA trap off).
"""
import json
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from .. import criteria, criteria_write
from .gift_programmes import _ProgrammeScopedBase
from .gifts import BIRTH_STATES_FIELD, REQUIREMENT_FIELDS
from .intake_years import _stored_tree_refused
from ..start_year import FIELD as START_YEARS_FIELD

logger = logging.getLogger('apps.scholarship.views_admin')

#: The columns a tree save rewrites, in this order (`criteria_write.columns_for`).
COLUMNS = (*REQUIREMENT_FIELDS, BIRTH_STATES_FIELD, START_YEARS_FIELD)


def _err(code, http=status.HTTP_400_BAD_REQUEST, **extra):
    return Response({'error': code, 'code': code, **extra}, status=http)


def _compact(tree):
    return json.dumps(tree, sort_keys=True, separators=(',', ':'))


def criteria_payload(c):
    """The GET / PATCH answer for one intake (field list in the module docstring of the tests and
    in CHANGELOG). ``criteria`` is the tree the gate reads: the stored one, else (``stored`` false)
    today's meaning of the columns. A refused stored tree is served as ``criteria`` null with
    ``rules_error`` true and the generic ``problems`` - never a guessed tree."""
    out = {'intake': {'id': c.id, 'code': c.code, 'name': c.name, 'year': c.year, 'is_open': c.is_open},
           'stored': c.criteria is not None, 'criteria': None, 'rules_error': False,
           'beyond_columns': False}
    if _stored_tree_refused(c):
        out.update(rules_error=True, problems=criteria.validate_tree(c.criteria))
        return out
    tree = criteria.tree_of(c)
    out['criteria'] = tree
    out['beyond_columns'] = out['stored'] and criteria_write.says_more_than_columns(tree)
    return out


def rule_year(programme):
    """The gift's rule year: the year taking applications, else the newest (year, then code) -
    `ProgrammeRulesTab.ruleYear` on the list `AdminIntakeYearListView` serves. None when none."""
    from ..models import ScholarshipCohort
    years = list(ScholarshipCohort.objects.filter(programme=programme).order_by('-year', 'code'))
    return next((y for y in years if y.is_open), years[0] if years else None)


class _CriteriaBase(_ProgrammeScopedBase):
    def _intake(self, admin, pk, lock=False):
        """``(cohort, error)`` for this route's intake, fenced to the caller's gifts."""
        raise NotImplementedError

    def get(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        c, err = self._intake(admin, pk)
        if err:
            return err
        return Response(criteria_payload(c))

    def patch(self, request, pk):
        admin, err = self._gate(request)
        if err:
            return err
        with transaction.atomic():
            return self._patch(request, admin, pk)

    def _body_keys(self):
        return {'criteria'}

    def _check_target(self, request, c):
        return None

    def _patch(self, request, admin, pk):
        # The fence first: another tenant's intake is a 404 whatever the body says.
        c, err = self._intake(admin, pk, lock=True)
        if err:
            return err
        data = request.data if isinstance(request.data, dict) else None
        if data is None:
            return _err('criteria_required')
        unknown = sorted(set(data) - self._body_keys())
        if unknown:
            return _err('unknown_field', fields=unknown)
        if 'criteria' not in data:
            return _err('criteria_required')
        # A bad tree is a 400 whatever the intake's state - never saved (`write_problems`).
        tree = data['criteria']
        problems = criteria_write.write_problems(tree)
        if problems:
            return _err('bad_criteria', problems=problems)
        err = self._check_target(request, c)
        if err:
            return err
        if _stored_tree_refused(c):
            logger.error('AUDIT intake_year_rules_error_refused cohort=%s action=criteria by=%s',
                         c.code, admin.email or '')
            return _err('rules_error', status.HTTP_409_CONFLICT)
        if c.criteria is None:
            return _err('criteria_not_built', status.HTTP_409_CONFLICT)

        old = c.criteria
        columns = criteria_write.columns_for(tree)
        moved = [f for f in COLUMNS if getattr(c, f) != columns[f]]
        changed = moved + (['criteria'] if old != tree else [])
        if changed:
            c.criteria = tree
            for f in moved:
                setattr(c, f, columns[f])
            c.save(update_fields=changed)
            logger.info('AUDIT intake_year_updated cohort=%s fields=%s by=%s',
                        c.code, ','.join(changed), admin.email or '')
            # FROM WHAT, TO WHAT (TD-203's lesson, as `intake_year_requirements_set`): the whole
            # old and new tree, compact JSON with sorted keys, so two lines compare by eye.
            logger.info('AUDIT intake_year_criteria_set cohort=%s old=%s new=%s by=%s',
                        c.code, _compact(old), _compact(tree), admin.email or '')
        return Response({**criteria_payload(c), 'changed': bool(changed)})


class AdminIntakeYearCriteriaView(_CriteriaBase):
    """GET / PATCH one intake year's criteria tree."""

    def _intake(self, admin, pk, lock=False):
        from ..models import ScholarshipCohort
        qs = ScholarshipCohort.objects.select_related('programme', 'programme__organisation')
        if lock:
            qs = qs.select_for_update(of=('self',))   # as `AdminIntakeYearDetailView` (TD-774)
        c = qs.filter(pk=pk, programme__in=self._programmes_for(admin)).first()
        if c is None:
            return None, Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return c, None


class AdminProgrammeCriteriaView(_CriteriaBase):
    """GET / PATCH the gift's rule year's criteria tree (`rule_year`). The PATCH must carry
    ``intake_id``: the year the screen showed. When the rule year has moved since (another year
    opened), 409 ``rule_year_changed`` - reload, never a save to a year nobody looked at."""

    def _intake(self, admin, pk, lock=False):
        p, err = self._programme_or_404(admin, pk)
        if err:
            return None, err
        y = rule_year(p)
        if y is None:
            return None, _err('no_intake_year', status.HTTP_404_NOT_FOUND)
        if lock:
            from ..models import ScholarshipCohort
            y = ScholarshipCohort.objects.select_for_update(of=('self',)).select_related(
                'programme', 'programme__organisation').get(pk=y.pk)
        return y, None

    def _body_keys(self):
        return {'criteria', 'intake_id'}

    def _check_target(self, request, c):
        want = request.data.get('intake_id')
        if isinstance(want, bool) or not isinstance(want, int):
            return _err('intake_id_required')
        if want != c.id:
            return _err('rule_year_changed', status.HTTP_409_CONFLICT, intake_id=c.id)
        return None
