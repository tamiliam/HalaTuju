"""Split a combined results upload into its parts, or move one whole results document — a ONE-TIME
TEAM command (owner approval by name, 2026-10-28; third results route follow-up).

WHY. Some students uploaded ONE file holding several results documents (an SPM slip on page 1, an
STPM certificate on page 2). A scan is read on page 1 only, so the other results are never seen,
and a degree-bound student can be asked for STPM results she has already sent. The team splits
each such file into parts and files each part in the right card, as it already moved whole slips
(roadmap §7a D15). One whole document can also be MOVED between the two results cards.

PREVIEW BY DEFAULT: it prints exactly what it would do and writes nothing (a split downloads the
original from Storage to count its pages — a read). ``--apply`` performs it.

    python manage.py split_combined_results --plan split_plan.json            # preview
    python manage.py split_combined_results --plan '[{"app": 254, ...}]'      # inline JSON
    python manage.py split_combined_results --plan split_plan.json --apply    # perform it
    SPLIT_RESULTS_PLAN='[...]' python manage.py split_combined_results         # plan from the env

The plan is a JSON list (or ``{"items": [...]}``) of:

    split: {"app": 254, "doc": 3020, "parts": [{"pages": [1], "slot": "results_slip"},
                                               {"pages": [2], "slot": "higher_results", "kind": "stpm"}]}
    move:  {"app": 252, "doc": 3615, "to": "higher_results", "kind": "stpm"}

WHAT A SPLIT DOES (each item atomic; a refused item never stops the others):
  * each part is a NEW PDF (pypdf — the PDF library the production image carries; PyMuPDF is
    eval-only) uploaded to Storage under a fresh key in the upload's own scheme
    (``storage.build_doc_key``: ``<org>/<app>/<slot>/<uuid>``), and a NEW `ApplicantDocument`
    with the original's application + household member, ``original_filename`` "<orig> (pages 2-3)",
    ``results_kind`` for the higher card, and NO read (empty ``vision_fields``, NULL run stamps) —
    the state `results_route.refile_*` leaves, so the live hourly self-heal reads it on the LIVE
    service. Nothing here calls Gemini or Vision.
  * the ORIGINAL is kept as history: superseded, ``superseded_by`` the part filed in its OWN card
    (else the first part). Pages given to no part stay in the original only (named in the note).
  * one live document per card, with NO contest (review fix 1): an item whose target card already
    holds a live document other than the one being split or moved is REFUSED (the preview names
    it), so every part becomes its card's live document and is read.
  * one reviewer note per part (kind ``team_split``, ``by: 'team'``).
A MOVE reuses `results_route._refile_to_higher_locked` / `refile_to_spm` with ``by='team'``.

SUBMITTED applications keep a frozen requirement (`requirements.freeze`). When an item files a
document into the higher card of a submitted application whose snapshot does not already require
it, the snapshot's documents are re-mapped by `results_route.map_documents` — the same D12/D14
rule the live path applies — ONLY for a student whose recorded results are tertiary (the
'required' arm: higher results required, SPM slip optional; never 'required_with_slip' for an
SPM-only record), and only once the higher document is live. The change and the arm are recorded on
the snapshot (``amended``). Not submitted → no snapshot change. A document is never taken OUT of a
higher card the submitted snapshot requires. Then `sync_resolution_items`.

IDEMPOTENT: after a run the original is superseded (a split) or already in its new card (a move),
so the same plan run again is refused item by item and writes nothing.
"""
from __future__ import annotations

import io
import json
import logging
import os
import uuid

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.scholarship import promotion, results_route, storage
from apps.scholarship.document_snapshot import live_docs
from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
from apps.scholarship.models.documents import RESULTS_KIND_CHOICES
from apps.scholarship.review_sla import TERMINAL

logger = logging.getLogger('apps.scholarship.results_route')

ENV_VAR = 'SPLIT_RESULTS_PLAN'
SLOTS = ('results_slip', 'higher_results')
KINDS = frozenset(k for k, _ in RESULTS_KIND_CHOICES)


class Refused(Exception):
    """An item the guards refuse — reported, the others carry on."""


# ── The plan ───────────────────────────────────────────────────────────────────────────────────


