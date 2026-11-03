"""What offer exact-read S6 WOULD do to live records — a READ-ONLY dry run (2026-11-03).

Run through `offer_s4_dry_run.py --s6` (the same safety: ONE read-only transaction, always rolled back;
every write, Storage, Gemini and the usage meter refused — `offer_s4_dry_run.read_only_rollback`).

TWO PASSES.
  1. DEPLOY (every live application holding a live offer letter, or `--keys`): S6 changes no stored
     genuineness, but it changes how the stored status is READ. Per application, on the STORED data:
       * the Pathway band (`build_verdict`) under the OLD ladder (main 3bbeda41's `_pathway_red_chips`,
         frozen below: Name / IC `unreadable` red, the stacked "not official / mismatch" Pathway chip) and
         under the NEW one;
       * the submission block (`offer_not_official`, for a NOT-yet-submitted application only — the
         grandfather) under the OLD rule (not genuine AND the band below Probable, frozen below) and the
         NEW one (`blockers._offer_blocks`: not_offer_letter only);
       * each offer chip's colour, OLD (main's `documentFacts`, mirrored below) -> NEW (`offerFacts.ts`,
         mirrored below): name, ic, pathway, official, reportingDate.
  2. RE-SCORE (the corpus letters, `--eval-dir`): the S7 preview. Genuineness is re-scored in memory from
     the corpus's cached text with MODEL 1.23.0 (`offer_replay.authenticity_of`), put on an in-memory COPY
     of the document, and the doc-level outcomes re-read: status / doc_seen, the Official and Pathway
     chips, `offer_fails`, and the pick planners (`plan_bumi_realign`, `plan_offer_link`) — what S7's
     re-score would move. (The band after a re-score is S7's own dry run: the verdict reads the database.)

Prints ids and outcomes only — never a name, an IC, a programme or an institution line.

GO / STOP (the operator reads the `verdict` line at the end):
  STOP  any application's Pathway band FALLS (old -> new, stored data);
  STOP  any application becomes BLOCKED whose stored offer is not `not_offer_letter`;
  STOP  any NEWLY blocked application whose letter, re-scored at the current MODEL (pass 2), would NOT be
        `not_offer_letter` — S6 would block it on a stale stored call (review M8, 2026-11-03);
  STOP  any Name / IC chip turns red that was not red;
  STOP  any Pathway chip is red under the new rules;
  STOP  the tool hit a refused write / Storage / Gemini (it raises);
  REVIEW `blocked_on_a_stale_call`: an open application blocked BEFORE and AFTER S6 whose re-score would
        lift the fail (app 329's shape, a confirmation, a printout) — S7 should re-score these first;
  REVIEW (not a stop) every NEWLY blocked `not_offer_letter` application (rule 1 makes it a fail where the
        date bonus used to lift its band) and every UNBLOCKED one (each must be a stored `suspect`) — the
        lists go to the owner;
  GO    otherwise.

Usage (from halatuju_api/; the operator runs it, never an agent):
  python -I apps/scholarship/eval/offer_s4_dry_run.py --s6 [--eval-dir <corpus>] [--keys K1,K2] [--json]
Env: DATABASE_URL (the session pooler URL).
"""
import copy
import json
import os
from collections import Counter
from unittest import mock

_BANDS = ('Certain', 'Probable', 'Unsure', "Can't verify")


# ── main 3bbeda41, frozen: the rules S6 replaced ──────────────────────────────────────────────
def old_pathway_red_chips(application):
    """`verdict_ladder._pathway_red_chips` as on main 3bbeda41 (before S6)."""
    from apps.scholarship.pathway_engine import student_offer_check
    from apps.scholarship.verdict_engine import _latest_doc
    from apps.scholarship.verdict_ladder import _pathway_effective_step
    offer = _latest_doc(application, 'offer_letter')
    if offer is None:
        return 0
    chk = student_offer_check(offer)
    red = {'mismatch', 'unreadable'}
    n = (1 if chk['name'] in red else 0) + (1 if chk['ic'] in red else 0)
    not_official = _pathway_effective_step(application) > 0
    if not_official or (chk['pathway'] == 'mismatch' and application.pathway_confirmed_at is None):
        n += 1
    return n


