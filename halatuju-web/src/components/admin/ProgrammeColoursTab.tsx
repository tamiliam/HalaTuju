'use client'

/**
 * "Colours" — Layer 1 A2. The second tab of the Programme screen.
 *
 * Design of record: the working mock approved 2026-09-01
 * (https://claude.ai/code/artifact/97405467-1fd5-45e3-97be-d83c5fb8739e). Stitch failed twice on
 * this project that day and never produced a screen; the mock is the same fallback used for the
 * sponsored-student page in July.
 *
 * ⚠ THE BROWSER IS NOT THE GATE. `apps/courses/contrast.py` refuses the save, and it re-runs
 * everything this file computes. The live check here exists so the person choosing sees the answer
 * as they type — and the Save button is disabled with the reason beside it, so they are never
 * invited to press something that will be refused. Both, not either: a disabled button is a
 * courtesy, a 400 is the rule.
 *
 * ⚠ THE PREVIEW IS SCOPED TO ITS OWN CARD, deliberately. Painting the draft colour onto the whole
 * console while somebody types would fight `branding-context` (which owns the real tokens) and
 * would repaint the very controls they are using to decide. The samples show real components; the
 * page around them stays the product they know.
 *
 * Every outcome of a Save has a line on screen (the #20 rule): saved, reset, refused as unreadable,
 * or a generic failure. There is no silent branch.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import InfoBox from '@/components/InfoBox'
import { PLATFORM, brandRamp } from '@/lib/branding'
import { PAIRS, checkColour, isHexColour } from '@/lib/contrast'
import {
  getOrganisationTheme, resetOrganisationTheme, saveOrganisationTheme,
  type OrganisationTheme,
} from '@/lib/admin-api'

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

/** The platform's own colour — what "Reset to default" goes back to, and what an organisation that
 *  has never chosen is already showing.
 *
 *  ⚠ READ FROM THE BRANDING SEAM, NEVER RE-TYPED. `lib/branding.ts` is the one sanctioned home for
 *  a brand literal and `theme.test.ts` fails the build on a copy anywhere else — which it did, on
 *  the first draft of this very file, three lines under a comment saying not to. */
const PLATFORM_COLOUR = PLATFORM.brandColour

type Outcome =
  | { kind: 'idle' }
  | { kind: 'saved' }
  | { kind: 'reset' }
  | { kind: 'unreadable'; failing: string[] }
  | { kind: 'error' }

/** Inline `--brand-N` for the preview card ONLY. Same shape `branding-context` writes globally. */
function previewVars(hex: string): Record<string, string> {
  const ramp = brandRamp(hex, 'light')
  const out: Record<string, string> = {}
  for (const step of STEPS) out[`--brand-${step}`] = ramp[step]
  return out
}