def load_plan(raw):
    """The plan's items from ``raw``: inline JSON (starts with ``[`` or ``{``) or a file path."""
    raw = (raw or '').strip()
    if not raw:
        raise CommandError(f'No plan: pass --plan <json-file-or-inline> or set {ENV_VAR}.')
    if raw[0] not in '[{':
        if not os.path.isfile(raw):
            raise CommandError(f'Plan file not found: {raw}')
        with open(raw, encoding='utf-8') as fh:
            raw = fh.read()
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise CommandError(f'The plan is not valid JSON: {exc}') from exc
    items = data.get('items') if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise CommandError('The plan must be a JSON list of items (or {"items": [...]}).')
    return items


def _page_label(pages):
    if len(pages) == 1:
        return f'page {pages[0]}'
    if pages == list(range(pages[0], pages[-1] + 1)):
        return f'pages {pages[0]}-{pages[-1]}'
    return 'pages ' + ', '.join(str(p) for p in pages)


def _check_kind(slot, kind):
    if slot not in SLOTS:
        raise Refused(f'slot {slot!r} is not one of {", ".join(SLOTS)}')
    if slot == 'higher_results' and kind not in KINDS:
        raise Refused(f'higher_results needs a kind in {sorted(KINDS)} (got {kind!r})')
    if slot == 'results_slip' and kind:
        raise Refused('an SPM results slip takes no kind')


def _check_parts(parts):
    """The parts' shape: pages are whole numbers, no page twice, one part per card."""
    if not isinstance(parts, list) or not parts:
        raise Refused('a split needs a non-empty "parts" list')
    seen, slots = set(), set()
    for part in parts:
        pages = part.get('pages') if isinstance(part, dict) else None
        if not isinstance(pages, list) or not pages or not all(
                isinstance(p, int) and not isinstance(p, bool) and p >= 1 for p in pages):
            raise Refused(f'part {part!r}: "pages" must be a list of page numbers from 1')
        if len(set(pages)) != len(pages) or seen & set(pages):
            raise Refused(f'part {part!r}: a page appears twice (parts may not overlap)')
        seen |= set(pages)
        _check_kind(part.get('slot'), part.get('kind') or '')
        if part['slot'] in slots:
            raise Refused(f'two parts for the {part["slot"]} card (one live document per card)')
        slots.add(part['slot'])


def _target(item, app, doc):
    """Guards common to both item kinds; returns 'split' or 'move'."""
    if doc.application_id != app.id:
        raise Refused(f'document {doc.id} does not belong to application {app.id}')
    if doc.superseded_at is not None:
        raise Refused(f'document {doc.id} is not live (superseded) — already done?')
    if app.status in TERMINAL:
        raise Refused(f'application status {app.status!r} is final; not touched')
    if doc.doc_type not in SLOTS:
        raise Refused(f'document {doc.id} is a {doc.doc_type!r}, not a results upload')
    if 'parts' in item and 'to' not in item:
        _check_parts(item['parts'])
        return 'split'
    if 'to' in item and 'parts' not in item:
        _check_kind(item['to'], item.get('kind') or '')
        if item['to'] == doc.doc_type:
            raise Refused(f'document {doc.id} is already in {doc.doc_type} — already done?')
        return 'move'
    raise Refused('an item needs either "parts" (a split) or "to" (a move)')


def _resolve(item):
    if not isinstance(item, dict) or not isinstance(item.get('app'), int) \
            or not isinstance(item.get('doc'), int):
        raise Refused(f'an item needs integer "app" and "doc" (got {item!r})')
    app = ScholarshipApplication.objects.filter(pk=item['app']).first()
    if app is None:
        raise Refused(f'no application {item["app"]}')
    doc = ApplicantDocument.objects.filter(pk=item['doc']).first()
    if doc is None:
        raise Refused(f'no document {item["doc"]}')
    return app, doc, _target(item, app, doc)


# ── The PDF ────────────────────────────────────────────────────────────────────────────────────


def _is_pdf(doc):
    return (doc.content_type or '').lower() == 'application/pdf' \
        or (doc.original_filename or '').lower().endswith('.pdf')


def _source_pdf(doc):
    """``(reader, page_count)`` of the original. Refuses an image: a photo or scan holds ONE page as
    far as a part is concerned, and a multi-page image (TIFF) is not something students upload — so
    an image is never split; move it whole instead."""
    if not _is_pdf(doc):
        raise Refused(f'document {doc.id} is {doc.content_type or "of unknown type"}, not a PDF; '
                      'an image cannot be split (move it whole instead)')
    data = storage.download_object(doc.storage_path)
    if not data:
        raise Refused(f'document {doc.id}: could not download the original from Storage')
    if not data.lstrip()[:5].startswith(b'%PDF'):
        raise Refused(f'document {doc.id}: the stored bytes are not a PDF')
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            raise Refused(f'document {doc.id}: the PDF is password-protected')
        return reader, len(reader.pages)
    except Refused:
        raise
    except Exception as exc:        # any pypdf failure on a damaged file refuses THIS item only
        raise Refused(f'document {doc.id}: the PDF could not be opened ({type(exc).__name__})') from exc