def old_offer_blocks(application, band):
    """`services.blockers._offer_blocks` as on main 3bbeda41, given the OLD Pathway band."""
    from apps.scholarship import requirements
    from apps.scholarship.document_snapshot import latest_doc
    from apps.scholarship.pathway_engine import offer_official_status
    if not requirements.asks_for(application, 'document', 'offer_letter'):
        return False
    if (getattr(application, 'chosen_pathway', '') or '').strip().lower() == 'stpm':
        return False
    offer = latest_doc(application, 'offer_letter')
    if offer is None or offer_official_status(offer) != 'not_genuine':
        return False
    return band not in ('Certain', 'Probable')


def _tone(s):
    """`officerCockpit.factStatus`, the four tones."""
    if s in ('match', 'found', 'ok', 'current'):
        return 'verified'
    if s in ('partial', 'uncertain', 'pending', 'stale', 'unconfirmed', 'check', 'check_near', 'check_name',
             'check_one'):
        return 'partial'
    if s in ('mismatch', 'unreadable', 'not_found', 'rejected'):
        return 'not'
    return 'unknown'


def old_chips(chk, auth):
    """main's `documentFacts` offer branch."""
    not_official = bool(auth) and auth != 'genuine'
    fake = bool(auth) and auth.startswith('not_')
    eff = fake or (not_official and not chk.get('reporting_official'))
    out = {'name': _tone(chk.get('name')), 'ic': _tone(chk.get('ic'))}
    if chk.get('pathway'):
        out['pathway'] = 'not' if eff else _tone(chk.get('pathway'))
    if not_official:
        out['official'] = 'not' if fake else 'partial'
    return out


def new_chips(chk, auth):
    """`offerFacts.ts` (S6)."""
    fake = bool(auth) and auth.startswith('not_')

    def ident(s):
        return 'partial' if s == 'unreadable' else _tone(s)

    out = {'name': ident(chk.get('name')), 'ic': ident(chk.get('ic'))}
    if chk.get('pathway'):
        green = not fake and (chk.get('pathway') == 'match' or bool(chk.get('pathway_set_by_offer')))
        out['pathway'] = 'verified' if green else 'partial'
    if auth:
        out['official'] = 'verified' if auth == 'genuine' else ('not' if fake else 'partial')
    if not (chk.get('name') == 'pending' and chk.get('ic') == 'pending'):
        out['reportingDate'] = 'verified' if (chk.get('reporting_date') or '').strip() else 'partial'
    return out


def _shown_status(doc):
    """What the serializer sends the cockpit (`get_authenticity`): canonical, NOT CHECKED -> none."""
    from apps.scholarship.genuineness.bands import shown_status, stored_authenticity
    a = stored_authenticity(doc.vision_fields)
    return shown_status(a.get('status'), 'offer_letter', a.get('doc_seen', '')) or ''


# ── Pass 1: deploy ──────────────────────────────────────────────────────────────────────────
def pathway_band(application):
    from apps.scholarship.verdict_engine import build_verdict
    from apps.scholarship.verdict_narrative import _fact_band
    for fact in build_verdict(application):
        if fact.get('fact') == 'pathway':
            return _fact_band(fact)
    return '-'


def deploy_one(application):
    from apps.scholarship import verdict_ladder
    from apps.scholarship.document_snapshot import latest_doc
    from apps.scholarship.genuineness.bands import stored_status
    from apps.scholarship.pathway_engine import student_offer_check
    from apps.scholarship.services.blockers import _offer_blocks
    offer = latest_doc(application, 'offer_letter')
    if offer is None:
        return None
    with mock.patch.dict(verdict_ladder._LADDER_CHIPS, {'pathway': old_pathway_red_chips}), \
            mock.patch.object(verdict_ladder, '_OFFER_CHIP_RED', {'mismatch', 'unreadable'}):
        band_old = pathway_band(application)
    band_new = pathway_band(application)
    open_app = application.profile_completed_at is None
    chk = student_offer_check(offer)
    auth = _shown_status(offer)
    return {'app': application.pk, 'doc': offer.pk, 'stored': stored_status(offer.vision_fields) or 'unscored',
            'open': open_app, 'band_old': band_old, 'band_new': band_new,
            'blocked_old': open_app and old_offer_blocks(application, band_old),
            'blocked_new': open_app and _offer_blocks(application),
            'chips_old': old_chips(chk, auth), 'chips_new': new_chips(chk, auth),
            'set_by_offer': bool(chk.get('pathway_set_by_offer'))}


