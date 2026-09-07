'use client'

/**
 * "Configuration" — Org Config Sprint A. The second tab of ORGANISATION → Settings, beside
 * Colours (whose shell comment promised it would arrive).
 *
 * The tab renders the server's REGISTRY of organisation-wide values — it invents nothing. Each row
 * is one setting: a number box, its unit, and the platform default beside it. ⚠ A BLANK BOX MEANS
 * "FOLLOW THE PLATFORM DEFAULT", and that is an answer, not an omission — the box's placeholder
 * shows the default, the note underneath names it, and clearing the box sends `null` so the stored
 * row never carries a copied default (a copied default rots the day the platform value moves).
 *
 * ⚠ THE BROWSER IS NOT THE GATE. The server validates every value against the registry's bounds
 * and refuses all-or-nothing; the inline range check here exists so the person typing sees the
 * answer immediately, and Save is disabled with the reason beside it (the Colours rule).
 *
 * Save follows the platform's nothing-to-save standard: asleep until a value actually differs
 * from what is stored. Every outcome has a line on screen (the #20 rule): saved, refused with the
 * offending row named, or a generic failure. There is no silent branch.
 *
 * First setting: `pool_funded_grace_days` (owner 2026-09-06 — the funded student card stays on
 * the sponsor browse page for 30 days instead of 2). The read site is `pool.display_pool_queryset`.
 */