def _part_bytes(reader, pages):
    from pypdf import PdfWriter
    try:
        writer = PdfWriter()
        for p in pages:
            writer.add_page(reader.pages[p - 1])
        buf = io.BytesIO()
        writer.write(buf)
        return buf.getvalue()
    except Exception as exc:        # a page pypdf cannot copy refuses THIS item only
        raise Refused(f'{_page_label(pages)} could not be extracted ({type(exc).__name__})') from exc


def _unassigned(parts, count):
    used = {p for part in parts for p in part['pages']}
    return [p for p in range(1, count + 1) if p not in used]


def _check_pages(parts, count):
    for part in parts:
        bad = [p for p in part['pages'] if p > count]
        if bad:
            raise Refused(f'page(s) {bad} do not exist (the PDF has {count} page(s))')


# ── The cards (review fix 1) ───────────────────────────────────────────────────────────────────


def _targets(action, item):
    return [p['slot'] for p in item['parts']] if action == 'split' else [item['to']]


def check_cards(app, doc, action, item):
    """Refuse an item whose target card already holds a LIVE document other than ``doc`` itself:
    a part or a moved document must BECOME the card's live document — a promotion contest it lost
    would leave it as history, never read (review fix 1). And refuse taking a document OUT of a
    higher card the submitted snapshot requires (review fix 2), which would leave a gap it owes."""
    targets = _targets(action, item)
    for slot in targets:
        blocking = list(live_docs(app, slot).exclude(id=doc.id).values_list('id', flat=True))
        if blocking:
            raise Refused(f'the {slot} card already holds live document(s) '
                          f'{", ".join(f"#{i}" for i in blocking)}; resolve that first')
    if doc.doc_type == 'higher_results' and 'higher_results' not in targets \
            and _snapshot_docs(app).get('higher_results') == 'required':
        raise Refused(f'document {doc.id} would leave the higher card that the submitted '
                      'requirement makes required')


# ── The submitted snapshot ─────────────────────────────────────────────────────────────────────


def _snapshot_docs(app):
    snap = app.requirements_snapshot if results_route.submitted(app) else None
    docs = snap.get('documents') if isinstance(snap, dict) else None
    return docs if isinstance(docs, dict) else {}


def snapshot_change(app):
    """``((before, after, arm), reason)`` for a SUBMITTED application's frozen requirement once a
    document is live in the higher card; ``(None, reason)`` when nothing changes. Review fix 2: only
    for a student whose RECORDED results are tertiary (`results_route.held_kind`) — never the
    `map_documents` 'required_with_slip' arm, which would make higher results required for a
    student who recorded SPM only. ``arm`` is `results_route.higher_need`'s answer."""
    if not results_route.submitted(app):
        return None, 'not submitted'
    docs = _snapshot_docs(app)
    if not docs:
        return None, 'no frozen snapshot'
    if docs.get('higher_results') == 'required':
        return None, 'already requires higher results'
    for memo in ('_requirements_memo', '_results_destination'):
        app.__dict__.pop(memo, None)
    if not results_route.held_kind(app):
        return None, f'recorded results are {results_route.held(app) or "none"}, not tertiary'
    arm = results_route.higher_need(app)
    if arm != 'required':
        return None, f'map_documents arm {arm or "none"} (post-SPM course or no higher card)'
    after = results_route.map_documents(app, dict(docs))
    if after == docs:
        return None, 'map_documents leaves it unchanged (SPM-only intake or no results asked)'
    return (docs, after, arm), 'map_documents arm required'


def _update_snapshot(app, change, item_note):
    before, after, arm = change
    snap = dict(app.requirements_snapshot)
    amended = list(snap.get('amended') or [])
    amended.append({'at': timezone.now().isoformat(), 'by': 'team', 'why': item_note, 'arm': arm,
                    'before': {k: before.get(k) for k in SLOTS},
                    'after': {k: after.get(k) for k in SLOTS}})
    app.requirements_snapshot = {**snap, 'documents': after, 'amended': amended}
    app.save(update_fields=['requirements_snapshot'])
    app.__dict__.pop('_requirements_memo', None)
    logger.info('AUDIT results_snapshot_amended app=%s by=team before=%s after=%s', app.id,
                {k: before.get(k) for k in SLOTS}, {k: after.get(k) for k in SLOTS})


