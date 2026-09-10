'use client'

// Programme → Configuration → "How it's advertised". The FOURTH tab (owner, 2026-09-09).
//
// ⚠⚠ THE ADVERTISED BAR IS DELIBERATELY STRICTER THAN THE ENGINE, AND THIS SCREEN MUST NEVER
// DERIVE FROM THE RULES TAB. Sprint 8 (2026-05-24) ruled that the public page advertises 5 A's /
// PNGK 3.0 while `shortlisting.evaluate()` runs 4 A- / PNGK 2.9, to catch near-misses; the owner
// reaffirmed it on 2026-09-09. Anything that reads a threshold here reverses a standing ruling.
//
// ⚠ BLANK MEANS THE PLATFORM DEFAULT, and blank is the correct state for BrightPath. The stored
// map holds ONLY what this organisation wrote — never a copied default, which rots the day the
// platform's own wording moves (the `OrganisationConfiguration` rule).
//
// ⚠ ALL-OR-NOTHING PER LANGUAGE. Title + intro + at least one bullet, or nothing at all. Per-FIELD
// fallback would render the platform's "Apply for B40 Education Assistance" above Sabah's own
// criteria — one gift's heading over another gift's terms, with nothing failing. The server
// refuses it (`apply_copy.normalise`); this screen only has to explain it.
//
// ⚠ EVERY SUB-COMPONENT IS AT MODULE SCOPE. A component declared inside the body is a NEW type on
// every render, so React unmounts and remounts it — the inputs lose focus on each keystroke. That
// is the 2026-07-21 invite-form defect, repeated on 2026-09-03. Do not move these inside.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useSelectedProgramme } from '@/lib/useSelectedProgramme'
import InfoBox from '@/components/InfoBox'
import ChooseProgramme from '@/components/admin/ChooseProgramme'
import SaveBar, { SAVE_BAR_PRIMARY, SAVE_BAR_SECONDARY } from '@/components/admin/SaveBar'
import {
  draftApplyCopy, updateAdminProgramme,
  type AdminApplyCopy, type AdminApplyCopyBlock, type AdminProgramme,
} from '@/lib/admin-api'

const LOCALES = ['en', 'ms', 'ta'] as const
type Loc = (typeof LOCALES)[number]

/** Server caps, mirrored so the box can stop a reader before the round trip. The SERVER is the
 *  guarantee — a form `maxLength` is a courtesy (the `parents_occupation` lesson, 2026-06-07). */
const MAX_TITLE = 120
const MAX_INTRO = 400
const MAX_BULLET = 200
const MAX_BULLETS = 8

interface Block { title: string; intro: string; criteria: string[] }
type Draft = Record<Loc, Block>

const EMPTY_BLOCK: Block = { title: '', intro: '', criteria: [''] }

type Outcome =
  | { kind: 'idle' }
  | { kind: 'saved' }
  | { kind: 'cleared' }
  | { kind: 'drafted' }
  | { kind: 'error'; message: string }

/** Which dialog is open. `null` = none. Two questions, one dialog: both are "this replaces
 *  something you cannot get back by pressing Cancel afterwards". */
type Ask = null | 'clear' | 'overwrite'

/** Stored map → editable draft. A missing locale is BLANK, never the English text: this is an
 *  editor, and pre-filling would silently promote English into a field nobody typed. */
export function toDraft(copy: AdminApplyCopy | undefined | null): Draft {
  const out = {} as Draft
  for (const loc of LOCALES) {
    const b = copy?.[loc]
    out[loc] = b
      ? { title: b.title || '', intro: b.intro || '', criteria: [...(b.criteria ?? [])] }
      : { ...EMPTY_BLOCK, criteria: [''] }
  }
  return out
}

/** Draft → the payload. A wholly blank language is OMITTED, which is how "use the default" is
 *  said; blank bullets are dropped so a tidied-up row is not an error. */
export function toPayload(draft: Draft): AdminApplyCopy {
  const out: AdminApplyCopy = {}
  for (const loc of LOCALES) {
    const b = draft[loc]
    const title = b.title.trim()
    const intro = b.intro.trim()
    const criteria = b.criteria.map(c => c.trim()).filter(Boolean)
    if (title || intro || criteria.length) out[loc] = { title, intro, criteria }
  }
  return out
}

/** Which languages hold something. Drives the confirm dialog's list, so a reader is told what
 *  they are about to lose BY NAME rather than "your wording". */
export function writtenLocales(copy: AdminApplyCopy): Loc[] {
  return LOCALES.filter(l => Boolean(copy[l]))
}

/** Has the ENGLISH been edited since the last save?
 *
 *  ⚠ THE DRAFT IS MADE FROM THE SAVED ENGLISH, because the server reads the stored row — so
 *  drafting over unsaved English would translate wording the reader can no longer see, and the
 *  result would look like a bad translation rather than a stale one. Asked about English ALONE:
 *  editing Malay must not lock the Tamil button. */
