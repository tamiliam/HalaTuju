'use client'

/**
 * "Colours" — Layer 1 A2, given a lifecycle by A3. The second tab of the Programme screen.
 *
 * Design of record: the working mock approved 2026-09-01
 * (https://claude.ai/code/artifact/97405467-1fd5-45e3-97be-d83c5fb8739e). Stitch failed twice on
 * this project that day and never produced a screen; the mock is the same fallback used for the
 * sponsored-student page in July. A3 adds a status banner and two verbs to it.
 *
 * ⚠ THE SCREEN'S ONE JOB IS THAT NOBODY CONFUSES "LIVE" WITH "DRAFT" (Layer 1 A3). Saving no longer
 * changes what applicants see; publishing does. So the two are kept apart everywhere — separate
 * payload keys, separate buttons — and a banner at the top always says which colour an applicant is
 * actually looking at, rather than leaving it to be inferred from the box.
 *
 * ⚠ THE BROWSER IS NOT THE GATE. `apps/courses/contrast.py` refuses the save, and it re-runs
 * everything this file computes. The live check here exists so the person choosing sees the answer
 * as they type — and Save is disabled with the reason beside it, so they are never invited to press
 * something that will be refused. A disabled button is a courtesy; the 400 is the rule.
 *
 * ⚠ THE PREVIEW IS SCOPED TO ITS OWN CARD, deliberately. Painting the draft colour onto the whole
 * console while somebody types would fight `branding-context` (which owns the real tokens) and
 * would repaint the very controls they are using to decide.
 *
 * Every outcome has a line on screen (the #20 rule): saved, discarded, published, reverted, refused
 * as unreadable, or a generic failure. There is no silent branch.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import InfoBox from '@/components/InfoBox'
import { PLATFORM, brandRamp } from '@/lib/branding'
import { PAIRS, checkColourBothModes, isHexColour } from '@/lib/contrast'
import {
  discardOrganisationThemeDraft, getOrganisationTheme, publishOrganisationTheme,
  revertOrganisationTheme, saveOrganisationThemeDraft,
  type OrganisationTheme,
} from '@/lib/admin-api'

const STEPS = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

/** The platform's own colour — what an organisation that has never chosen is already showing.
 *
 *  ⚠ READ FROM THE BRANDING SEAM, NEVER RE-TYPED. `lib/branding.ts` is the one sanctioned home for
 *  a brand literal and `theme.test.ts` fails the build on a copy anywhere else — which it did, on
 *  the first draft of this file, three lines under a comment saying not to. */
const PLATFORM_COLOUR = PLATFORM.brandColour

type Outcome =
  | { kind: 'idle' }
  | { kind: 'draftSaved' }
  | { kind: 'draftDiscarded' }
  | { kind: 'published' }
  | { kind: 'reverted' }
  | { kind: 'unreadable'; failing: string[] }
  | { kind: 'error' }

/** Inline `--brand-N` for the preview card ONLY. Same shape `branding-context` writes globally. */
function previewVars(hex: string): Record<string, string> {
  const ramp = brandRamp(hex, 'light')
  const out: Record<string, string> = {}
  for (const step of STEPS) out[`--brand-${step}`] = ramp[step]
  return out
}

/** What the colour box should hold: the unpublished work if any, else what is live, else ours. */
function boxColour(th: OrganisationTheme | null): string {
  return th?.draft?.colour || th?.live?.colour || PLATFORM_COLOUR
}