def judge(rows, rescored=None):
    """The GO / STOP verdict and its counts, from the deploy rows (+ `rescored`: app -> the status its live
    letter would carry if re-scored now, from pass 2; absent for an app outside the corpus)."""
    rescored = rescored or {}
    t, stop, review = Counter(), [], {'newly_blocked_not_offer': [], 'unblocked': [],
                                      'blocked_on_a_stale_call': []}
    for r in rows:
        t['applications'] += 1
        o, n = _BANDS.index(r['band_old']) if r['band_old'] in _BANDS else -1, \
            _BANDS.index(r['band_new']) if r['band_new'] in _BANDS else -1
        t['band:same' if o == n else ('band:up' if n < o else 'band:DOWN')] += 1
        if n > o >= 0:
            stop.append(f"band falls on app {r['app']} ({r['band_old']} -> {r['band_new']})")
        if r['blocked_new'] and not r['blocked_old']:
            t['newly_blocked'] += 1
            if r['stored'] == 'not_offer_letter':
                review['newly_blocked_not_offer'].append(r['app'])
                if rescored.get(r['app'], 'not_offer_letter') != 'not_offer_letter':
                    stop.append(f"app {r['app']} newly blocked on a stale call (re-scores "
                                f"{rescored[r['app']]})")
            else:
                stop.append(f"app {r['app']} newly blocked on a stored {r['stored']}")
        if (r['blocked_old'] and r['blocked_new']
                and rescored.get(r['app'], 'not_offer_letter') != 'not_offer_letter'):
            review['blocked_on_a_stale_call'].append(r['app'])
        if r['blocked_old'] and not r['blocked_new']:
            t['unblocked'] += 1
            review['unblocked'].append(r['app'])
            if r['stored'] != 'suspect':
                stop.append(f"app {r['app']} unblocked on a stored {r['stored']}")
        for chip in ('name', 'ic', 'pathway', 'official', 'reportingDate'):
            a, b = r['chips_old'].get(chip, '-'), r['chips_new'].get(chip, '-')
            if a != b:
                t[f'chip:{chip}:{a}->{b}'] += 1
        for chip in ('name', 'ic'):
            if r['chips_new'].get(chip) == 'not' and r['chips_old'].get(chip) != 'not':
                stop.append(f"app {r['app']} {chip} chip turns red")
        if r['chips_new'].get('pathway') == 'not':
            stop.append(f"app {r['app']} Pathway chip is red")
        t['set_by_offer'] += r['set_by_offer']
        t[f"stored:{r['stored']}"] += 1
    return ('STOP' if stop else 'GO'), stop, review, t


# ── Pass 2: re-score (the S7 preview) ───────────────────────────────────────────────────────
def rescore_one(eval_dir, key, doc):
    from apps.scholarship.eval.offer_replay import authenticity_of, production_text
    from apps.scholarship.eval.offer_s4_dry_run import plan_offer_doc
    from apps.scholarship.genuineness.bands import stored_authenticity
    from apps.scholarship.pathway_engine import offer_fails, student_offer_check
    text, _route = production_text(os.path.join(eval_dir, 'snapshots'), key)
    new_auth = authenticity_of(text)
    if new_auth is None:
        return {'key': key, 'doc': doc.pk, 'rescore': 'no_text'}
    d = copy.copy(doc)
    d.application = copy.deepcopy(doc.application)
    vf = copy.deepcopy(doc.vision_fields) if isinstance(doc.vision_fields, dict) else {}
    old = stored_authenticity(vf)
    vf['authenticity'] = new_auth
    d.vision_fields = vf
    chk = student_offer_check(d)
    before, after = plan_offer_doc(doc), plan_offer_doc(d)
    return {'key': key, 'doc': doc.pk, 'app': doc.application_id, 'live': doc.superseded_at is None,
            'status': f"{old.get('status') or 'unscored'}->{new_auth['status']}",
            'seen': f"{old.get('doc_seen') or '-'}->{new_auth.get('doc_seen') or '-'}",
            'fails': offer_fails(d), 'chips': new_chips(chk, _shown_status(d)),
            'realign': f"{before['realign']}->{after['realign']}", 'link': f"{before['link']}->{after['link']}"}


