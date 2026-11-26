'use client'

// Programme → Configuration → Rules. The FIRST tab, ahead of "what we ask for" (owner,
// 2026-09-03: "I see the rules as a configuration item, and it precedes what we ask for").
//
// ⚠ IT EDITS THE ROUND YOU ARE RUNNING, NOT THE GIFT. The seven thresholds are columns on the
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
// ⚠ A SWITCHED-OFF TEST IS NOT APPLIED — the defect S2a found was every threshold being NOT NULL
// with a default, so BrightPath carried an STPM floor it never asked for.
//
// CRITERIA EDITOR SPRINT 4: the screen edits the rule year's stored criteria TREE through the
// programme criteria API (`getProgrammeCriteria` / `saveProgrammeCriteria`), not the seven columns.
// The save names the year shown (`intake_id`), so a year opened meanwhile is never edited by
// mistake (409 rule_year_changed -> reload). An intake whose tree is not built yet shows its rules
// read-only with a calm notice (criteria_not_built: trees are built on live by a separate command).

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { useLatest } from '@/lib/useLatest'
import { useSelectedProgramme } from '@/lib/useSelectedProgramme'
import InfoBox from '@/components/InfoBox'
import ChooseProgramme from '@/components/admin/ChooseProgramme'
import CriteriaEditor from '@/components/admin/CriteriaEditor'
import SaveBar, { SAVE_BAR_PRIMARY } from '@/components/admin/SaveBar'
import {
  getProgrammeCriteria, saveProgrammeCriteria, type AdminIntakeYear, type CriteriaPayload,
} from '@/lib/admin-api'
import {
  canShow, errorKey, sameTree, stateToTree, treeToState, EMPTY_STATE, type EditorState,
} from '@/lib/criteriaTree'

type Outcome = { kind: 'idle' } | { kind: 'saved' } | { kind: 'error'; message: string }

/**
 * WHICH round's rules. The one taking applications, else the newest — the round an admin means
 * when they say "our rules". Returns null when the gift has no year yet. The server's
 * `criteria_tree.rule_year` is this exactly; the tab now asks the server, this stays for callers.
 */
export function ruleYear(years: readonly AdminIntakeYear[]): AdminIntakeYear | null {
  if (years.length === 0) return null
  return years.find((y) => y.is_open)
    ?? [...years].sort((a, b) => b.year - a.year)[0]
}

/** `goToYear` switches the page to the Intake year tab. Optional so the component still mounts
 *  standalone in tests; when absent the empty state falls back to prose alone. */
