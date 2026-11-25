"""#85 — re-score the live payslips the old cascade wrongly called not_salary, with NO read and NO AI call.

Before salary_doc 1.3.0 the "no recognisable payslip fields" reject ran before the statutory branch, so a
slip whose text showed two or more statutory deductions (KWSP / SOCSO / EIS / PCB) but none of the wage
labels was stored as `not_salary`, and the family was asked again for the earner's income. 1.3.0 accepts
such a slip when the deductions are WHOLE words (review round 1: 'EIS' inside LEISURE, a tax form's LHDN do
not count); the MyKad reject still runs first.

Selected: live (not superseded) `salary_slip` rows stored `not_salary` by model 1.2.x (>= 1.2.0, < 1.3.0),
whose stored markers show `statutory >= 2`, `wage == 0` and a recorded `kwsp`, with a reason that is not the
MyKad reason. Rows of the same shape from a model OLDER than 1.2.0 (before income declarations were
recognised) are only counted and listed by id, never written: a fresh read could make them a declaration.
Rows of that shape with NO model version (or one that does not parse) are listed as "unknown model", by id,
never written.

Per selected row:
  * stored OCR text (`ApplicantDocumentOcrText`) — the 1.3.0 scorer is run on that text, as a fresh read
    would be (declaration check and whole-word rule included); written only when it answers
    genuine/private, otherwise the row is left as it is ("text fails").
  * no stored text — the stored marker COUNTS cannot tell a whole word from a substring, so the row is
    listed as "needs eye check" and NOT written. Review round 2: after someone has looked at a slip, its
    id goes in `--eye-checked-ids`; ONLY those ids are written from their stored markers, ONLY when they are
    on this run's eye-check list, and each is re-checked as eligible under the row lock. An id that is not
    on the list (or no longer eligible) is reported and skipped — there is no flag that writes every
    no-text row.

DRY-RUN BY DEFAULT: prints document id + case number + from-model + the outcome, and the counts; never the
text or any personal data. `--apply` writes, each row re-fetched under a row lock and re-checked first.

    python manage.py rescore_salary_statutory                                    # dry run
    python manage.py rescore_salary_statutory --eye-checked-ids 4431             # dry run, incl. those ids
    python manage.py rescore_salary_statutory --apply --eye-checked-ids 4431     # write text rows + those ids
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.scholarship.genuineness.salary_doc import MODEL_VERSION, decide, salary_genuineness
from apps.scholarship.models import ApplicantDocument, ApplicantDocumentOcrText
from apps.scholarship.vision.authenticity import _family_auth

#: The 1.2.x models: income declarations recognised (1.2.0), but the no-wage reject before the statutory
#: branch (fixed in 1.3.0). Only rows scored by these are re-written.
FROM_MODEL = (1, 2)
FIXED_IN = (1, 3)
_MYKAD_REASON = 'MyKad'

TEXT_OK, TEXT_FAILS, NO_TEXT = 'text_ok', 'text_fails', 'no_text'


def _version(raw) -> tuple:
    try:
        return tuple(int(p) for p in str(raw or '').split('.')[:2])
    except ValueError:
        return ()


def _marker_count(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def _shape(doc):
    """(the stored authenticity, its model version) when this row is a not_salary the old order may have got
    wrong — >=2 statutory, 0 wage, not the MyKad reject — else None."""
    vf = doc.vision_fields if isinstance(doc.vision_fields, dict) else {}
    auth = vf.get('authenticity')
    if not isinstance(auth, dict) or auth.get('status') != 'not_salary':
        return None
    if str(auth.get('reason') or '').startswith(_MYKAD_REASON):
        return None
    m = auth.get('markers')
    if not isinstance(m, dict):
        return None
    stat, wage = _marker_count(m.get('statutory')), _marker_count(m.get('wage'))
    if stat is None or stat < 2 or wage != 0:
        return None
    return auth, _version(auth.get('model_version'))


def eligible(doc) -> bool:
    """A live 1.2.x salary-slip row of the shape above, with complete (>= 1.1.0) markers."""
    if doc.doc_type != 'salary_slip' or doc.superseded_at is not None:
        return False
    shape = _shape(doc)
    if shape is None:
        return False
    auth, version = shape
    return FROM_MODEL <= version < FIXED_IN and isinstance(auth['markers'].get('kwsp'), bool)


def is_older(doc) -> bool:
    """The same shape from a model before 1.2.0 (or 1.1.x markers): counted, never written."""
    shape = _shape(doc)
    return shape is not None and bool(shape[1]) and shape[1] < FROM_MODEL


def _stamp(auth, doc, basis):
    auth['rescored'] = {'by': 'rescore_salary_statutory', 'basis': basis,
                        'from_model_version': doc.vision_fields['authenticity'].get('model_version'),
                        'at': timezone.now().isoformat()}
    return auth


def from_text(doc, text):
    """The 1.3.0 answer on the stored OCR text: (TEXT_OK, auth) when genuine/private, else (TEXT_FAILS, None)."""
    sg = salary_genuineness(text)
    if (sg.get('status'), sg.get('family')) != ('genuine', 'private'):
        return TEXT_FAILS, None
    return TEXT_OK, _stamp(_family_auth(sg), doc, 'stored_ocr_text')


def from_markers(doc):
    """The stored result from the stored markers alone — ONLY for a row someone has eye-checked. The counts
    cannot tell a whole word from a substring, so the stored statutory count stands in for the whole-word one."""
    m = doc.vision_fields['authenticity']['markers']
    sg = decide({'statutory': m['statutory'], 'statutory_words': m['statutory'], 'wage': m['wage'],
                 'kwsp': m['kwsp'], 'mykad': False, 'govt': False, 'singapore': False, 'gig': False})
    return _stamp(_family_auth(sg), doc, 'stored_markers_eye_checked')


def rescored_authenticity(doc, text, eye_checked=False):
    """(outcome, the new stored result or None) for one eligible row. `eye_checked` is for THIS row only
    (its id was given in --eye-checked-ids and it is on the eye-check list)."""
    if text and text.strip():
        return from_text(doc, text)
    return NO_TEXT, (from_markers(doc) if eye_checked else None)


def _stored_text(doc_id):
    return (ApplicantDocumentOcrText.objects.filter(document_id=doc_id)
            .values_list('text', flat=True).first())


def is_unknown_model(doc) -> bool:
    """The same shape with no (or an unparsable) model version: counted by id, never written."""
    shape = _shape(doc)
    return shape is not None and not shape[1]


def rescore_candidates():
    """(eligible rows, older-model rows, unknown-model rows) of the shape above, each by id."""
    qs = ApplicantDocument.live(ApplicantDocument.objects.filter(
        doc_type='salary_slip', vision_fields__authenticity__status='not_salary'))
    docs = list(qs.only('id', 'application_id', 'doc_type', 'superseded_at', 'vision_fields').order_by('id'))
    return ([d for d in docs if eligible(d)], [d for d in docs if is_older(d)],
            [d for d in docs if is_unknown_model(d)])


def _write(doc_id, eye_checked=False):
    """Re-fetch under a row lock, re-check, re-score and save. True when written."""
    with transaction.atomic():
        doc = ApplicantDocument.objects.select_for_update().filter(pk=doc_id).first()
        if doc is None or not eligible(doc):
            return False
        _, auth = rescored_authenticity(doc, _stored_text(doc_id), eye_checked)
        if auth is None:
            return False
        doc.vision_fields = dict(doc.vision_fields, authenticity=auth)
        doc.save(update_fields=['vision_fields'])
        return True


_SAY = {TEXT_OK: 'not_salary -> genuine/private (stored OCR text, whole words)',
        TEXT_FAILS: 'stays not_salary (stored OCR text fails the whole-word rule)',
        NO_TEXT: 'needs eye check (no stored OCR text)'}


def _parse_ids(raw):
    if not raw:
        return set()
    try:
        return {int(p) for p in raw.split(',') if p.strip()}
    except ValueError:
        raise CommandError('--eye-checked-ids takes comma-separated document ids, e.g. 4431,8406')


class Command(BaseCommand):
    help = ('#85: re-score the live 1.2.x payslips called not_salary with >=2 statutory deductions, from '
            'stored OCR text (dry-run unless --apply; no read, no AI call; a row without text is written '
            'only when its id is in --eye-checked-ids).')

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Write the results. Without it nothing is saved.')
        parser.add_argument('--eye-checked-ids', default='',
                            help='Comma-separated document ids of no-text rows someone has looked at; only '
                                 'these are written from their stored markers, and only when they are on '
                                 'the eye-check list and still eligible.')

    def handle(self, *args, **opts):
        apply, asked = opts['apply'], _parse_ids(opts['eye_checked_ids'])
        docs, older, unknown = rescore_candidates()
        counts = {TEXT_OK: 0, TEXT_FAILS: 0, NO_TEXT: 0}
        eye_check, written, skipped = [], 0, []
        for doc in docs:
            text = _stored_text(doc.id)
            has_text = bool(text and text.strip())
            eye_checked = not has_text and doc.id in asked
            outcome, auth = rescored_authenticity(doc, text, eye_checked)
            counts[outcome] += 1
            if outcome == NO_TEXT:
                eye_check.append(doc.id)
            say = _SAY[outcome] + (' -> genuine/private (stored markers, eye-checked)' if eye_checked else '')
            self.stdout.write(f"  document {doc.id} case {doc.application_id} model "
                              f"{doc.vision_fields['authenticity'].get('model_version')}: {say}")
            if apply and auth is not None:
                if _write(doc.id, eye_checked):
                    written += 1
                elif eye_checked:
                    skipped.append(doc.id)                 # changed since selection: no longer eligible
        skipped += sorted(asked - set(eye_check))          # not on this run's eye-check list
        mode = 'APPLIED' if apply else 'DRY-RUN (nothing written; --apply to write)'
        self.stdout.write(f'rescore_salary_statutory: {mode}; model {MODEL_VERSION}; selected={len(docs)} '
                          f'text_ok={counts[TEXT_OK]} text_fails={counts[TEXT_FAILS]} '
                          f'needs_eye_check={counts[NO_TEXT]} written={written}')
        if eye_check:
            self.stdout.write(f'  needs eye check (written only when named in --eye-checked-ids): ids={eye_check}')
        if skipped:
            self.stdout.write(f'  eye-checked ids skipped (not on the eye-check list, or no longer eligible): '
                              f'ids={sorted(skipped)}')
        self.stdout.write(f'  older model (< 1.2.0, never written): count={len(older)} '
                          f'ids={[d.id for d in older]}')
        self.stdout.write(f'  unknown model (no model version, never written): count={len(unknown)} '
                          f'ids={[d.id for d in unknown]}')