export function englishUnsaved(draft: Draft, saved: Draft): boolean {
  return JSON.stringify(toPayload(draft).en ?? null) !== JSON.stringify(toPayload(saved).en ?? null)
}

// ── Module-scope pieces (see the remount warning above) ──────────────────────────────────────

function ConfirmDialog({ ask, languages, busy, onCancel, onConfirm, t }: {
  ask: Exclude<Ask, null>
  languages: string
  busy: boolean
  onCancel: () => void
  onConfirm: () => void
  t: (k: string, p?: Record<string, string>) => string
}) {
  const clearing = ask === 'clear'
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      data-testid={`confirm-${ask}`}
      onClick={() => !busy && onCancel()}>
      <div className="w-full max-w-md rounded-2xl bg-ground-0 p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}>
        <h2 className={`text-lg font-semibold ${clearing ? 'text-critical-700' : 'text-ground-900'}`}>
          {t(clearing ? 'admin.applyCopy.clearTitle' : 'admin.applyCopy.overwriteTitle')}
        </h2>
        <p className="mt-2 text-sm text-ground-700">
          {t(clearing ? 'admin.applyCopy.clearBody' : 'admin.applyCopy.overwriteBody')}
        </p>
        {/* ⚠ NAME THE LANGUAGES. The button lives on ONE language's tab and clears ALL of them —
            somebody standing on an empty Malay form has no way to know English goes too. */}
        {clearing && languages && (
          <p className="mt-2 text-sm text-ground-700" data-testid="clear-languages">
            {t('admin.applyCopy.clearLanguages', { languages })}
          </p>
        )}
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" onClick={onCancel} disabled={busy}
            className="rounded-lg px-4 py-2 text-sm font-medium text-ground-600 hover:text-ground-900 disabled:opacity-50">
            {t('common.cancel')}
          </button>
          <button type="button" onClick={onConfirm} disabled={busy}
            data-testid={`confirm-${ask}-go`}
            className={clearing
              ? 'rounded-lg bg-critical-fill px-4 py-2 text-sm font-semibold text-critical-fill-ink hover:bg-critical-fill-hover disabled:opacity-50'
              : SAVE_BAR_PRIMARY}>
            {t(clearing ? 'admin.applyCopy.clearCta' : 'admin.applyCopy.overwriteCta')}
          </button>
        </div>
      </div>
    </div>
  )
}