export default function ProgrammeColoursTab() {
  const { token } = useAdminAuth()
  const { t } = useT()

  const [theme, setTheme] = useState<OrganisationTheme | null>(null)
  const [draft, setDraft] = useState(PLATFORM_COLOUR)
  const [loadError, setLoadError] = useState(false)
  const [orgChoices, setOrgChoices] = useState<string[] | null>(null)
  const [org, setOrg] = useState<string | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })

  // Depends on the token and the chosen organisation ONLY — never on `t`. A translator handle can
  // be a fresh function every render, and depending on it re-fires the fetch over an unsaved draft.
  const load = useCallback(async (code?: string) => {
    if (!token) return
    setLoadError(false)
    try {
      const th = await getOrganisationTheme(code, { token })
      setTheme(th)
      setDraft(boxColour(th))
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
  // ⚠ BOTH MODES since F7a. A colour is stored once and rendered in light AND dark, so a screen
  // reporting only the light numbers would tell somebody their colour is fine while the save path
  // — which checks both — refuses it. The list is longer; that is the point.
  const checks = useMemo(() => (valid ? checkColourBothModes(draft) : []), [draft, valid])
  const failing = checks.filter((c) => !c.passes)

  // Compare the box against the EFFECTIVE colour, never against '' — the A2 lesson. An
  // organisation with no row is already showing the platform colour, so comparing against nothing
  // woke Save the moment the tab loaded.
  const saved = boxColour(theme)
  const edited = valid && draft.toLowerCase() !== saved.toLowerCase()
  const canSaveDraft = edited && failing.length === 0 && !busy
  // ⚠ PUBLISH IS ASLEEP WHILE THERE ARE UNSAVED EDITS. Publishing would ship the SAVED draft, not
  // what is in the box — so offering it mid-edit would publish something other than what the
  // person is looking at. The tooltip says to save first.
  const canPublish = !!theme?.draft && !edited && !busy
  const canDiscard = (!!theme?.draft || edited) && !busy
  const canRevert = !!theme?.can_revert && !busy

  const onColour = (value: string) => {
    setOutcome({ kind: 'idle' })
    setDraft(value)
  }

  /** One shape for all four writes: never clear the outcome on the way IN (a refusal must not be
   *  wiped by a loader), always re-read the whole record, always leave a line on screen. */
  const run = async (action: () => Promise<OrganisationTheme>, ok: Outcome) => {
    if (!token || busy) return
    setBusy(true)
    try {
      const th = await action()
      setTheme(th)
      setDraft(boxColour(th))
      setOutcome(ok)
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
      setBusy(false)
    }
  }

  const ramp = valid ? brandRamp(draft, 'light') : brandRamp(PLATFORM_COLOUR, 'light')

  const statusLine = () => {
    switch (outcome.kind) {
      case 'draftSaved': return t('admin.programme.colours.draftSaved')
      case 'draftDiscarded': return t('admin.programme.colours.draftDiscarded')
      case 'published': return t('admin.programme.colours.published')
      case 'reverted': return t('admin.programme.colours.reverted')
      case 'unreadable': return t('admin.programme.colours.refused', {
        pairs: outcome.failing.map((k) => t(`admin.programme.colours.pairShort.${k}`)).join(', '),
      })
      case 'error': return t('admin.programme.colours.errorGeneric')
      default:
        if (!valid) return t('admin.programme.colours.badHex')
        if (failing.length > 0) return t('admin.programme.colours.cannotSave')
        if (edited) return t('admin.programme.colours.unsaved')
        if (theme?.draft) return t('admin.programme.colours.draftWaiting')
        return t('admin.programme.colours.nothingToDo')
    }
  }

  return (
    <>
      {/* No heading — the "Colours" tab above is it. Same change as the config tab (2026-09-02);
          this one read "Your colours" directly under a tab labelled "Colours". */}
      <p className="mt-6 text-sm text-ground-600">{t('admin.programme.colours.subtitle')}</p>

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
          {/* ── 0. WHAT APPLICANTS SEE RIGHT NOW. First, because it is the fact everything below is
                 relative to, and the one thing a person must never have to infer. ──────────── */}
          <div className="mt-4" data-testid="live-state">
            <InfoBox kind={theme.draft ? 'warning' : 'info'}>
              {theme.live
                ? t('admin.programme.colours.liveIs', { colour: theme.live.colour })
                : t('admin.programme.colours.liveIsDefault')}
              {theme.draft ? ` ${t('admin.programme.colours.draftPending')}` : ''}
            </InfoBox>
          </div>

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
            {/* ⚠ EACH BLOCK GETS ITS OWN FIXED-HEIGHT ROW, bottom-aligned. `items-end` on the GRID
                aligns the CELLS, and the 500 cell carries an extra child (its dot) — so its whole
                column was pushed up and the raised block floated off the strip's baseline. And the
                ends are rounded BY INDEX: each block is the only child of its cell, so a `first:`
                variant matched all ten. Both found on the live screen, not by a test. */}
            <div className="mt-4 grid grid-cols-10" data-testid="palette">
              {STEPS.map((step, i) => (
                <div key={step} className="text-center">
                  <span className="flex h-14 items-end">
                    <span
                      className={`w-full ${step === 500 ? 'h-14' : 'h-10'} ${
                        i === 0 ? 'rounded-l-md' : ''} ${i === STEPS.length - 1 ? 'rounded-r-md' : ''} ${
                        step === 500 ? 'rounded-md' : ''}`}
                      style={{ background: `rgb(${ramp[step]})` }} aria-hidden />
                  </span>
                  <span className="mt-1.5 block font-mono text-[10px] text-ground-500">{step}</span>
                  {/* The identity stop — the colour they actually chose. Every other shade is
                      derived from it, so the palette has to say which one is theirs. */}
                  {step === 500 && (
                    <span data-testid="identity-stop"
                      className="mx-auto mt-1 block h-1 w-1 rounded-full bg-ground-900" />
                  )}
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
              <span className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink">
                {t('admin.programme.colours.sampleButton')}
              </span>
              <span className="rounded-r-lg border-l-4 border-brand-shape bg-primary-50 px-4 py-2 text-sm text-primary-700">
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
                <li key={`${c.mode}-${c.key}`} className="flex items-center gap-3 py-2.5 text-sm"
                  data-testid={`check-${c.mode}-${c.key}`} data-passes={c.passes ? 'yes' : 'no'}>
                  <span aria-hidden className={`grid shrink-0 place-items-center rounded-full text-[11px] font-bold text-white ${
                    c.passes ? 'bg-positive-600' : 'bg-critical-600'}`}
                    style={{ height: '18px', width: '18px' }}>
                    {c.passes ? '✓' : '✗'}
                  </span>
                  {/* Every row now says which mode it measured. Without it a person reading two
                      rows with the same name and different numbers would think one was a mistake. */}
                  <span className="shrink-0 rounded-full bg-ground-100 px-2 py-0.5 text-[11px] font-medium text-ground-600">
                    {t(`admin.programme.colours.mode.${c.mode}`)}
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

          {/* ── the toolbar. FOUR verbs; the two that change what applicants see are on the
                 right, and only ONE of them is the brand-filled button. ───────────────────── */}
          <div className="sticky bottom-0 mt-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ground-200 bg-ground-50 px-5 py-3">
            <p className="text-sm text-ground-700" data-testid="colours-outcome">{statusLine()}</p>
            <div className="flex flex-wrap gap-2">
              <button type="button" data-testid="revert-colours" disabled={!canRevert}
                onClick={() => void run(
                  () => revertOrganisationTheme(org, { token: token as string }),
                  { kind: 'reverted' })}
                className="rounded-lg border border-ground-300 bg-ground-0 px-4 py-2 text-sm font-medium text-ground-700 disabled:opacity-50">
                {theme.previous_colour
                  ? t('admin.programme.colours.revertTo', { colour: theme.previous_colour })
                  : t('admin.programme.colours.revertToDefault')}
              </button>
              <button type="button" data-testid="discard-draft" disabled={!canDiscard}
                onClick={() => {
                  if (theme.draft) {
                    void run(() => discardOrganisationThemeDraft(org, { token: token as string }),
                      { kind: 'draftDiscarded' })
                  } else {
                    // Nothing saved to throw away — just put the box back.
                    setDraft(saved)
                    setOutcome({ kind: 'idle' })
                  }
                }}
                className="rounded-lg border border-ground-300 bg-ground-0 px-4 py-2 text-sm font-medium text-ground-700 disabled:opacity-50">
                {t('admin.programme.colours.discard')}
              </button>
              <button type="button" data-testid="save-draft" disabled={!canSaveDraft}
                onClick={() => void run(
                  () => saveOrganisationThemeDraft(draft, org, { token: token as string }),
                  { kind: 'draftSaved' })}
                title={!edited ? t('common.nothingToSave') : undefined}
                className="rounded-lg border border-primary-600 bg-ground-0 px-4 py-2 text-sm font-semibold text-primary-700 disabled:opacity-50">
                {t('admin.programme.colours.saveDraft')}
              </button>
              <button type="button" data-testid="publish-colours" disabled={!canPublish}
                onClick={() => void run(
                  () => publishOrganisationTheme(org, { token: token as string }),
                  { kind: 'published' })}
                title={edited ? t('admin.programme.colours.saveFirst') : undefined}
                className="rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
                {t('admin.programme.colours.publish')}
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
