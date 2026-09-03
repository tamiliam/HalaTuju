'use client'

// Programme → Configuration → Rules. The FIRST tab, ahead of "what we ask for" (owner,
// 2026-09-03: "I see the rules as a configuration item, and it precedes what we ask for").
//
// ⚠ IT EDITS THE ROUND YOU ARE RUNNING, NOT THE GIFT. The six thresholds are columns on the
// intake year (`ScholarshipCohort`), which is where the decision engine reads them, and they stay
// there: moving them up to the Programme would be a behaviour-sensitive migration for no gain,
// and the roadmap already declined it. So the screen speaks the owner's model — "this gift's
// rules" — while the data stays on the row the engine trusts. The heading names the year, because
// a rules screen that will not tell you which round it is changing is a trap.
//
// ⚠⚠ RULES ARE NOT FROZEN FOR SUBMITTED STUDENTS AND "WHAT WE ASK FOR" IS. That asymmetry is the
// reason for the warning on this tab and not the next one. `requirements_snapshot` freezes the
// documents and questions per application at submit, so changing them touches nobody already in;
// `shortlisting.evaluate()` reads these thresholds LIVE, so changing them changes who passes from
// that moment on, and a re-run re-bands. Two settings, one screen, different blast radius — say so
// rather than letting them look like the same kind of switch.
//
// ⚠ THE VALUE IS THE SWITCH. Unticking a requirement clears it, and a cleared requirement is NOT
// APPLIED — the defect S2a found was every threshold being NOT NULL with a default, so BrightPath
// carried an STPM floor it never asked for, applied to nine live applicants for a whole intake.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useSelectedProgramme } from '@/lib/useSelectedProgramme'
import InfoBox from '@/components/InfoBox'
import ChooseProgramme from '@/components/admin/ChooseProgramme'
import RequirementFields from '@/components/admin/RequirementFields'
import {
  getAdminIntakeYears, updateAdminIntakeYear, type AdminIntakeYear,
} from '@/lib/admin-api'
import {
  draftToRequirements, requirementsToDraft, EMPTY_REQUIREMENTS, type RequirementDraft,
} from '@/lib/intakeYears'

type Outcome = { kind: 'idle' } | { kind: 'saved' } | { kind: 'error'; message: string }

/**
 * WHICH round's rules. The one taking applications, else the newest — the round an admin means
 * when they say "our rules". Returns null when the gift has no year yet, which is a real state on
 * a gift created five minutes ago and must be said, not defaulted around.
 */
export function ruleYear(years: readonly AdminIntakeYear[]): AdminIntakeYear | null {
  if (years.length === 0) return null
  return years.find((y) => y.is_open)
    ?? [...years].sort((a, b) => b.year - a.year)[0]
}