function Bullets({ value, onChange, t }: {
  value: string[]
  onChange: (next: string[]) => void
  t: (k: string, p?: Record<string, string>) => string
}) {
  const rows = value.length ? value : ['']
  return (
    <div className="space-y-2">
      {rows.map((line, i) => (
        <div key={i} className="flex items-start gap-2">
          <input
            className="input flex-1" maxLength={MAX_BULLET} value={line}
            data-testid={`bullet-${i}`}
            placeholder={t('admin.applyCopy.bulletPlaceholder')}
            onChange={(e) => {
              const next = [...rows]; next[i] = e.target.value; onChange(next)
            }} />
          <button type="button" className="btn-ghost px-2 py-2"
            aria-label={t('admin.applyCopy.removeBullet')}
            onClick={() => onChange(rows.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      {rows.length < MAX_BULLETS && (
        <button type="button" className="text-sm text-primary-600 hover:underline"
          data-testid="add-bullet"
          onClick={() => onChange([...rows, ''])}>
          + {t('admin.applyCopy.addBullet')}
        </button>
      )}
    </div>
  )
}

function LangTabs({ active, onPick, t }: {
  active: Loc
  onPick: (l: Loc) => void
  t: (k: string) => string
}) {
  return (
    <div className="flex gap-1 border-b border-ground-200 mb-4" role="tablist">
      {LOCALES.map(l => (
        <button key={l} type="button" role="tab" aria-selected={active === l}
          data-testid={`lang-${l}`}
          className={`px-3 py-2 text-sm border-b-2 -mb-px ${active === l
            ? 'border-primary-600 text-primary-700 font-medium'
            : 'border-transparent text-ground-500 hover:text-ground-800'}`}
          onClick={() => onPick(l)}>
          {t(`admin.applyCopy.lang.${l}`)}
        </button>
      ))}
    </div>
  )
}

// ── The tab ──────────────────────────────────────────────────────────────────────────────────

export default function ApplyCopyTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const { programme, programmes, loading, mustChoose, select } = useSelectedProgramme()

  const [lang, setLang] = useState<Loc>('en')
  const [draft, setDraft] = useState<Draft>(() => toDraft(undefined))
  const [saved, setSaved] = useState<Draft>(() => toDraft(undefined))
  const [flagged, setFlagged] = useState<string[]>([])
  const [busy, setBusy] = useState(false)
  const [ask, setAsk] = useState<Ask>(null)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  const programmeId = programme?.id ?? null

  // Seed from the gift the scope hook already fetched — `getAdminProgrammes` carries `apply_copy`,
  // so there is no second request to make.
  useEffect(() => {
    const asDraft = toDraft(programme?.apply_copy)
    setDraft(asDraft)
    setSaved(asDraft)
    setFlagged(programme?.apply_copy_sensitive ?? [])
    setAsk(null)
    setOutcome({ kind: 'idle' })
  }, [programmeId, programme])

  const dirty = useMemo(
    () => JSON.stringify(toPayload(draft)) !== JSON.stringify(toPayload(saved)),
    [draft, saved])
  const configured = useMemo(() => Boolean(toPayload(saved).en), [saved])

  const patch = useCallback(async (payload: AdminApplyCopy, ok: Outcome) => {
    if (!token || programmeId === null) return
    setBusy(true)
    try {
      const row: AdminProgramme = await updateAdminProgramme(
        programmeId, { apply_copy: payload }, { token })
      // ⚠ RE-SEED FROM THE SERVER'S ROW, never from the draft — the server drops blank bullets and
      // trims, so a local echo would leave the screen disagreeing with what was stored.
      const asDraft = toDraft(row.apply_copy)
      setDraft(asDraft)
      setSaved(asDraft)
      setFlagged(row.apply_copy_sensitive ?? [])
      setOutcome(ok)
    } catch (e) {
      const code = (e as { code?: string })?.code || ''
      const field = (e as { field?: string })?.field || ''
      const known = ['too_long', 'too_many', 'markup', 'incomplete',
        'english_required', 'bad_shape'].includes(code)
      setOutcome({
        kind: 'error',
        message: known
          ? t(`admin.applyCopy.error.${code}`, { field: field || '—' })
          : t('admin.applyCopy.saveFailed'),
      })
    } finally {
      setBusy(false)
      setAsk(null)
    }
  }, [token, programmeId, t])

  /** ⚠ FILLS THE BOXES. IT NEVER SAVES — the server refuses to write, and so does this. The
   *  reader corrects the draft and presses Save, which is the same PATCH and the same
   *  validation any typed wording goes through. */
  const runDraft = useCallback(async (loc: Loc) => {
    // English is the SOURCE, so it can never be a target. The button renders only on the other
    // two tabs; this is the type-level statement of the same thing.
    if (!token || programmeId === null || loc === 'en') return
    setBusy(true)
    try {
      const block: AdminApplyCopyBlock = await draftApplyCopy(programmeId, loc, { token })
      setDraft(d => ({
        ...d,
        [loc]: {
          title: block.title || '',
          intro: block.intro || '',
          criteria: [...(block.criteria ?? [])],
        },
      }))
      setOutcome({ kind: 'drafted' })
    } catch (e) {
      const code = (e as { code?: string })?.code || ''
      const known = ['english_required', 'bad_locale', 'bullet_count', 'draft_too_long',
        'bad_reply', 'ai_unconfigured', 'ai_unavailable', 'ai_failed'].includes(code)
      setOutcome({
        kind: 'error',
        message: known ? t(`admin.applyCopy.error.${code}`) : t('admin.applyCopy.draftFailed'),
      })
    } finally {
      setBusy(false)
      setAsk(null)
    }
  }, [token, programmeId, t])

  if (loading) return <p className="text-ground-500">{t('common.loading')}</p>
  // `mustChoose` and "resolved to nothing" both mean the same thing to a reader: pick a gift.
  if (mustChoose || !programme) {
    return <ChooseProgramme programmes={programmes} onSelect={select} />
  }

  const block = draft[lang]
  const set = (patchBlock: Partial<Block>) =>
    setDraft({ ...draft, [lang]: { ...block, ...patchBlock } })

  // The draft is made from the SAVED English, so it is offered only when there IS saved English
  // and nothing unsaved is hiding it. Each refusal says which of the two it is.
  const staleEnglish = englishUnsaved(draft, saved)
  const draftBlocked = !configured
    ? t('admin.applyCopy.draftNeedsEnglish')
    : staleEnglish ? t('admin.applyCopy.draftEnglishUnsaved') : ''
  const targetHasText = Boolean(toPayload(draft)[lang])
  const clearList = writtenLocales(toPayload(saved))
    .map(l => t(`admin.applyCopy.lang.${l}`)).join(', ')

  return (
    <div data-testid="apply-copy-tab">
      <p className="text-sm text-ground-600 mb-4">{t('admin.applyCopy.hint')}</p>

      {/* ⚠ ADVISORY, NEVER A REFUSAL (owner ruling 2026-09-09, option A). MyNadi's s44(6) tax
          status requires its programme not to discriminate by race — but that constraint follows
          the funder, not the platform, and an ethnicity-scoped gift is lawful here. So this says
          so and gets out of the way. */}
      {flagged.length > 0 && (
        <div className="mb-4" data-testid="sensitive-warning">
          <InfoBox kind="warning">
            {t('admin.applyCopy.sensitiveWarning', { terms: flagged.join(', ') })}
          </InfoBox>
        </div>
      )}

      {!configured && (
        <div className="mb-4" data-testid="using-default">
          <InfoBox kind="info">{t('admin.applyCopy.usingDefault')}</InfoBox>
        </div>
      )}

      <LangTabs active={lang} onPick={setLang} t={t} />

      {lang !== 'en' && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-ground-500">{t('admin.applyCopy.fallbackNote')}</p>
          {/* ⚠ "DRAFT", NOT "TRANSLATE" — the word sets the expectation the feature depends on:
              a person reads every line before any of it can be saved. */}
          <div className="text-right">
            <button type="button" className={SAVE_BAR_SECONDARY}
              disabled={busy || Boolean(draftBlocked)}
              title={draftBlocked || undefined}
              data-testid="draft-from-english"
              onClick={() => (targetHasText ? setAsk('overwrite') : runDraft(lang))}>
              {busy ? t('admin.applyCopy.drafting') : t('admin.applyCopy.draft')}
            </button>
            <p className="mt-1 text-xs text-ground-500 max-w-xs" data-testid="draft-hint">
              {draftBlocked || t('admin.applyCopy.draftHint')}
            </p>
          </div>
        </div>
      )}

      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-ground-800 mb-1">
            {t('admin.applyCopy.field.title')}
          </label>
          <input className="input w-full" maxLength={MAX_TITLE} data-testid="copy-title"
            value={block.title} onChange={(e) => set({ title: e.target.value })} />
        </div>

        <div>
          <label className="block text-sm font-medium text-ground-800 mb-1">
            {t('admin.applyCopy.field.intro')}
          </label>
          <textarea className="input w-full" rows={3} maxLength={MAX_INTRO} data-testid="copy-intro"
            value={block.intro} onChange={(e) => set({ intro: e.target.value })} />
        </div>

        <div>
          <label className="block text-sm font-medium text-ground-800 mb-1">
            {t('admin.applyCopy.field.criteria')}
          </label>
          <Bullets value={block.criteria} onChange={(criteria) => set({ criteria })} t={t} />
          {/* ⚠ THE COST OF THE DIVERGENCE, SAID OUT LOUD. The owner accepted that the advertised
              bar may differ from the Rules tab; the tab has to name what that costs, or the next
              org_admin discovers it through a student who was turned down automatically. */}
          <p className="text-sm text-ground-600 mt-3">{t('admin.applyCopy.looserWarning')}</p>
        </div>
      </div>

      <SaveBar
        testId="apply-copy-outcome"
        status={
          outcome.kind === 'saved' ? t('admin.applyCopy.saved')
            : outcome.kind === 'cleared' ? t('admin.applyCopy.cleared')
              : outcome.kind === 'drafted' ? t('admin.applyCopy.drafted')
                : outcome.kind === 'error' ? outcome.message
                  : null
        }
      >
        {/* ⚠⚠ THIS DELETES EVERY LANGUAGE, AND IT USED TO DO SO ON ONE CLICK, FROM A TAB THAT
            SHOWS ONLY ONE. It was labelled by its OUTCOME ("Use the standard wording"), which
            reads as a peer of Save rather than as a delete, and it appears whenever ENGLISH is
            saved — so it sat, live and unlabelled, beside an empty Malay form whose Cancel-less
            press would take the English with it. Named for the ACTION now, and it asks first. */}
        {configured && (
          <button type="button" className={SAVE_BAR_SECONDARY} disabled={busy}
            data-testid="use-default"
            onClick={() => setAsk('clear')}>
            {t('admin.applyCopy.clearAll')}
          </button>
        )}
        <button type="button" className={SAVE_BAR_PRIMARY} disabled={busy || !dirty}
          title={dirty ? undefined : t('common.nothingToSave')}
          data-testid="copy-save"
          onClick={() => patch(toPayload(draft), { kind: 'saved' })}>
          {t('common.save')}
        </button>
      </SaveBar>

      {ask && (
        <ConfirmDialog
          ask={ask} languages={clearList} busy={busy} t={t}
          onCancel={() => setAsk(null)}
          onConfirm={() => (ask === 'clear'
            ? patch({}, { kind: 'cleared' })
            : runDraft(lang))} />
      )}
    </div>
  )
}