def run_s6(eval_dir, keys, *, all_live, session, out=print):
    from apps.scholarship.eval.offer_s4_dry_run import doc_id_of
    from apps.scholarship.models import ApplicantDocument, ScholarshipApplication
    deploy, rescored = [], []
    with session():
        if all_live:
            apps = (ScholarshipApplication.objects.filter(documents__doc_type='offer_letter',
                                                          documents__superseded_at__isnull=True)
                    .distinct().order_by('pk'))
        else:
            ids = [d for d in (doc_id_of(k) for k in keys) if d]
            apps = (ScholarshipApplication.objects.filter(documents__pk__in=ids).distinct().order_by('pk'))
        for app in apps:
            r = deploy_one(app)
            if r:
                deploy.append(r)
        for key in keys:
            did = doc_id_of(key)
            doc = (ApplicantDocument.objects.select_related('application', 'application__profile')
                   .filter(pk=did, doc_type='offer_letter').first()) if did else None
            if doc is not None:
                rescored.append(rescore_one(eval_dir, key, doc))
    now = {r['app']: r['status'].split('->')[-1] for r in rescored if r.get('live') and 'app' in r}
    verdict, stop, review, t = judge(deploy, now)
    moved = [r for r in rescored if r.get('status', '').split('->')[0] != r.get('status', '').split('->')[-1]]
    for r in deploy:
        changed = {c: f"{r['chips_old'].get(c, '-')}->{r['chips_new'].get(c, '-')}" for c in r['chips_new']
                   if r['chips_old'].get(c, '-') != r['chips_new'].get(c)}
        if changed or r['band_old'] != r['band_new'] or r['blocked_old'] != r['blocked_new']:
            out(f"  app={r['app']} doc={r['doc']} stored={r['stored']} band {r['band_old']}->{r['band_new']} "
                f"blocked {r['blocked_old']}->{r['blocked_new']} chips {changed or 'same'}")
    out(f'deploy pass: ' + ', '.join(f'{k}={v}' for k, v in sorted(t.items())))
    for r in moved:
        out(f"  RESCORE {r['key']} app={r.get('app')} {'live' if r.get('live') else 'superseded'} "
            f"{r['status']} ({r['seen']}) fails={r['fails']} chips={r['chips']} realign {r['realign']} "
            f"link {r['link']}")
    out(f'rescore pass (S7 preview): letters={len(rescored)} status_moved={len(moved)}')
    out(f"review: newly_blocked_not_offer={review['newly_blocked_not_offer']} unblocked={review['unblocked']} "
        f"blocked_on_a_stale_call={review['blocked_on_a_stale_call']}")
    for s in stop:
        out(f'  STOP: {s}')
    out(f'verdict: {verdict}')
    return {'verdict': verdict, 'stop': stop, 'review': review, 'totals': dict(t),
            'deploy': deploy, 'rescored': rescored}


def main(args, *, session, out=print):
    from apps.scholarship.eval.offer_s4_dry_run import s4_keys
    keys = [k.strip() for k in (args.keys or '').split(',') if k.strip()] or s4_keys(args.eval_dir, '.offer_expect.json')
    res = run_s6(args.eval_dir, keys, all_live=not args.keys, session=session,
              out=(lambda *_: None) if args.json else out)
    if args.json:
        out(json.dumps(res, indent=1, sort_keys=True, default=str))
    return 0 if res['verdict'] == 'GO' else 1