# ── Apply ──────────────────────────────────────────────────────────────────────────────────────


def _upload_parts(app, doc, reader, parts):
    """Upload every part BEFORE any row is written; returns ``[(part, path, size)]``. Any failure
    (a refused upload, an exception, a page that will not copy) deletes every object uploaded so
    far and refuses the item (review fix 4)."""
    out = []
    try:
        for part in parts:
            data = _part_bytes(reader, part['pages'])
            path = storage.build_doc_key(app, app.id, part['slot'], uuid.uuid4().hex)
            if not storage.upload_object(path, data, 'application/pdf'):
                raise Refused(f'document {doc.id}: Storage upload failed; nothing written')
            out.append((part, path, len(data)))
    except Exception as exc:
        if out:
            storage.delete_objects([p for _, p, _ in out])
        if isinstance(exc, Refused):
            raise
        raise Refused(f'document {doc.id}: Storage upload failed ({type(exc).__name__}); '
                      'nothing written') from exc
    return out


def _create_parts(app, doc, uploaded, unassigned):
    stem = doc.original_filename or f'document {doc.id}'
    made = []
    for part, path, size in uploaded:
        made.append(ApplicantDocument.objects.create(
            application=app, doc_type=part['slot'], household_member=doc.household_member,
            results_kind=(part.get('kind') or '') if part['slot'] == 'higher_results' else '',
            storage_path=path, content_type='application/pdf', size=size,
            original_filename=f'{stem} ({_page_label(part["pages"])})'[:255]))
    own = next((m for m in made if m.doc_type == doc.doc_type), made[0])
    ApplicantDocument.objects.filter(id=doc.id).update(superseded_at=timezone.now(),
                                                       superseded_by=own)
    for part_doc, (part, _, _) in zip(made, uploaded):
        results_route._note(app, 'team_split', by='team', document_id=part_doc.id,
                            from_document_id=doc.id, pages=part['pages'], slot=part['slot'],
                            results_kind=part_doc.results_kind, unassigned_pages=unassigned)
        logger.info('AUDIT results_split app=%s from_doc=%s doc=%s slot=%s pages=%s kind=%s '
                    'unassigned=%s', app.id, doc.id, part_doc.id, part['slot'],
                    part['pages'], part_doc.results_kind, unassigned)
    return made


def apply_split(app, doc, item, reader, count):
    parts = item['parts']
    unassigned = _unassigned(parts, count)
    uploaded = _upload_parts(app, doc, reader, parts)
    try:
        with transaction.atomic():
            locked = ApplicantDocument.objects.select_for_update().get(pk=doc.pk)
            if locked.superseded_at is not None:
                raise Refused(f'document {doc.id} was superseded meanwhile')
            check_cards(app, locked, 'split', item)          # again, under the lock
            made = _create_parts(app, locked, uploaded, unassigned)
            _finish(app, any(p['slot'] == 'higher_results' for p in parts), f'split doc {doc.id}')
    except Exception:
        storage.delete_objects([p for _, p, _ in uploaded])
        raise
    return made


def apply_move(app, doc, item):
    to, kind = item['to'], item.get('kind') or ''
    with transaction.atomic():
        locked = ApplicantDocument.objects.select_for_update().get(pk=doc.pk)
        if locked.superseded_at is not None or locked.doc_type == to:
            raise Refused(f'document {doc.id} moved or superseded meanwhile')
        check_cards(app, locked, 'move', item)               # again, under the lock
        fields = {'from': locked.doc_type, 'from_document_id': locked.id, 'pages': 'all',
                  'slot': to}
        if to == 'higher_results':
            moved = results_route._refile_to_higher_locked(
                app, locked, kind, promotion, live_docs, ApplicantDocument, by='team', **fields)
        else:
            moved = results_route.refile_to_spm(app, locked, by='team', **fields)
        _finish(app, to == 'higher_results', f'move doc {doc.id}')
    return moved


def _finish(app, into_higher, why):
    # Review fix 2(b): only once a higher-results document is actually LIVE.
    if into_higher and live_docs(app, 'higher_results').exists():
        change, _ = snapshot_change(app)
        if change:
            _update_snapshot(app, change, why)
    from apps.scholarship.resolution import sync_resolution_items
    sync_resolution_items(app)