import { useCallback, useEffect, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import InfoBox from '@/components/InfoBox'
import {
  getOrganisationConfiguration, saveOrganisationConfiguration,
  type OrganisationConfigSetting, type OrganisationConfiguration,
} from '@/lib/admin-api'

/** Groups render in this order; a group appears only when the registry has a row in it. */
const GROUP_ORDER = ['sponsor_page', 'student_comms']

type Outcome =
  | { kind: 'idle' }
  | { kind: 'saved' }
  | { kind: 'refused'; key: string }
  | { kind: 'error' }

/** The text-box state the payload implies: '' for "following the default", else the number. */
function draftFrom(cfg: OrganisationConfiguration | null): Record<string, string> {
  const out: Record<string, string> = {}
  for (const s of cfg?.settings ?? []) out[s.key] = s.value === null ? '' : String(s.value)
  return out
}

/** Parse one box. '' is valid and means null (follow the default). */
function parseBox(raw: string, s: OrganisationConfigSetting):
    { ok: true; value: number | null } | { ok: false } {
  const text = (raw ?? '').trim()
  if (text === '') return { ok: true, value: null }
  if (!/^\d+$/.test(text)) return { ok: false }
  const n = parseInt(text, 10)
  if (n < s.min || n > s.max) return { ok: false }
  return { ok: true, value: n }
}

export default function OrganisationConfigurationTab() {
  const { token } = useAdminAuth()
  const { t } = useT()

  const [config, setConfig] = useState<OrganisationConfiguration | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [loadError, setLoadError] = useState(false)
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  const [org, setOrg] = useState<string | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  // Depends on the token and the chosen organisation ONLY — never on `t` (the re-fired-fetch
  // trap: a translator handle can be a fresh function every render and would wipe unsaved edits).
  const load = useCallback(async (code?: string) => {
    if (!token) return
    setLoadError(false)
    try {
      const cfg = await getOrganisationConfiguration(code, { token })
      setConfig(cfg)
      setDraft(draftFrom(cfg))
      setOrgChoices(null)
    } catch (e) {
      const err = e as Error & { body?: { code?: string; organisations?: string[] } }
      if (err.body?.code === 'organisation_required' && Array.isArray(err.body.organisations)) {
        setOrgChoices(err.body.organisations)
      } else {
        setLoadError(true)
      }
    }
  }, [token])

  useEffect(() => { void load(org) }, [load, org])

  const settings = config?.settings ?? []
  const rows = settings.map((s) => {
    const parsed = parseBox(draft[s.key] ?? '', s)
    const edited = parsed.ok && parsed.value !== s.value
    return { s, parsed, edited }
  })
  const invalid = rows.some((r) => !r.parsed.ok)
  const edited = rows.some((r) => r.edited)
  const canSave = edited && !invalid && !busy

  const onSave = async () => {
    if (!token || !canSave) return
    // Send ONLY what changed — the payload is the diff, so the audit trail names real changes.
    const values: Record<string, number | null> = {}
    for (const r of rows) if (r.edited && r.parsed.ok) values[r.s.key] = r.parsed.value
    setBusy(true)
    try {
      const cfg = await saveOrganisationConfiguration(values, org, { token })
      setConfig(cfg)
      setDraft(draftFrom(cfg))
      setOutcome({ kind: 'saved' })
    } catch (e) {
      const err = e as Error & { body?: { code?: string; key?: string } }
      if (err.body?.code && err.body.key) {
        setOutcome({ kind: 'refused', key: err.body.key })
      } else {
        setOutcome({ kind: 'error' })
      }
    } finally {
      setBusy(false)
    }
  }

  const label = (key: string) => t(`admin.orgSettings.config.setting.${key}.label`)

  const statusLine = () => {
    switch (outcome.kind) {
      case 'saved': return t('admin.orgSettings.config.saved')
      case 'refused': return t('admin.orgSettings.config.refused', { label: label(outcome.key) })
      case 'error': return t('admin.orgSettings.config.errorGeneric')
      default:
        if (invalid) return t('admin.orgSettings.config.invalid')
        if (edited) return t('admin.orgSettings.config.unsaved')
        return t('admin.orgSettings.config.nothingToDo')
    }
  }

  return (
    <>
      <p className="mt-6 text-sm text-ground-600">{t('admin.orgSettings.config.subtitle')}</p>

      {loadError && (
        <div className="mt-4"><InfoBox kind="block">{t('admin.orgSettings.config.loadError')}</InfoBox></div>
      )}

      {orgChoices && (
        <div className="mt-4 rounded-xl border border-ground-200 bg-ground-0 p-4">
          <p className="text-sm font-medium text-ground-800">{t('admin.orgSettings.config.organisationRequired')}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {orgChoices.map((code) => (
              <button key={code} type="button" onClick={() => setOrg(code)}
                className="rounded-lg border border-ground-300 px-3 py-1.5 text-sm hover:bg-ground-50">
                {code}
              </button>
            ))}
          </div>
        </div>
      )}

      {config && (
        <>
          {GROUP_ORDER.filter((g) => settings.some((s) => s.group === g)).map((group) => (
            <section key={group}
              className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
              <h2 className="text-lg font-semibold text-ground-900">
                {t(`admin.orgSettings.config.group.${group}`)}
              </h2>
              <ul className="mt-2 divide-y divide-ground-100" data-testid="config-rows">
                {rows.filter((r) => r.s.group === group).map(({ s, parsed }) => (
                  <li key={s.key} className="flex flex-wrap items-start justify-between gap-4 py-4">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ground-900">{label(s.key)}</p>
                      <p className="mt-0.5 text-sm text-ground-500">
                        {t(`admin.orgSettings.config.setting.${s.key}.desc`)}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center justify-end gap-2">
                        <input type="text" inputMode="numeric" spellCheck={false} autoComplete="off"
                          value={draft[s.key] ?? ''}
                          onChange={(e) => {
                            setOutcome({ kind: 'idle' })
                            setDraft((d) => ({ ...d, [s.key]: e.target.value }))
                          }}
                          placeholder={String(s.default)}
                          aria-label={label(s.key)}
                          data-testid={`config-${s.key}`}
                          className="w-24 rounded-lg border border-ground-200 bg-ground-0 px-3 py-2 text-right text-sm tabular-nums text-ground-900" />
                        {/* Fixed-width unit column: with a natural-width label the right-aligned
                            pair shifts the BOX by the unit's length ("days" vs "questions"), so
                            the boxes never line up down the page (owner, 2026-09-07). w-24 also
                            fits the longest ta unit. */}
                        <span className="w-24 shrink-0 text-left text-sm text-ground-500"
                          data-testid={`config-${s.key}-unit`}>
                          {t(`admin.orgSettings.config.unit.${s.unit}`)}
                        </span>
                      </div>
                      {parsed.ok ? (
                        <p className="mt-1 text-xs text-ground-400">
                          {t('admin.orgSettings.config.defaultNote', {
                            n: String(s.default),
                            unit: t(`admin.orgSettings.config.unit.${s.unit}`),
                          })}
                        </p>
                      ) : (
                        <p className="mt-1 text-xs text-critical-700" data-testid={`config-${s.key}-invalid`}>
                          {t('admin.orgSettings.config.rowInvalid', {
                            min: String(s.min), max: String(s.max),
                          })}
                        </p>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ))}

          <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-50 px-5 py-3">
            <p className="text-sm text-ground-700" data-testid="config-outcome">{statusLine()}</p>
            <button type="button" data-testid="save-config" disabled={!canSave}
              onClick={() => void onSave()}
              title={!edited ? t('common.nothingToSave') : undefined}
              className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
              {t('admin.orgSettings.config.save')}
            </button>
          </div>
        </>
      )}
    </>
  )
}
