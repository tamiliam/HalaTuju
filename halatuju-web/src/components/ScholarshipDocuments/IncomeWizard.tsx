'use client'

/**
 * THE HOUSEHOLD-INCOME WIZARD on the student's Documents tab — Check-1 item 3.
 *
 * ⚠ MOVED OUT OF `../ScholarshipDocuments.tsx` WHOLE (TD-272, 2026-09-20), AND NOTHING ELSE
 * HAPPENED TO IT. Every line below is the line it was; only the declaration gained
 * `export default`, and the imports were re-pointed at the same modules from one directory down.
 * The tab that draws it is still `../ScholarshipDocuments.tsx`.
 *
 * ⚠ THE TWO `react-hooks/exhaustive-deps` DISABLES BELOW ARE DEBT THAT TRAVELLED WITH THE CODE,
 * and they are STILL reasonless on purpose. They are recorded in
 * `halatuju-web/code-standards.json` at THIS path, reached by a declared move in its `_moved`
 * array — the ledger key followed its code, which is the whole point of TD-272's fix. Writing a
 * justification for why a dependency array is deliberately incomplete is ANALYSIS, not a move,
 * and a wrong justification written into the code is worse than the recorded debt. Retiring them
 * (a `useEffectOnce`-style hook, or an honest dependency list) is a later design job. Until then
 * the entries stay, and this file may not gain a third.
 */
import { useState, useEffect, type ReactNode } from 'react'
import {
  updateScholarshipDetails,
  type ApplicantDocument,
  type ScholarshipApplication,
} from '@/lib/api'
import { asksForDocument } from '@/lib/scholarship'
import {
  incomeRequirements,
  wizardComplete,
  hasPatronymic,
  clampDeclared,
  declaredAmount,
  type IncomeRoute,
  type IncomeEarner,
  type WorkingMember,
} from '@/lib/incomeWizard'
import { earningMembers, sameMemberSet } from '@/lib/familyRoster'
import { clusterAnchorKey, clusterDocKey } from '@/lib/documentHelp'
import IncomeClusterCoach from '../IncomeClusterCoach'
import MemberIncomeGroup from '../scholarship/MemberIncomeGroup'
import { docKey, CollapsibleSection } from './cards'

// ── Income wizard (Check-1 item 3) ────────────────────────────────────────
// A few questions → the dynamic document checklist (compulsory + optional),
// mirroring income_engine.income_requirements so the student's list matches the
// officer verdict exactly. Encouraging, never-punitive; nothing here blocks.

// Income cluster docs whose per-file coach is suppressed — the one cluster coach speaks
// for the whole earner cluster instead.
const CLUSTER_COACH_DOCS = new Set([
  'parent_ic', 'str', 'salary_slip', 'epf', 'birth_certificate', 'guardianship_letter',
])

// Slot model (TD-115): on the STR route these income docs belong to the single earner, so
// their card is tagged with the earner (the backend tags uploads the same way). The
// relationship docs (birth_certificate / guardianship_letter) stay member-less single slots.
const STR_EARNER_DOCS = new Set(['str', 'parent_ic', 'salary_slip', 'epf'])