# ── Preview ────────────────────────────────────────────────────────────────────────────────────


def _live_in(app, slot, exclude_id):
    rows = live_docs(app, slot).exclude(id=exclude_id)
    return [f'#{d.id} ({"read" if d.vision_fields else "unread"})' for d in rows] or ['none']


def describe(app, doc, action, item, count=None):
    """The preview lines for one item (ids and states only — never a name or an IC)."""
    lines = [f'  status={app.status} submitted={"yes" if results_route.submitted(app) else "no"} '
             f'gift_asks_higher={"yes" if results_route.gift_asks_higher(app) else "no (D16c)"} '
             f'current_slot={doc.doc_type} content_type={doc.content_type or "?"}']
    targets = _targets(action, item)
    if action == 'split':
        lines.append(f'  SPLIT {count} page(s) into a new PDF per part; original #{doc.id} kept as '
                     'history (superseded)')
        for p in item['parts']:
            kind = f' kind={p.get("kind")}' if p['slot'] == 'higher_results' else ''
            lines.append(f'    {_page_label(p["pages"])} -> {p["slot"]}{kind} (new document, unread)')
        lines.append(f'    unassigned pages (stay in the original only): '
                     f'{_unassigned(item["parts"], count) or "none"}')
    else:
        kind = f' kind={item.get("kind")}' if item['to'] == 'higher_results' else ''
        lines.append(f'  MOVE #{doc.id} whole: {doc.doc_type} -> {item["to"]}{kind} (read cleared)')
    for slot in targets:
        lines.append(f'  live in {slot} now (besides this document): {", ".join(_live_in(app, slot, doc.id))}')
    change, why = snapshot_change(app) if 'higher_results' in targets else (None, 'nothing filed in the higher card')
    lines.append('  snapshot change: ' + (f'yes {dict((k, change[0].get(k)) for k in SLOTS)} -> '
                                          f'{dict((k, change[1].get(k)) for k in SLOTS)} ({why})'
                                          if change else f'no ({why})'))
    # Review fix 3, report-only: the semester-result ask reads only `semester_result` uploads, so
    # this item cannot change it — printed so the lead sees whether that ask may return.
    from apps.scholarship.income_engine import semester_result_gap
    lines.append(f'  semester_result_gap after: {"yes" if semester_result_gap(app) else "no"} '
                 '(reads only semester_result uploads; unchanged by this item)')
    return lines


class Command(BaseCommand):
    help = ('ONE-TIME team command: split a combined results PDF into parts filed in the right '
            'results card, or move one whole results document. Preview unless --apply.')

    def add_arguments(self, parser):
        parser.add_argument('--plan', default='',
                            help=f'JSON file path or inline JSON (else the {ENV_VAR} env var).')
        parser.add_argument('--apply', action='store_true', help='Perform it (default: preview).')

    def handle(self, *args, **opts):
        items = load_plan(opts['plan'] or os.environ.get(ENV_VAR, ''))
        do_apply, done, refused = opts['apply'], 0, 0
        for item in items:
            label = f'app {item.get("app")} doc {item.get("doc")}' if isinstance(item, dict) else '?'
            try:
                done += self._one(item, label, do_apply)
            except Refused as exc:
                refused += 1
                self.stdout.write(self.style.WARNING(f'{label}: REFUSED — {exc}'))
                logger.info('AUDIT results_split_refused %s reason=%s', label, exc)
        mode = 'APPLIED' if do_apply else 'PREVIEW (nothing written; pass --apply)'
        self.stdout.write(f'{mode}: {done} item(s) {"done" if do_apply else "ready"}, '
                          f'{refused} refused.')

    def _one(self, item, label, do_apply):
        app, doc, action = _resolve(item)
        reader = count = None
        check_cards(app, doc, action, item)
        if action == 'split':
            reader, count = _source_pdf(doc)
            _check_pages(item['parts'], count)
        self.stdout.write(f'{label}: {action.upper()}')
        for line in describe(app, doc, action, item, count):
            self.stdout.write(line)
        if not do_apply:
            return 1
        if action == 'split':
            made = apply_split(app, doc, item, reader, count)
            self.stdout.write(self.style.SUCCESS(
                f'  done: new document(s) {", ".join(f"#{m.id}" for m in made)}; #{doc.id} superseded'))
        else:
            moved = apply_move(app, doc, item)
            self.stdout.write(self.style.SUCCESS(f'  done: #{moved.id} now in {moved.doc_type}'))
        return 1
