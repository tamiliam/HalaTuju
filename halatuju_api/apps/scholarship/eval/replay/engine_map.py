"""The engine map (design 1, "The adapter"): each engine's import path in the OLD tree (v3.1.0) and the
NEW tree (live main). Some moved after v3.1.0 (A3.4, A3.6, A3.8): `contracts.py` became `contracts/`,
`sponsorship.py` became `sponsorship/`.

`resolve_tree(side)` imports every path for one tree and raises `Unresolved` naming each one that does not
resolve, so a moved name can never be compared against nothing. The image build runs
`python -m replay.engine_map --side old` and `--side new` in each tree's own venv and fails on exit 1.

The adapters that turn a case into a call and an answer into a record are R2 (`ADAPTERS`, from `adapters`).
"""
import argparse
import importlib
import sys

from . import adapters as _adapters
from . import rulings, scrub, vocab

S = 'apps.scholarship.'

#: name -> (old 'module:attr', new 'module:attr'). Paths checked against both trees on 2026-11-13.
ENGINES = {
    'verdict.build_verdict': (S + 'verdict_engine:build_verdict',) * 2,
    'award.verdict_disqualifier': (S + 'award:verdict_disqualifier',) * 2,
    'award.proposed_award_amount': (S + 'award:proposed_award_amount',) * 2,
    'award.course_start_unknown': (S + 'award:course_start_unknown',) * 2,
    'resolution.doc_match_verdict': (S + 'resolution:doc_match_verdict',) * 2,
    'higher.match_verdict': (S + 'higher_results:match_verdict',) * 2,
    'higher.student_higher_check': (S + 'higher_results:student_higher_check',) * 2,
    'academic.student_slip_check': (S + 'academic_engine:student_slip_check',) * 2,
    'academic.semester_check': (S + 'academic_engine:semester_check',) * 2,
    'academic.student_school_leaving_check': (S + 'academic_engine:student_school_leaving_check',) * 2,
    'help.verdict_for_document': (S + 'help_engine:verdict_for_document',) * 2,
    # generate_interview_gaps is a Gemini call (out of scope, 3.2): the replay compares the deterministic
    # flags block it feeds the prompt, hashed (adapters._gap_flags).
    'gaps.flags_summary': (S + 'gap_engine:_flags_summary',) * 2,
    'shortlist.evaluate': (S + 'shortlisting:evaluate',) * 2,
    'courses.check_eligibility': ('apps.courses.engine:check_eligibility',) * 2,
    'courses.compute_student_merit': ('apps.courses.eligibility_service:compute_student_merit',) * 2,
    'courses.check_stpm_eligibility': ('apps.courses.stpm_engine:check_stpm_eligibility',) * 2,
    'requirements.required_documents': (S + 'requirements:required_documents',) * 2,
    'requirements.required_questions': (S + 'requirements:required_questions',) * 2,
    'funding.classify_pathway': (S + 'funding_estimate:classify_pathway',) * 2,
    'funding.estimate_funding': (S + 'funding_estimate:estimate_funding',) * 2,
    'payments.schedule_row': (S + 'payments:_schedule_row',) * 2,
    'payments.eligibility': (S + 'payments:eligibility',) * 2,
    'payments.default_amount': (S + 'payments:default_amount',) * 2,
    'payments.paid_to_date': (S + 'payments:paid_to_date',) * 2,
    'schedule.row_for': (S + 'default_schedule:row_for',) * 2,
    'contracts.pick_schedule_row': (S + 'contracts:pick_schedule_row', S + 'contracts.readers:pick_schedule_row'),
    'contracts.schedule_calendar': (S + 'contracts:schedule_calendar', S + 'contracts.readers:schedule_calendar'),
    'sponsor.sponsor_balance': (S + 'sponsorship:sponsor_balance', S + 'sponsorship.wallet:sponsor_balance'),
    'sponsor.sponsor_available_total': (S + 'sponsorship:sponsor_available_total',
                                        S + 'sponsorship.wallet:sponsor_available_total'),
}
SIDES = {'old': 0, 'new': 1}
#: The engine names are codes: each child writes one per record, and the parent, the ruling catalogue and
#: the report read them back. Unregistered, the scrubber hashed every one (R2 review: no ruling could
#: match, and the report filed every engine under 'other'). This is a literal, because the registry takes
#: literals only (test_replay_guards). RulingRegistryTest asserts every ENGINES key is registered.
scrub.register_codes((
    'verdict.build_verdict', 'award.verdict_disqualifier', 'award.proposed_award_amount',
    'award.course_start_unknown', 'resolution.doc_match_verdict', 'higher.match_verdict',
    'higher.student_higher_check', 'academic.student_slip_check', 'academic.semester_check',
    'academic.student_school_leaving_check', 'help.verdict_for_document', 'gaps.flags_summary',
    'shortlist.evaluate', 'courses.check_eligibility', 'courses.compute_student_merit',
    'courses.check_stpm_eligibility', 'requirements.required_documents', 'requirements.required_questions',
    'funding.classify_pathway', 'funding.estimate_funding', 'payments.schedule_row', 'payments.eligibility',
    'payments.default_amount', 'payments.paid_to_date', 'schedule.row_for', 'contracts.pick_schedule_row',
    'contracts.schedule_calendar', 'sponsor.sponsor_balance', 'sponsor.sponsor_available_total',
))

#: name -> adapter factory (R2). An adapter has `.name`, `.cases()` (keys) and `.run(key, months)`.
#: Each adapter module registers its codes at import, ABOVE the freeze below.
ADAPTERS = dict(_adapters.ADAPTERS)
#: The modules whose import registered their codes above the freeze below (this one adds ENGINES).
REGISTERED_BY = (vocab, rulings, _adapters)

# Every adapter is imported by now: no code may be registered after this line (scrub.register_codes).
scrub.freeze_registry()


class Unresolved(Exception):
    """One or more engine paths do not resolve in this tree."""


def path_for(name, side):
    return ENGINES[name][SIDES[side]]


def _import_path(path):
    module, _, attr = path.partition(':')
    obj = importlib.import_module(module)
    for part in attr.split('.'):
        obj = getattr(obj, part)
    if not callable(obj):
        raise TypeError(path)
    return obj


def resolve_tree(side):
    """{name: callable} for every engine in ``side``'s tree; Unresolved listing every miss."""
    found, missing = {}, []
    for name in sorted(ENGINES):
        try:
            found[name] = _import_path(path_for(name, side))
        except Exception:
            missing.append(f'{name} -> {path_for(name, side)}')
    if missing:
        raise Unresolved('; '.join(missing))
    return found


def main(argv=None, out=print):
    ap = argparse.ArgumentParser(description='Resolve every engine path in this tree (image build check).')
    ap.add_argument('--side', choices=sorted(SIDES), required=True)
    args = ap.parse_args(argv)
    try:
        found = resolve_tree(args.side)
    except Unresolved as exc:
        out(f'engine map: {args.side} tree UNRESOLVED: {exc}')
        return 1
    out(f'engine map: {args.side} tree resolves all {len(found)} engines')
    return 0


if __name__ == '__main__':
    import django
    django.setup()
    sys.exit(main(sys.argv[1:]))