export default function ProgrammeRulesTab() {
  const { token } = useAdminAuth()
  const { t } = useT()
  const { programme, programmes, loading, mustChoose, select } = useSelectedProgramme()

  const [years, setYears] = useState<AdminIntakeYear[]>([])
  const [draft, setDraft] = useState<RequirementDraft>(EMPTY_REQUIREMENTS)
  const [saved, setSaved] = useState<RequirementDraft>(EMPTY_REQUIREMENTS)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })
  /**
   * ⚠ ITS OWN LOADING FLAG, AND NOT THE ONE FROM `useSelectedProgramme`. That one goes false as
   * soon as the PROGRAMMES have arrived, which is strictly earlier than the YEARS — so keying the
   * empty state on it made the tab announce "this gift has no intake year yet" for a moment on
   * every load, about a gift with a live round. An empty card is never merely useless: it asserts
   * something, and here it asserted something false (lessons.md, 2026-08-18). Caught by the
   * rendered test, invisible to any source-shape guard.
   */
  const [yearsLoading, setYearsLoading] = useState(true)

  const programmeId = programme?.id ?? null
  const year = useMemo(() => ruleYear(years), [years])

  const load = useCallback(async () => {
    if (!token || programmeId === null) { setYears([]); return }
    setYearsLoading(true)
    try {
      const d = await getAdminIntakeYears(programmeId, { token })
      setYears(d.years)
      const target = ruleYear(d.years)
      const asDraft = requirementsToDraft(target?.requirements)
      setDraft(asDraft)
      setSaved(asDraft)
      setOutcome({ kind: 'idle' })
    } catch {
      setOutcome({ kind: 'error', message: t('admin.years.loadFailed') })
    } finally {
      setYearsLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, programmeId])

  useEffect(() => { void load() }, [load])

  // The platform's nothing-to-save standard (request #6): a Save with no edit behind it is a
  // control that promises something. ⚠ The dangerous direction is the opposite of the bug — a
  // Save wrongly ASLEEP strands real work — so this compares the draft with what was LOADED, and
  // any difference at all wakes it.
  const dirty = useMemo(
    () => (Object.keys(draft) as (keyof RequirementDraft)[]).some((k) => draft[k] !== saved[k]),
    [draft, saved],
  )

  const save = async () => {
    if (!year || !token) return
    setBusy(true); setOutcome({ kind: 'idle' })
    try {
      await updateAdminIntakeYear(year.id, draftToRequirements(draft), { token })
      await load()
      setOutcome({ kind: 'saved' })
    } catch (e) {
      const code = (e as { code?: string })?.code
      setOutcome({
        kind: 'error',
        message: t(`admin.years.error.${code === 'bad_year' ? 'badYear' : 'generic'}`),
      })
    } finally {
      setBusy(false)
    }
  }

  if (mustChoose) return <ChooseProgramme programmes={programmes} onSelect={select} />

  if (!loading && programmes.length === 0) {
    return (
      <p className="mt-6 rounded-2xl border border-dashed border-ground-300 px-4 py-10 text-center text-sm text-ground-400">
        {t('admin.years.noProgrammes')}
      </p>
    )
  }

  // A gift with no round yet. Say what is missing and where it is made, rather than drawing six
  // empty boxes that would save nowhere. ⚠ Only once the YEARS have actually been asked for —
  // see `yearsLoading`.
  if (programme && !loading && !yearsLoading && years.length === 0) {
    return (
      <div className="mt-6">
        <InfoBox kind="info">{t('admin.rules.noYear')}</InfoBox>
      </div>
    )
  }

  return (
    <div className="mt-6" data-testid="rules-tab">
      <p className="text-sm text-ground-600">{t('admin.rules.subtitle')}</p>

      {year && (
        <p className="mt-1 text-sm font-medium text-ground-800" data-testid="rules-year">
          {t('admin.rules.editing', { year: String(year.year), name: year.name })}
        </p>
      )}

      {/* ⚠ NOT the same caution the config tab shows. That one warns about a live intake; this one
          warns that the change is NOT frozen for anybody, which is a different and larger claim. */}
      <div className="mt-4">
        <InfoBox kind="warning">{t('admin.rules.liveWarning')}</InfoBox>
      </div>

      <div className="mt-4">
        <RequirementFields draft={draft} onChange={setDraft} idPrefix="rules" />
      </div>

      <p className="mt-3 text-xs text-ground-500">{t('admin.rules.untickNote')}</p>

      <div className="mt-5 flex items-center gap-4">
        <button type="button" onClick={save} disabled={busy || !dirty || !year}
          className="rounded-lg bg-brand-fill px-5 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover disabled:opacity-50">
          {t('common.save')}
        </button>
        {!dirty && !busy && (
          <span className="text-sm text-ground-500">{t('common.nothingToSave')}</span>
        )}
        {outcome.kind === 'saved' && (
          <span className="text-sm font-medium text-positive-700">{t('admin.rules.saved')}</span>
        )}
        {outcome.kind === 'error' && (
          <span className="text-sm font-medium text-critical-600">{outcome.message}</span>
        )}
      </div>
    </div>
  )
}