export default function IncomeWizard({
  app,
  token,
  t,
  renderCard,
  onChange,
  docs,
  lang,
}: {
  app: ScholarshipApplication
  token: string | null
  t: (key: string) => string
  renderCard: (docType: string, opts?: { required?: boolean; helpOverride?: string; titleOverride?: string; member?: string; legacyBlank?: boolean; suppressCoach?: boolean }) => ReactNode
  onChange?: () => void
  docs: ApplicantDocument[]
  lang: string
}) {
  // Q1 prefills from the Apply-stage STR declaration (receives_str): had STR → 'str' (Yes),
  // else 'salary' (No). The student can change it.
  const prefillRoute = app.income_route || (app.receives_str ? 'str' : 'salary')
  // Phase-2-lite harmonisation: pre-tick the earners derived from the family roster
  // (the "About your family" professions) so the student doesn't re-name the same
  // people. UI prefill only — saved when the student confirms/changes a selection.
  const rosterEarners = earningMembers(app) as WorkingMember[]
  // STR route needs ONE earner. Default to the roster's earning parent, else FATHER — so the
  // "whose STR" pill is pre-selected and the grouped cluster (STR + that parent's IC) appears
  // immediately. The student can switch to Mother / Legal guardian at any time.
  const defaultEarner = (app.income_earner
    || rosterEarners.find((r) => r === 'father' || r === 'mother' || r === 'guardian')
    || 'father')
  const [ans, setAns] = useState({
    income_route: prefillRoute,
    income_earner: defaultEarner,
    income_working_members: (app.income_working_members && app.income_working_members.length
      ? app.income_working_members
      : rosterEarners) as WorkingMember[],
    // Phase 2A: declared informal income per member ({member: RM/month}).
    income_declared: (app.income_declared || {}) as Partial<Record<WorkingMember, number>>,
  })
  // #1: the prefill above only runs on first mount (useState), so a roster filled or refetched
  // AFTER the income step initialised wouldn't flow through. Keep the salary-route "who works"
  // default in sync with the family roster UNTIL the student explicitly customises it (then we
  // respect their choice). Source of truth: the persisted income_working_members is non-empty
  // once they save, and `touchedMembers` covers the moment before that save round-trips.
  const [touchedMembers, setTouchedMembers] = useState(false)
  // TD-262 F2: the cash/informal door is no longer a FALLBACK behind a text link — it is the
  // third card, and each `MemberIncomeGroup` owns whether its own card is open (seeded from that
  // member's saved figure). Nothing about it is the wizard's business any more.

  const save = async (patch: Record<string, unknown>) => {
    setAns((a) => ({ ...a, ...patch }))
    if (!token) return
    try {
      await updateScholarshipDetails(app.id, patch, { token })
      onChange?.()
    } catch {
      /* soft — local state already updated, save retries on the next change */
    }
  }

  // Persist the prefilled route once (so the verdict reflects the declaration), AND — on the
  // salary route — persist the roster-seeded "who works" so it isn't left silently empty when
  // the student accepts the prefill and just uploads. The uploads get tagged to the earner, but
  // income_working_members was previously only saved on an explicit toggle, so an accepted prefill
  // left tagged docs disagreeing with an empty list → income read as Optional/undeclared. (Backend
  // mirror: income_engine.effective_working_members reconstructs the same fallback.)
  useEffect(() => {
    if (!token) return
    const patch: Record<string, unknown> = {}
    if (!app.income_route) patch.income_route = prefillRoute
    // STR route: persist the defaulted earner so the backend agrees with the pre-selected pill.
    if ((app.income_route || prefillRoute) === 'str' && !app.income_earner) patch.income_earner = defaultEarner
    const routeIsSalary = (app.income_route || prefillRoute) === 'salary'
    if (routeIsSalary && !(app.income_working_members && app.income_working_members.length)
        && rosterEarners.length) {
      patch.income_working_members = rosterEarners
    }
    if (Object.keys(patch).length) {
      updateScholarshipDetails(app.id, patch, { token })
        .then(() => onChange?.())
        .catch(() => { /* soft */ })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // #1: re-seed the roster-derived "who works" / earner default when the roster changes, as long
  // as the student hasn't explicitly chosen (touched, or already saved a non-empty selection).
  useEffect(() => {
    if (touchedMembers) return
    if (app.income_working_members && app.income_working_members.length) return
    const next = earningMembers(app) as WorkingMember[]
    setAns((a) => {
      if (sameMemberSet(a.income_working_members, next)) return a
      const earner = a.income_earner
        || (next.find((r) => r === 'father' || r === 'mother' || r === 'guardian') || '')
      return { ...a, income_working_members: next, income_earner: earner as typeof a.income_earner }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app.father_occupation, app.mother_occupation,
      JSON.stringify(app.other_family_members), app.income_working_members, touchedMembers])

  const iq = (k: string) => t(`scholarship.docs.income.wizard.${k}`)

  const Pills = ({
    options,
    selected,
    onPick,
  }: {
    options: { value: string; label: string }[]
    selected: string
    onPick: (v: string) => void
  }) => (
    <div className="flex flex-wrap gap-2 mt-1.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onPick(o.value)}
          className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
            selected === o.value
              ? 'bg-brand-fill text-brand-fill-ink border-primary-600'
              : 'text-ground-600 border-ground-300 hover:border-primary-400'
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )

  const Question = ({ label, children }: { label: string; children: ReactNode }) => (
    <div>
      <p className="text-sm font-medium text-ground-800">{label}</p>
      {children}
    </div>
  )


  const answers = {
    income_route: ans.income_route as IncomeRoute,
    income_earner: ans.income_earner as IncomeEarner,
    income_working_members: ans.income_working_members,
    income_declared: ans.income_declared,
  }

  // Phase 2A: persist a member's declared average monthly income (0/blank → clear the entry).
  const saveDeclared = (m: WorkingMember, raw: string) => {
    const n = clampDeclared(raw)
    const next = { ...(ans.income_declared || {}) } as Partial<Record<WorkingMember, number>>
    if (n > 0) next[m] = n
    else delete next[m]
    save({ income_declared: next })
  }
  // Is there a supporting letter ON FILE for this earner — the document the cash door uploads?
  // PRESENCE, deliberately: `supportLetterCounts` below asks whether the server would COUNT it,
  // and a letter that did not read is exactly the one a family most needs to reach and replace.
  // Matched the way the card itself matches (`household_member === member`, no `legacyBlank`), so
  // the door is only held open for a letter this earner's card can actually draw.
  const hasSupportLetter = (m: WorkingMember) =>
    docs.some((d) => d.doc_type === 'income_support_doc' && (d.household_member || '') === m)
  // ⚠ THE OLD, WRONG GATE ON THE CASH DOOR — kept ONLY as the fallback for a payload that
  // predates the served answer. It asks whether a salary/EPF FILE exists, not whether it shows
  // anything, so on its own it shut the cash door on a family whose payslip was a photo of the
  // wrong thing (TD-262 F2, the lockout). `MemberIncomeGroup.cashDoorClosed` prefers
  // `app.income_shown` and reaches this only when the api has served nothing.
  const memberHasProof = (m: WorkingMember) =>
    docs.some((d) => (d.doc_type === 'salary_slip' || d.doc_type === 'epf')
      && (d.household_member || '') === m)
  // The student's name comes off their OWN IC (the same name the patronymic match uses).
  // A mononym (no A/L·A/P·…) can't prove a father/sibling link by shared name → the wizard
  // surfaces the birth certificate instead (#55). Unknown until the IC is read → assume a
  // patronymic exists (don't surface the BC prematurely).
  const icName = docs.find((d) => d.doc_type === 'ic')?.vision_name || ''
  const studentHasPatronymic = !icName || hasPatronymic(icName)
  const reqs = incomeRequirements(answers, { studentHasPatronymic })
  const ready = wizardComplete(answers)
  // Green-border / "Complete" cue: the STR cluster is genuinely VERIFIED, not merely uploaded. Presence is
  // MEMBER-AWARE (mirrors the card's own slot match: household_member === earner, or a legacy blank for
  // STR-earner docs — so an IC left tagged to another member never counts as this earner's IC). Then, per
  // owner spec:
  //   • STR  — genuine + an APPROVED STR (current/unconfirmed) whose recipient matches the earner's IC on
  //            name OR IC (either identifies the same person), with no positive mismatch on the other.
  //   • IC   — genuine + readable (name + IC number read).
  //   • relationship doc — it must PROVE the relationship, and a BC ties TWO people, so BOTH ties confirm:
  //            birth certificate → child = the student AND mother = the mother's IC; guardianship letter →
  //            ward = the student AND guardian = the guardian's IC.
  // "Genuine" = not positively flagged suspect/not-<type> (an unscored doc doesn't block — we never gate on
  // our own missing scan).
  const strEarner = ans.income_earner
  const notFlaggedFake = (d: ApplicantDocument) => {
    const a = String(d.authenticity?.status || '')
    return a === '' || a === 'genuine' || a === 'likely_genuine'
  }
  const slotVerified = (dt: string, slotMember: string): boolean => {
    const isEarnerDoc = STR_EARNER_DOCS.has(dt)
    const inSlot = docs.filter((d) => d.doc_type === dt
      && ((d.household_member || '') === slotMember || (isEarnerDoc && !(d.household_member || ''))))
    if (!inSlot.length) return false
    if (dt === 'str') return inSlot.some((d) => {
      // Genuine, approved STR whose recipient matches the earner's IC on name OR IC — either identifies
      // the same person — with no positive mismatch on the other field.
      const c = d.str_check
      const cs = String(c?.current_status || '')
      return notFlaggedFake(d) && (cs === 'current' || cs === 'unconfirmed')
        && c?.name_status !== 'mismatch' && c?.nric_status !== 'mismatch'
        && (c?.name_status === 'match' || c?.nric_status === 'match')
    })
    if (dt === 'parent_ic') return inSlot.some((d) => notFlaggedFake(d) && d.income_ic_check?.readable === true)
    if (dt === 'birth_certificate') return inSlot.some((d) => {
      // A BC ties TWO people (the student AND the parent), so BOTH ties must confirm — not either.
      const b = d.bc_check
      return notFlaggedFake(d) && b?.child_status === 'match' && b?.mother_status === 'match'
    })
    if (dt === 'guardianship_letter') return inSlot.some((d) => {
      const g = d.guardianship_check
      return notFlaggedFake(d) && g?.ward_status === 'match' && g?.guardian_status === 'match'
    })
    return inSlot.some(notFlaggedFake)   // any other compulsory doc: present + not flagged non-genuine
  }
  const strComplete = ans.income_route === 'str' && !!strEarner
    && reqs.compulsory.every((dt) => slotVerified(dt, STR_EARNER_DOCS.has(dt) ? strEarner : ''))
  // A supporting letter the SERVER would count for this earner, asking what
  // `income_engine.has_income_support_doc` asks: tagged to THIS earner OR UNTAGGED (an
  // Action-Centre upload lands untagged, and one family-level letter is enough — D1), not flagged
  // non-genuine, and READ (`student_verdict === 'ok'` — V1 #2: a blank image must not "prove" a
  // declared wage; the student payload carries `vision_fields`). ⚠ One untagged letter therefore
  // ticks EVERY earner who declared an amount, exactly as the api counts the same row for each;
  // this cue reads as the GATE reads (the officer's panel claims it once — TD-262 chunk 2).
  const supportLetterCounts = (d: ApplicantDocument, m: WorkingMember): boolean =>
    ((d.household_member || '') === m || (d.household_member || '') === '')
    && notFlaggedFake(d)
    && (d.vision_fields?.student_verdict || '') === 'ok'
  // A member's income is SHOWN any one way — the three ways the server counts for THIS EARNER
  // (income_engine.member_income_evidenced, arms 1-3; the backend gate is authoritative, and this
  // drives the green cue + the income-collapse trigger): a salary slip, an EPF, or a declared
  // amount backed by a supporting letter. ⚠ THERE IS NO STR ARM, AND THAT IS THE OWNER'S RULE,
  // NOT AN OVERSIGHT (2026-09-19, docs/decisions.md): a household STR clears the gate and predicts
  // green but says nothing about what THIS earner earns — a working adult's proof is ADDITIONAL
  // to a proven STR. The engine's fourth `str_not_breached` arm is a gate shortcut wearing a
  // per-member name; do not copy it here.
  // drift-test: halatuju-web/src/lib/__tests__/incomeEvidenceHomes.test.ts
  const memberIncomeShown = (m: WorkingMember): boolean =>
    slotVerified('salary_slip', m)
    || slotVerified('epf', m)
    || (declaredAmount(ans.income_declared, m) > 0
        && docs.some((d) => d.doc_type === 'income_support_doc' && supportLetterCounts(d, m)))
  // Salary route is "satisfied" once AT LEAST ONE ticked earner is complete: their IC (+ any
  // relationship doc) verified AND their income shown (owner 2026-07-24/25). The rest may come now
  // or at Check 2, and other earners stay optional.
  const salaryComplete = ans.income_route === 'salary'
    && reqs.members.some((block) =>
         block.compulsory.every(({ docType, member }) => slotVerified(docType, member))
         && memberIncomeShown(block.member))
  // Once the chosen route is satisfied, fold the whole income block into a calm green summary
  // that INVITES more evidence rather than demanding it — so the tab never reads as a wall.
  const incomeSatisfied = strComplete || salaryComplete

  // Salary route — toggle a working household member in/out of the multi-select.
  const MEMBER_OPTIONS: WorkingMember[] = ['father', 'mother', 'guardian', 'brother', 'sister']
  const members = ans.income_working_members
  const toggleMember = (m: WorkingMember) => {
    setTouchedMembers(true)   // #1: the student is now choosing — stop syncing from the roster
    const next = members.includes(m) ? members.filter((x) => x !== m) : [...members, m]
    save({ income_working_members: next })
  }

  // STR-route checklist display order: income evidence first, then the earner IC,
  // then the relationship doc.
  const DISPLAY_ORDER = ['str', 'salary_slip', 'epf', 'water_bill', 'electricity_bill',
                         'parent_ic', 'birth_certificate', 'guardianship_letter']
  const ordered = (docs: string[]) =>
    [...docs].sort((a, b) => DISPLAY_ORDER.indexOf(a) - DISPLAY_ORDER.indexOf(b))
  // STR route: income-doc help + IC card title name the single chosen earner.
  const e = ans.income_earner
  // The single cluster coach is dropped directly beneath the MOST RECENTLY UPLOADED document
  // in the earner's cluster (so it sits under whatever the student just added, and moves down
  // when they add the next one) — not at the foot, where it sank below the utility bills.
  const strAnchor = e ? clusterAnchorKey(docs, e, 'str') : ''
  const helpFor = (dt: string): string | undefined => {
    if (!e) return undefined
    if (dt === 'parent_ic') return iq(`icHelp.${e}`)
    if (dt === 'salary_slip') return iq(`salaryHelp.${e}`)
    if (dt === 'epf') return iq(`epfHelp.${e}`)
    return undefined
  }
  // Card titles name the earner so they match the sub-text ("Father's salary slip",
  // "Father's EPF statement") — no confusion about whose document each slot is for.
  const titleFor = (dt: string): string | undefined => {
    if (!e) return undefined
    if (dt === 'str') return iq(`strTitle.${e}`)          // "Father's STR document"
    if (dt === 'parent_ic') return iq(`icTitle.${e}`)
    if (dt === 'salary_slip') return iq(`salaryTitle.${e}`)
    if (dt === 'epf') return iq(`epfTitle.${e}`)
    return undefined
  }
  // Salary route: the same context-aware help/title, but per household-member block.
  const memberHelp = (dt: string, m: string): string | undefined => {
    if (dt === 'parent_ic') return iq(`icHelp.${m}`)
    if (dt === 'salary_slip') return iq(`salaryHelp.${m}`)
    if (dt === 'epf') return iq(`epfHelp.${m}`)
    return undefined // birth cert / guardianship letter keep their default help
  }
  const memberTitle = (dt: string, m: string): string | undefined => {
    if (dt === 'parent_ic') return iq(`icTitle.${m}`)
    if (dt === 'salary_slip') return iq(`salaryTitle.${m}`)
    if (dt === 'epf') return iq(`epfTitle.${m}`)
    return undefined
  }

  // Utility bills are HOUSEHOLD-level (not route-specific), so they render ONCE in a shared
  // "Utilities" block below both route branches — Electricity first, then Water.
  const UTILITY_DOCS = ['electricity_bill', 'water_bill']

  const body = (
    <div className="space-y-4">
      {/* Encouraging, never-punitive intro (blue = info). */}
      <div className="rounded-xl bg-info-50 ring-1 ring-info-100 p-3 text-sm text-info-900/90">
        {iq('intro')}
      </div>

      {/* Q1 — STR document? Yes → STR route, No → salary route */}
      <Question label={iq('q1')}>
        <Pills selected={ans.income_route}
          options={[{ value: 'str', label: iq('yes') }, { value: 'salary', label: iq('no') }]}
          onPick={(v) => save({ income_route: v })} />
      </Question>

      {/* Q2 — STR route: a single earner. Salary route: tick everyone who works. */}
      {ans.income_route === 'str' ? (
        <Question label={iq('q2Str')}>
          <Pills selected={ans.income_earner}
            options={['father', 'mother', 'guardian'].map((v) => ({ value: v, label: iq(`earner.${v}`) }))}
            onPick={(v) => save({ income_earner: v })} />
        </Question>
      ) : (
        <Question label={iq('q2Multi')}>
          <div className="flex flex-wrap gap-2 mt-1.5">
            {MEMBER_OPTIONS.map((m) => {
              const on = members.includes(m)
              return (
                <button key={m} type="button" onClick={() => toggleMember(m)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    on ? 'bg-brand-fill text-brand-fill-ink border-primary-600'
                       : 'text-ground-600 border-ground-300 hover:border-primary-400'}`}>
                  {on ? '✓ ' : ''}{iq(`member.${m}`)}
                </button>
              )
            })}
          </div>
        </Question>
      )}

      {/* Family burden (siblings in school / tertiary) moved to the Story tab's
          "About your family" card in the 2026-06 redesign — captured once there. */}

      {/* Dynamic checklist — appears once the wizard is answered. Compulsory docs carry a
          red * on the card title; optional docs carry no marker (the * is what distinguishes). */}
      {ready && ans.income_route === 'str' && (
        <div className="space-y-3 pt-1">
          {/* THE GROUP: the STR proof + the earner's IC (+ a relationship doc for mother/guardian).
              Each card names the earner ("Father's STR document", "Father's IC"), so the box needs no
              header. Green BORDER (no fill) + a "Complete" badge once every compulsory doc is on file.
              Supplementary income evidence (salary slip / EPF / utilities) renders BELOW, outside the box. */}
          <div className={`rounded-lg border bg-ground-50/60 p-2.5 space-y-2 ${
            strComplete ? 'border-positive-300' : 'border-ground-100'}`}>
            {strComplete && (
              <div className="flex justify-end">
                <span className="inline-flex items-center gap-1 rounded-full border border-positive-200 bg-positive-100 px-2 py-0.5 text-[10px] font-bold text-positive-700">
                  <svg className="h-2.5 w-2.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20 6 9 17l-5-5" />
                  </svg>
                  {iq('clusterDone')}
                </span>
              </div>
            )}
            {ordered(reqs.compulsory).map((dt) => (
              <div key={dt}>
                {renderCard(dt, { required: true, helpOverride: helpFor(dt), titleOverride: titleFor(dt),
                  ...(STR_EARNER_DOCS.has(dt) ? { member: e, legacyBlank: true } : {}),
                  suppressCoach: CLUSTER_COACH_DOCS.has(dt) })}
                {/* The single cluster coach rides directly under the most recently uploaded cluster doc. */}
                {e && clusterDocKey(dt, '') === strAnchor && (
                  <div className="mt-2"><IncomeClusterCoach member={e} route="str" docs={docs} token={token} t={t} lang={lang} /></div>
                )}
              </div>
            ))}
          </div>
          {/* Supplementary income evidence (salary slip / EPF) — optional on the STR route (the STR
              already evidences income), so it folds into a quiet collapsible (default closed) like
              Utilities, so it never adds to the wall. Utilities render once in the shared block below. */}
          {(() => {
            const supp = ordered(reqs.optional).filter((dt) => !UTILITY_DOCS.includes(dt))
            if (supp.length === 0) return null
            return (
              <CollapsibleSection
                tone="optional"
                title={iq('supplementaryTitle')}
                summary={iq('supplementaryNote')}
                openLabel={t('scholarship.docs.add')}
                hideLabel={t('scholarship.docs.hide')}
              >
                <div className="space-y-3">
                  {supp.map((dt) => (
                    <div key={dt}>
                      {renderCard(dt, { required: false, helpOverride: helpFor(dt), titleOverride: titleFor(dt),
                        ...(STR_EARNER_DOCS.has(dt) ? { member: e, legacyBlank: true } : {}),
                        suppressCoach: CLUSTER_COACH_DOCS.has(dt) })}
                      {e && clusterDocKey(dt, '') === strAnchor && (
                        <div className="mt-2"><IncomeClusterCoach member={e} route="str" docs={docs} token={token} t={t} lang={lang} /></div>
                      )}
                    </div>
                  ))}
                </div>
              </CollapsibleSection>
            )
          })()}
        </div>
      )}

      {/* Salary route — one document block per ticked working member. */}
      {ready && ans.income_route === 'salary' && (
        <div className="space-y-3 pt-1">
          {reqs.members.map((block) => {
            // This member's cluster coach rides under their most recently uploaded cluster doc.
            const salAnchor = clusterAnchorKey(docs, block.member, 'salary')
            const coach = (
              <div className="mt-2"><IncomeClusterCoach member={block.member} route="salary" docs={docs} token={token} t={t} lang={lang} /></div>
            )
            return (
            <div key={block.member} className="rounded-lg border border-ground-100 bg-ground-50/60 p-2.5 space-y-2">
              <p className="text-xs font-semibold text-ground-700">{iq(`member.${block.member}`)}</p>
              {block.compulsory.map(({ docType, member }) => (
                <div key={docKey(docType, member)}>
                  {renderCard(docType, { required: true, member,
                    helpOverride: memberHelp(docType, block.member),
                    titleOverride: memberTitle(docType, block.member),
                    suppressCoach: CLUSTER_COACH_DOCS.has(docType) })}
                  {clusterDocKey(docType, member) === salAnchor && coach}
                </div>
              ))}
              {/* Income — shown ANY ONE way (owner 2026-07-25), and since TD-262 F2 the screen
                  finally SAYS so: three cards of equal weight, the third opening in place to the
                  cash/informal amount + its one letter. Green once any one is shown. */}
              <MemberIncomeGroup
                block={block}
                t={t}
                iq={iq}
                shown={memberIncomeShown(block.member)}
                served={app.income_shown}
                presenceFallback={memberHasProof(block.member)}
                declared={declaredAmount(ans.income_declared, block.member)}
                hasSupportLetter={hasSupportLetter(block.member)}
                onDeclare={saveDeclared}
                renderCard={renderCard}
                memberHelp={memberHelp}
                memberTitle={memberTitle}
                clusterCoachDocs={CLUSTER_COACH_DOCS}
                docKeyOf={docKey}
                clusterDocKeyOf={clusterDocKey}
                salaryAnchor={salAnchor}
                coach={coach}
              />
            </div>
          )})}
        </div>
      )}

      {/* Utilities + closing note — SHARED across BOTH income routes (household-level docs are the
          same regardless of STR vs salary). Household-level and always optional, so it folds into
          a quiet collapsible (default closed) — never a wall. Electricity first, then Water. */}
      {ready && (() => {
        // Two independent filters, and they answer different questions. `reqs.optional` is the
        // income ROUTE engine ("does this household's route surface a utility bill?");
        // `asksForDocument` is the PROGRAMME ("does this organisation collect one at all?").
        // A bill has to clear both — the route can no more override the configuration than the
        // configuration can reach inside the route.
        const utils = UTILITY_DOCS.filter(
          (dt) => reqs.optional.includes(dt) && asksForDocument(app.requirements, dt))
        return (
          <div className="space-y-3 pt-1">
            {utils.length > 0 && (
              <CollapsibleSection
                tone="optional"
                title={iq('utilities')}
                summary={iq('utilitiesNote')}
                openLabel={t('scholarship.docs.add')}
                hideLabel={t('scholarship.docs.hide')}
              >
                <div className="space-y-3">
                  {utils.map((dt) => (<div key={dt}>{renderCard(dt, { required: false })}</div>))}
                </div>
              </CollapsibleSection>
            )}
            <p className="text-xs text-ground-400">{iq('footer')}</p>
          </div>
        )
      })()}
    </div>
  )

  // Satisfied → the whole block folds behind a green, inviting summary (add-more, not done-forever).
  if (incomeSatisfied) {
    return (
      <CollapsibleSection
        tone="done"
        title={iq('satisfiedTitle')}
        summary={iq('satisfiedNote')}
        openLabel={t('scholarship.docs.view')}
        hideLabel={t('scholarship.docs.hide')}
      >
        {body}
      </CollapsibleSection>
    )
  }
  return body
}
