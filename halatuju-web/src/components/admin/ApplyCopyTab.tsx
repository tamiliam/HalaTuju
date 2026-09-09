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
  updateAdminProgramme, type AdminApplyCopy, type AdminProgramme,
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
  | { kind: 'error'; message: string }

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

// ── Module-scope pieces (see the remount warning above) ──────────────────────────────────────

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
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  const programmeId = programme?.id ?? null

  // Seed from the gift the scope hook already fetched — `getAdminProgrammes` carries `apply_copy`,
  // so there is no second request to make.
  useEffect(() => {
    const asDraft = toDraft(programme?.apply_copy)
    setDraft(asDraft)
    setSaved(asDraft)
    setFlagged(programme?.apply_copy_sensitive ?? [])
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
        <p className="text-sm text-ground-500 mb-4">{t('admin.applyCopy.fallbackNote')}</p>
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
              : outcome.kind === 'error' ? outcome.message
                : null
        }
      >
        {configured && (
          <button type="button" className={SAVE_BAR_SECONDARY} disabled={busy}
            data-testid="use-default"
            onClick={() => patch({}, { kind: 'cleared' })}>
            {t('admin.applyCopy.useDefault')}
          </button>
        )}
        <button type="button" className={SAVE_BAR_PRIMARY} disabled={busy || !dirty}
          title={dirty ? undefined : t('common.nothingToSave')}
          data-testid="copy-save"
          onClick={() => patch(toPayload(draft), { kind: 'saved' })}>
          {t('common.save')}
        </button>
      </SaveBar>
    </div>
  )
}