export default function ProgrammeRulesTab({ goToYear }: { goToYear?: () => void } = {}) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const { programme, programmes, loading, mustChoose, select } = useSelectedProgramme()

  const [payload, setPayload] = useState<CriteriaPayload | null>(null)
  const [noYear, setNoYear] = useState(false)
  const [draft, setDraft] = useState<EditorState>(EMPTY_STATE)
  const [saved, setSaved] = useState<EditorState>(EMPTY_STATE)
  const [busy, setBusy] = useState(false)
  const [outcome, setOutcome] = useState<Outcome>({ kind: 'idle' })
  /** The server's own reasons for refusing a tree (bad_criteria), shown as it sends them. */
  const [serverProblems, setServerProblems] = useState<string[]>([])
  /** Another admin saved first (409 criteria_changed): offer a reload, never overwrite. */
  const [stale, setStale] = useState(false)
  /**
   * ⚠ ITS OWN LOADING FLAG, AND NOT THE ONE FROM `useSelectedProgramme`: that one goes false as
   * soon as the PROGRAMMES have arrived, strictly earlier than the rules — keying the empty state
   * on it announced "no intake year" for a moment about a gift with a live round (lessons.md,
   * 2026-08-18).
   */
  const [rulesLoading, setRulesLoading] = useState(true)

  const programmeId = programme?.id ?? null
  const year = payload?.intake ?? null
  const rulesError = payload?.rules_error === true
  const notBuilt = payload !== null && !rulesError && !payload.stored
  const unshowable = payload !== null && !rulesError && !canShow(payload.criteria)
  const locked = rulesError || notBuilt || unshowable

  const tRef = useLatest(t)   // read inside the loader so a language switch does not re-run it
  const load = useCallback(async (keepOutcome = false) => {
    if (!token || programmeId === null) { setPayload(null); return }
    setRulesLoading(true)
    try {
      const d = await getProgrammeCriteria(programmeId, { token })
      setPayload(d); setNoYear(false)
      const s = treeToState(d.criteria)
      setDraft(s); setSaved(s); setServerProblems([]); setStale(false)
      if (!keepOutcome) setOutcome({ kind: 'idle' })
    } catch (e) {
      const code = (e as { code?: string })?.code
      if (code === 'no_intake_year') { setNoYear(true); setPayload(null) }
      else setOutcome({ kind: 'error', message: tRef.current('admin.years.loadFailed') })
    } finally {
      setRulesLoading(false)
    }
  }, [token, programmeId, tRef])

  useEffect(() => { void load() }, [load])

  // Nothing-to-save standard (request #6): compare with what was LOADED; any difference wakes Save.
  const dirty = useMemo(() => !sameTree(draft, saved), [draft, saved])
  // What would stop a save, worked out as the admin types: Save sleeps and the reasons show, so a
  // tree the server would refuse is never sent (an unchanged screen shows no reasons).
  const problems = useMemo(() => (dirty ? stateToTree(draft).problems : []), [dirty, draft])

  const statusLine = () => {
    if (outcome.kind === 'saved') {
      return <span className="font-medium text-positive-700">{t('admin.rules.saved')}</span>
    }
    if (outcome.kind === 'error') {
      return <span className="font-medium text-critical-600" data-testid="rules-save-error">{outcome.message}</span>
    }
    return dirty ? t('common.unsavedChanges') : null
  }

  const save = async () => {
    if (!year || !token || programmeId === null || locked) return
    const { tree, problems: local } = stateToTree(draft)
    if (local.length) return
    setBusy(true); setOutcome({ kind: 'idle' })
    try {
      await saveProgrammeCriteria(programmeId, year.id, tree, payload?.digest, { token })
      await load(true)
      setOutcome({ kind: 'saved' })
    } catch (e) {
      const err = e as { code?: string; status?: number; body?: { problems?: unknown } }
      setOutcome({ kind: 'error', message: t(errorKey(err?.code, err?.status)) })
      const sent = err?.body?.problems
      setServerProblems(Array.isArray(sent) ? sent.filter((p): p is string => typeof p === 'string') : [])
      if (err?.code === 'criteria_changed') setStale(true)
      // Another year started taking applications: show the rules of the year that is now in force.
      if (err?.code === 'rule_year_changed') await load(true)
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

  // A gift with no round yet: say what is missing and point to where it is made (PF-1: it points;
  // it does not create a year for them). Only once the rules have actually been asked for.
  if (programme && !loading && !rulesLoading && noYear) {
    return (
      <div className="mt-6">
        <InfoBox kind="info">{t('admin.rules.noYear')}</InfoBox>
        {goToYear && (
          <button type="button" onClick={goToYear} data-testid="rules-go-to-year"
            className="mt-3 rounded-lg bg-brand-fill px-4 py-2 text-sm font-semibold text-brand-fill-ink hover:bg-brand-fill-hover">
            {t('admin.rules.goToYear')}
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="mt-6" data-testid="rules-tab">
      {year && (
        <p className="text-sm font-medium text-ground-800" data-testid="rules-year">
          {t('admin.rules.editing', { year: String(year.year), name: year.name })}
        </p>
      )}

      {/* ⚠ The change is NOT frozen for anybody already in - a larger claim than a live-intake note. */}
      <div className="mt-4">
        <InfoBox kind="warning">{t('admin.rules.liveWarning')}</InfoBox>
      </div>

      {rulesError && (
        <div className="mt-4" data-testid="rules-error">
          <InfoBox kind="block">{t('admin.rules.rulesError')}</InfoBox>
        </div>
      )}
      {notBuilt && (
        <div className="mt-4" data-testid="rules-not-built">
          <InfoBox kind="info">{t('admin.criteria.notReady')}</InfoBox>
        </div>
      )}
      {unshowable && !notBuilt && (
        <div className="mt-4" data-testid="rules-cannot-show">
          <InfoBox kind="block">{t('admin.criteria.cannotShow')}</InfoBox>
        </div>
      )}

      {!rulesError && payload && (
        <div className="mt-4">
          <CriteriaEditor state={draft} onChange={setDraft} disabled={locked} idPrefix="rules" />
        </div>
      )}

      {problems.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-sm text-critical-600" data-testid="rules-problems">
          {problems.map((p) => <li key={p}>{t(`admin.criteria.problem.${p}`)}</li>)}
        </ul>
      )}

      {serverProblems.length > 0 && (
        <ul className="mt-3 list-disc pl-5 text-sm text-critical-600" data-testid="rules-server-problems">
          {serverProblems.map((p) => <li key={p}>{p}</li>)}
        </ul>
      )}

      {stale && (
        <div className="mt-3" data-testid="rules-stale">
          <InfoBox kind="warning">{t('admin.criteria.error.criteriaChanged')}</InfoBox>
          <button type="button" onClick={() => { void load() }} data-testid="rules-reload"
            className="mt-2 rounded-lg border border-ground-300 px-3 py-1.5 text-sm font-medium text-ground-800">
            {t('admin.criteria.reload')}
          </button>
        </div>
      )}

      <p className="mt-3 text-xs text-ground-500">{t('admin.criteria.foot')}</p>

      <SaveBar status={statusLine()}>
        <button type="button" onClick={save} disabled={busy || !dirty || !year || locked || problems.length > 0}
          title={!dirty ? t('common.nothingToSave') : undefined}
          className={SAVE_BAR_PRIMARY}>
          {t('common.save')}
        </button>
      </SaveBar>
    </div>
  )
}
