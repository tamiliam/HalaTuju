'use client'

// "What we ask for" — Layer 0 Sprint 5 (2026-08-30), MOVED here unchanged by Layer 1 A2 when the
// page grew a second tab. Design of record: the Stitch screen approved 2026-07-29, CONTENT COLUMN
// ONLY — the shell (rail, breadcrumb, palette) comes from the app, never from the mock, and the
// mock's orange active row is not built (amber means caution).
//
// ⚠ THE CATALOGUE IS NOT A FENCE. This tab reads and writes CONFIGURATION through one endpoint that
// is itself org-fenced; nothing here decides who may see what. The endpoint is the authority.
//
// Every outcome of a Save has a line on screen (the #20 rule): saved, refused because a core item
// was switched off, or a generic failure. There is no silent branch.

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import InfoBox from '@/components/InfoBox'
import {
  getProgrammeConfiguration, saveProgrammeConfiguration,
  type ProgrammeConfigItem, type ProgrammeConfiguration, type ProgrammeItemState,
} from '@/lib/admin-api'
import {
  ITEM_STATES, allowedStates, changes, documents, draftFrom, isHeavy, itemKey, questions, tally,
  type Draft,
} from '@/lib/programmeConfig'

/** The three-state control. Rendered per row; a locked row offers `required` only. */
function StateControl({ item, value, onChange, t }: {
  item: ProgrammeConfigItem
  value: ProgrammeItemState
  onChange: (next: ProgrammeItemState) => void
  t: (k: string) => string
}) {
  const allowed = allowedStates(item)
  return (
    <div role="radiogroup" aria-label={t(item.label_key)}
      className="inline-flex rounded-lg bg-ground-100 p-0.5" data-item={itemKey(item)}>
      {ITEM_STATES.map((s) => {
        const selected = value === s
        const enabled = allowed.includes(s)
        return (
          <button key={s} type="button" role="radio" aria-checked={selected}
            data-state={s}
            disabled={!enabled}
            onClick={() => enabled && onChange(s)}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
              selected ? 'bg-ground-0 text-ground-900 shadow-sm ring-1 ring-ground-200'
                : enabled ? 'text-ground-500 hover:text-ground-800' : 'text-ground-300 cursor-not-allowed'}`}>
            {t(`admin.programme.config.state.${s}`)}
          </button>
        )
      })}
    </div>
  )
}

function ItemRow({ item, value, onChange, t }: {
  item: ProgrammeConfigItem
  value: ProgrammeItemState
  onChange: (next: ProgrammeItemState) => void
  t: (k: string) => string
}) {
  const heavy = isHeavy(item)
  return (
    <li className={`flex items-start justify-between gap-4 px-5 py-4 ${
      heavy ? 'bg-primary-50/60 border-l-4 border-brand-shape' : ''}`}
      data-testid={`row-${itemKey(item)}`}>
      <div className="min-w-0">
        <p className="font-medium text-ground-900">{t(item.label_key)}</p>
        <p className="mt-0.5 text-sm text-ground-500">
          {t(`admin.programme.config.desc.${item.kind}.${item.code}`)}
        </p>
        {heavy && (
          <p className="mt-1 text-xs text-ground-600">{t('admin.programme.config.heavyNote')}</p>
        )}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {/* Locked rows stay visible WITH the reason (owner decision 2). Muted grey, sentence
            case — the mock's caps-blue badge competed with the brand actions. Read from the
            item's own core flag, never a constant. */}
        {item.is_core && (
          <span className="text-xs text-ground-500" data-testid="always-required">
            {t('admin.programme.config.alwaysRequired')}
          </span>
        )}
        <StateControl item={item} value={value} onChange={onChange} t={t} />
      </div>
    </li>
  )
}

export default function ProgrammeConfigTab() {
  const { token } = useAdminAuth()
  const { t } = useT()

  const [config, setConfig] = useState<ProgrammeConfiguration | null>(null)
  const [draft, setDraft] = useState<Draft>({})
  const [loadError, setLoadError] = useState(false)
  const [programmeChoices, setProgrammeChoices] = useState<string[] | null>(null)
  const [programme, setProgramme] = useState<string | undefined>(undefined)
  const [saving, setSaving] = useState(false)
  // ONE closed set of outcomes; every value has a line below. Adding a value without a line is
  // the #20 bug returning.
  const [outcome, setOutcome] = useState<
    { kind: 'idle' } | { kind: 'saved' } | { kind: 'core'; item: string } | { kind: 'error' }
  >({ kind: 'idle' })

  // `load` depends on the token ONLY — never on `t`. A translator handle can be a fresh function
  // every render; depending on it here re-fires the fetch on each render, which silently re-reads
  // the server copy over an unsaved draft (found by the rendered test).
  const load = useCallback(async (code?: string) => {
    if (!token) return
    setLoadError(false)
    try {
      const c = await getProgrammeConfiguration(code, { token })
      setConfig(c)
      setDraft(draftFrom(c.items))
      setProgrammeChoices(null)
    } catch (e) {
      const err = e as Error & { body?: { code?: string; programmes?: string[] } }
      if (err.body?.code === 'programme_required' && Array.isArray(err.body.programmes)) {
        setProgrammeChoices(err.body.programmes)
      } else {
        setLoadError(true)
      }
    }
  }, [token])

  useEffect(() => { void load(programme) }, [load, programme])

  const pending = useMemo(() => (config ? changes(config.items, draft) : []), [config, draft])
  const docs = useMemo(() => (config ? documents(config.items) : []), [config])
  const qs = useMemo(() => (config ? questions(config.items) : []), [config])

  const setState = (item: ProgrammeConfigItem, next: ProgrammeItemState) => {
    setOutcome({ kind: 'idle' })
    setDraft((d) => ({ ...d, [itemKey(item)]: next }))
  }

  const discard = () => {
    if (config) setDraft(draftFrom(config.items))
    setOutcome({ kind: 'idle' })
  }

  const save = async () => {
    if (!token || !config || pending.length === 0) return
    setSaving(true)
    // Do NOT clear the outcome here on the way in — a refusal must never be wiped by a loader
    // (the sponsor-terms lesson). It is replaced only by this save's own result.
    try {
      const c = await saveProgrammeConfiguration(pending, programme, { token })
      setConfig(c)
      setDraft(draftFrom(c.items))
      setOutcome({ kind: 'saved' })
    } catch (e) {
      const err = e as Error & { body?: { code?: string; item?: string } }
      if (err.body?.code === 'core_item') {
        const [kind, code] = (err.body.item || ':').split(':')
        const row = config.items.find((i) => i.kind === kind && i.code === code)
        setOutcome({ kind: 'core', item: row ? t(row.label_key) : err.body.item || '' })
      } else {
        setOutcome({ kind: 'error' })
      }
    } finally {
      setSaving(false)
    }
  }

  const all = docs.length + qs.length
  const tDocs = tally(docs, draft)
  const tQs = tally(qs, draft)
  const nothingToSave = pending.length === 0

  return (
    <>
      <h2 className="mt-6 text-lg font-semibold text-ground-900">{t('admin.programme.config.title')}</h2>
      <p className="mt-1 text-sm text-ground-600">{t('admin.programme.config.subtitle')}</p>

      {loadError && (
        <div className="mt-4"><InfoBox kind="block">{t('admin.programme.config.loadError')}</InfoBox></div>
      )}

      {programmeChoices && (
        <div className="mt-4 rounded-xl border border-ground-200 bg-ground-0 p-4">
          <p className="text-sm font-medium text-ground-800">{t('admin.programme.config.programmeRequired')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {programmeChoices.map((code) => (
              <button key={code} type="button" onClick={() => setProgramme(code)}
                className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">
                {code}
              </button>
            ))}
          </div>
        </div>
      )}

      {config && (
        <>
          {/* The live-applicant warning names a REAL, counted number and sits ABOVE the controls
              (owner decision 4) — never in a confirmation dialog after the decision. */}
          <div className="mt-4" data-testid="live-warning">
            <InfoBox kind="warning">
              {config.live_applicants > 0
                ? t('admin.programme.config.liveWarning', { n: String(config.live_applicants) })
                : t('admin.programme.config.liveWarningNone')}
            </InfoBox>
          </div>

          {[
            { key: 'documents', rows: docs, title: 'sectionDocuments', hint: 'documentsHint' },
            { key: 'questions', rows: qs, title: 'sectionQuestions', hint: 'questionsHint' },
          ].map(({ key, rows, title, hint }) => (
            <section key={key} className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 shadow-sm"
              aria-labelledby={`section-${key}`}>
              <div className="border-b border-ground-100 px-5 py-4">
                <h2 id={`section-${key}`} className="text-lg font-semibold text-ground-900">
                  {t(`admin.programme.config.${title}`)}
                </h2>
                <p className="text-sm text-ground-500">{t(`admin.programme.config.${hint}`)}</p>
              </div>
              <ul className="divide-y divide-ground-100">
                {rows.map((item) => (
                  <ItemRow key={itemKey(item)} item={item}
                    value={draft[itemKey(item)] ?? item.state}
                    onChange={(next) => setState(item, next)} t={t} />
                ))}
              </ul>
            </section>
          ))}

          <p className="mt-4 text-xs text-ground-500">
            <Link href="/admin/requests" className="underline hover:no-underline">
              {t('admin.programme.config.requestLink')}
            </Link>
          </p>

          {/* Footer toolbar — a neutral tint (the mock's pale blue read as an info panel). */}
          <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-50 px-5 py-3">
            <div className="text-sm text-ground-700">
              <p>
                {t('admin.programme.config.summary', {
                  required: String(tDocs.required + tQs.required),
                  optional: String(tDocs.optional + tQs.optional),
                  total: String(all),
                })}
              </p>
              <p className="text-xs text-ground-500" data-testid="save-outcome">
                {outcome.kind === 'saved' ? t('admin.programme.config.saved')
                  : outcome.kind === 'core' ? t('admin.programme.config.errorCore', { item: outcome.item })
                    : outcome.kind === 'error' ? t('admin.programme.config.errorGeneric')
                      : nothingToSave ? t('admin.programme.config.unchanged')
                        : t('admin.programme.config.changed', { n: String(pending.length) })}
              </p>
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={discard} disabled={nothingToSave || saving}
                className="rounded-lg border border-ground-300 bg-ground-0 px-4 py-2 text-sm font-medium text-ground-700 disabled:opacity-50">
                {t('admin.programme.config.discard')}
              </button>
              <button type="button" onClick={save} disabled={nothingToSave || saving}
                title={nothingToSave ? t('common.nothingToSave') : undefined}
                className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {saving ? t('admin.programme.config.saving') : t('admin.programme.config.save')}
              </button>
            </div>
          </div>
        </>
      )}
    </>
  )
}