export default function ProgrammeColoursTab() {
  const { token } = useAdminAuth()
  const { t } = useT()

  const [theme, setTheme] = useState<OrganisationTheme | null>(null)
  const [draft, setDraft] = useState(PLATFORM_COLOUR)
  const [loadError, setLoadError] = useState(false)
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  const [org, setOrg] = useState<string | undefined>(undefined)
  const [saving, setSaving] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  // Depends on the token and the chosen organisation ONLY — never on `t`. A translator handle can
  // be a fresh function every render, and depending on it re-fires the fetch over an unsaved draft.
  const load = useCallback(async (code?: string) => {
    if (!token) return
    setLoadError(false)
    try {
      const th = await getOrganisationTheme(code, { token })
      setTheme(th)
      setDraft(th.colour || PLATFORM_COLOUR)
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

  const valid = isHexColour(draft)
  const checks = useMemo(() => (valid ? checkColour(draft) : []), [draft, valid])
  const failing = checks.filter((c) => !c.passes)
  const saved = theme?.colour || ''
  // ⚠ COMPARE AGAINST THE EFFECTIVE COLOUR, NOT THE STORED ONE. An organisation with no row is
  // ALREADY showing the platform colour, so comparing the draft against '' woke Save the moment
  // the tab loaded — offering to "save" a change nobody made, which would create a row that
  // changes nothing and quietly take the organisation off the stylesheet. Found by the rendered
  // test; a pure test of the maths could never have seen it.
  const current = saved || PLATFORM_COLOUR
  const changed = valid && draft.toLowerCase() !== current.toLowerCase()
  const canSave = changed && valid && failing.length === 0 && !saving

  const onColour = (value: string) => {
    setOutcome({ kind: 'idle' })
    setDraft(value)
  }

  const save = async () => {
    if (!token || !canSave) return
    setSaving(true)
    // Do NOT clear the outcome on the way in — a refusal must never be wiped by a loader.
    try {
      setTheme(await saveOrganisationTheme(draft, org, { token }))
      setOutcome({ kind: 'saved' })
    } catch (e) {
      const err = e as Error & { body?: { code?: string; failing?: string[] } }
      if (err.body?.code === 'unreadable') {
        // The server refused something the browser thought was fine — the two disagreeing is a
        // real bug, so show ITS answer rather than ours.
        setOutcome({ kind: 'unreadable', failing: err.body.failing || [] })
      } else {
        setOutcome({ kind: 'error' })
      }
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    if (!token || saving) return
    setSaving(true)
    try {
      const th = await resetOrganisationTheme(org, { token })
      setTheme(th)
      setDraft(PLATFORM_COLOUR)
      setOutcome({ kind: 'reset' })
    } catch {
      setOutcome({ kind: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const ramp = valid ? brandRamp(draft, 'light') : brandRamp(PLATFORM_COLOUR, 'light')

  return (
    <>
      <h2 className="mt-6 text-lg font-semibold text-ground-900">{t('admin.programme.colours.title')}</h2>
      <p className="mt-1 text-sm text-ground-600">{t('admin.programme.colours.subtitle')}</p>

      {loadError && (
        <div className="mt-4"><InfoBox kind="block">{t('admin.programme.colours.loadError')}</InfoBox></div>
      )}

      {orgChoices && (
        <div className="mt-4 rounded-xl border border-ground-200 bg-ground-0 p-4">
          <p className="text-sm font-medium text-ground-800">{t('admin.programme.colours.organisationRequired')}</p>
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

      {theme && (
        <>
          {/* ── 1. the colour ─────────────────────────────────────────────────────────── */}
          <section className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programme.colours.pickTitle')}</h2>
            <p className="text-sm text-ground-500">{t('admin.programme.colours.pickHint')}</p>
            <div className="mt-4 flex flex-wrap items-end gap-4">
              <input type="color" value={valid ? draft : PLATFORM_COLOUR}
                onChange={(e) => onColour(e.target.value)}
                aria-label={t('admin.programme.colours.swatchLabel')}
                data-testid="colour-swatch"
                className="h-14 w-14 shrink-0 cursor-pointer rounded-xl border border-ground-200 p-0" />
              <div>
                <label htmlFor="brand-hex" className="block text-xs font-semibold uppercase tracking-wide text-ground-500">
                  {t('admin.programme.colours.hexLabel')}
                </label>
                <input id="brand-hex" type="text" value={draft} spellCheck={false} autoComplete="off"
                  onChange={(e) => onColour(e.target.value)}
                  className="mt-1 w-36 rounded-lg border border-ground-200 bg-ground-0 px-3 py-2 font-mono text-sm text-ground-900" />
              </div>
              <button type="button" onClick={reset} disabled={theme.is_default || saving}
                data-testid="reset-colour"
                className="ml-auto pb-2 text-sm text-ground-500 underline hover:no-underline disabled:opacity-50">
                {t('admin.programme.colours.reset')}
              </button>
            </div>
            {!valid && (
              <p className="mt-3 text-sm text-critical-700" data-testid="bad-hex">
                {t('admin.programme.colours.badHex')}
              </p>
            )}
          </section>

          {/* ── 2. the palette ────────────────────────────────────────────────────────── */}
          <section className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programme.colours.paletteTitle')}</h2>
            <p className="text-sm text-ground-500">{t('admin.programme.colours.paletteHint')}</p>
            <div className="mt-4 grid grid-cols-10" data-testid="palette">
              {STEPS.map((step) => (
                <div key={step} className="text-center">
                  <span className="block h-10 rounded-none first:rounded-l-md"
                    style={{ background: `rgb(${ramp[step]})` }} aria-hidden />
                  <span className="mt-1.5 block font-mono text-[10px] text-ground-500">{step}</span>
                </div>
              ))}
            </div>
          </section>

          {/* ── 3. the preview, scoped to this card ───────────────────────────────────── */}
          <section className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm"
            style={previewVars(valid ? draft : PLATFORM_COLOUR) as React.CSSProperties}>
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programme.colours.previewTitle')}</h2>
            <p className="text-sm text-ground-500">{t('admin.programme.colours.previewHint')}</p>
            <div className="mt-4 flex flex-wrap items-center gap-4">
              <span className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white">
                {t('admin.programme.colours.sampleButton')}
              </span>
              <span className="rounded-r-lg border-l-4 border-primary-500 bg-primary-50 px-4 py-2 text-sm text-primary-700">
                {t('admin.programme.colours.samplePanel')}
              </span>
              <span className="text-sm text-primary-600 underline">
                {t('admin.programme.colours.sampleLink')}
              </span>
            </div>
          </section>

          {/* ── 4. the check ──────────────────────────────────────────────────────────── */}
          <section className="mt-6 rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-ground-900">{t('admin.programme.colours.checkTitle')}</h2>
            <p className="text-sm text-ground-500">{t('admin.programme.colours.checkHint')}</p>
            <ul className="mt-3 divide-y divide-ground-100 border-t border-ground-100" data-testid="checks">
              {checks.map((c) => (
                <li key={c.key} className="flex items-center gap-3 py-2.5 text-sm"
                  data-testid={`check-${c.key}`} data-passes={c.passes ? 'yes' : 'no'}>
                  <span aria-hidden className={`grid h-4.5 w-4.5 shrink-0 place-items-center rounded-full text-[11px] font-bold text-white ${
                    c.passes ? 'bg-positive-600' : 'bg-critical-600'}`}
                    style={{ height: '18px', width: '18px' }}>
                    {c.passes ? '✓' : '✗'}
                  </span>
                  <span className="min-w-0 flex-1 text-ground-800">
                    {t(`admin.programme.colours.pair.${c.key}`)}
                  </span>
                  <span className="font-mono text-sm tabular-nums text-ground-600">{c.ratio.toFixed(1)}</span>
                  <span className="text-xs text-ground-400">
                    {t('admin.programme.colours.needs', { n: c.min.toFixed(1) })}
                  </span>
                </li>
              ))}
            </ul>
            {valid && failing.length > 0 && (
              <div className="mt-4" data-testid="unreadable-note">
                <InfoBox kind="block">
                  {t('admin.programme.colours.unreadable', {
                    pairs: failing.map((c) => t(`admin.programme.colours.pairShort.${c.key}`)).join(', '),
                  })}
                </InfoBox>
              </div>
            )}
          </section>

          {/* ── the toolbar ───────────────────────────────────────────────────────────── */}
          <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-50 px-5 py-3">
            <p className="text-sm text-ground-700" data-testid="colours-outcome">
              {outcome.kind === 'saved' ? t('admin.programme.colours.saved')
                : outcome.kind === 'reset' ? t('admin.programme.colours.wasReset')
                  : outcome.kind === 'unreadable'
                    ? t('admin.programme.colours.refused', {
                      pairs: outcome.failing
                        .map((k) => t(`admin.programme.colours.pairShort.${k}`)).join(', '),
                    })
                    : outcome.kind === 'error' ? t('admin.programme.colours.errorGeneric')
                      : !valid ? t('admin.programme.colours.badHex')
                        : failing.length > 0 ? t('admin.programme.colours.cannotSave')
                          : changed ? t('admin.programme.colours.changed')
                            : theme.is_default ? t('admin.programme.colours.usingDefault')
                              : t('admin.programme.colours.unchanged')}
            </p>
            <div className="flex gap-2">
              <button type="button" onClick={() => { setDraft(current); setOutcome({ kind: 'idle' }) }}
                disabled={!changed || saving}
                className="rounded-lg border border-ground-300 bg-ground-0 px-4 py-2 text-sm font-medium text-ground-700 disabled:opacity-50">
                {t('admin.programme.colours.discard')}
              </button>
              <button type="button" onClick={save} disabled={!canSave}
                data-testid="save-colours"
                title={!changed ? t('common.nothingToSave') : undefined}
                className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50">
                {saving ? t('admin.programme.colours.saving') : t('admin.programme.colours.save')}
              </button>
            </div>
          </div>
        </>
      )}
    </>
  )
}

/** Exported for the guard test: the screen must carry a label for EVERY pair the check can report,
 *  or a refusal renders a raw dotted key at the moment somebody is being told no. */
export const PAIR_KEYS = PAIRS.map((p) => p.key)
