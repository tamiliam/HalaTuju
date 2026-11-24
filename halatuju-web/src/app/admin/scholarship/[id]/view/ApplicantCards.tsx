'use client'

/**
 * THE APPLICANT SUMMARY — About, Family & finances, Academic (with Plans folded in) and Support,
 * in two masonry columns.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. The household income / size readings arrive
 * as props, computed by `householdFigures` below (request #54 moved them here from the cockpit).
 */
import { isThirdRoute } from '@/lib/qualification'
import VerifiedTick from '@/components/VerifiedTick'
import { shownInstitution } from '@/lib/fieldVerification'
import {
  formatPhone,
  formatAddress,
  expandMatricInstitution,
} from '@/lib/scholarship'
import { higherExamYear, spmExamYear } from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import { isApplyStage } from '@/lib/applicationStatus'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import { Card, DiffMarker, Field, Grades, joinOr, resultsChangeKey, yn, NON_PARENT_RELATIONSHIPS, type T, type Vtip } from './shared'
import { GuardianCorrect } from './GuardianCorrect'
import { GuardianCallRecord } from './GuardianCallRecord'
import { FamilyAnswers } from './FamilyAnswers'

const V = 'admin.scholarship.verified'
const rm = (n: number) => `RM ${Number(n).toLocaleString('en-US')}`

/**
 * The household income / size / per-capita fields (from the server's `household_check`). Request
 * #54 (owner 2026-11-06): the card shows what the student DECLARED. A tick means the documents
 * support it — income only on a ±10% / RM300 match (`income.matches`), size when accounted for or
 * confirmed. When the documents disagree, an amber note names what they show (never a replacement
 * of the declared figure); when an earner's document is untrusted or unread, the note gives the
 * total read so far and names who. Per capita = declared income ÷ effective size. Display only.
 */
export function householdFigures(app: AdminScholarshipDetail, t: T) {
  const hc = app.household_check
  const inc = hc?.income
  const notes: string[] = []
  if (inc?.documented_total != null && !inc.matches) {
    notes.push(t(`${V}.incomeDiffers`, { value: rm(inc.documented_total) }))
  } else if (inc && inc.documented_total == null && inc.has_documents && inc.unchecked?.length) {
    if (inc.read_total) notes.push(t(`${V}.incomePartial`, { value: rm(inc.read_total) }))
    for (const u of inc.unchecked) {
      const member = t(`scholarship.docs.income.wizard.member.${u.member}`)
      notes.push(u.reason === 'unverified' ? t(`${V}.uncheckedUnverified`, { member }) : t(`${V}.uncheckedUnread`, { member }))
    }
  }
  // Household size: once the student CONFIRMS the roster count (household_size_confirm query), the
  // roster count leads with a tick and the stated figure drops to a muted "Declared: M" note.
  // Otherwise: a tick when fully accounted, or an amber "Roster counts N" on an unconfirmed over-count.
  const confirmed = !!hc?.size.confirmed
  const size = confirmed ? hc!.size.described : app.household_size
  return {
    incomeValue: app.household_income ? rm(app.household_income) : null,
    incomeTip: inc?.matches ? t(`${V}.tooltip`, { source: t(`${V}.source.incomeProof`) }) : undefined,
    incomeNote: notes.length ? notes.join(' ') : undefined,
    sizeValue: size,
    sizeTip: (confirmed || hc?.size.accounted) ? t(`${V}.sizeAccounted`) : undefined,
    sizeNote: confirmed
      ? (app.household_size ? t(`${V}.declaredNote`, { value: String(app.household_size) }) : undefined)
      : (hc?.size.overcount ? t(`${V}.rosterNote`, { count: String(hc.size.described) }) : undefined),
    sizeNoteTone: (confirmed ? 'muted' : 'amber') as 'amber' | 'muted',
    perCapita: app.household_income && size ? app.household_income / size : null,
  }
}

export function ApplicantCards({
  app, t, vtip, incomeValue, incomeTip, incomeNote,
  sizeValue, sizeTip, sizeNote, sizeNoteTone, perCapita, canCorrectGuardian, onGuardianCorrected,
}: {
  app: AdminScholarshipDetail
  t: T
  vtip: Vtip
  incomeValue: string | null
  incomeTip: string | undefined
  incomeNote: string | undefined
  sizeValue: number | null
  sizeTip: string | undefined
  sizeNote: string | undefined
  sizeNoteTone: 'amber' | 'muted'
  perCapita: number | null
  /** Request #26: super / org_admin may correct the parent/guardian contact (the server re-gates). */
  canCorrectGuardian?: boolean
  onGuardianCorrected?: () => void | Promise<void>
}) {
  return (<>

      {/* Applicant info — three explicit columns (About+Family / Academic / Support…) */}
      {(() => {
        const isStpm = app.qualification === 'stpm'
        // Third results route S2b: Matriculation / Asasi / Diploma — STPM-equivalent, but its own
        // lines: the qualification + the server's overall CGPA, the CGPA as printed, the SPM block.
        const third = isThirdRoute(app.qualification) ? app.qualification : null
        // A required slot with no value reads N/A in a muted colour (owner mock, 2026-11-24).
        const na = t('admin.scholarship.na')
        const fmt2 = (n?: number | null) => (n == null ? n : Number(n).toFixed(2))
        // STPM CGPA C3 (owner 2026-10-28): the STPM grades and CGPA come from onboarding and are
        // counter-checked against the uploaded STPM results ON THE SERVER (`stpm_marks.py`, through
        // higher_results' own matcher) — a match gets the same tick the SPM grades carry, a
        // difference a marker naming what the document shows; no read document → no mark.
        const sm = isStpm ? app.stpm_marks : null
        const stpmMark = (m?: { status: 'match' | 'differ'; doc: string | number } | null) => (!m ? null
          : m.status === 'match'
            ? <VerifiedTick label={t('admin.scholarship.verified.tooltip', { source: t('admin.scholarship.verified.source.stpmResults') })} />
            : <DiffMarker label={t('admin.scholarship.verified.stpmDiffers', { value: String(m.doc) })} />)
        // ONE tick after the chips when every subject matches, like the SPM grades (owner,
        // 2026-10-30: "to be consistent with SPM"). A subject that differs keeps its own marker
        // naming what the document shows; a match no longer repeats the tick on every chip.
        const smGrades = Object.entries(sm?.grades || {})
        // ...and only when the slip itself has no STPM subject she left out (owner 2026-11-06: a
        // tick means subjects AND grades match exactly; `all_subjects` is the server's answer).
        const stpmAllMatch = smGrades.length > 0
          && smGrades.length === Object.values(app.stpm_grades || {}).filter(Boolean).length
          && smGrades.every(([, m]) => m?.status === 'match')
          && sm?.all_subjects === 'match'
        const gradeMarks = sm ? Object.fromEntries(smGrades.filter(([, m]) => m?.status === 'differ')
          .map(([k, m]) => [k, stpmMark(m)])) : undefined
        const cgpaMark = sm?.cgpa === 'match' || sm?.cgpa === 'differ'
          ? stpmMark({ status: sm.cgpa, doc: fmt2(sm.cgpa_doc) ?? '' })
          : sm?.cgpa === 'not_calculated'
            ? <span className="ml-1 text-xs text-ground-400">({t('admin.scholarship.stpmCgpaNotCalculated')})</span>
            : null
        // Pathway context: matric/stpm are INSTITUTION pathways (track + school);
        // everything else (asasi, university, poly, pismp…) is a PROGRAMME pathway
        // (a chosen course), so Pre-U track doesn't apply.
        const isInstitutionPathway = app.chosen_pathway === 'matric' || app.chosen_pathway === 'stpm'
        // Human labels for the stored codes — reuse the apply-form's own i18n maps so
        // the admin sees the same words the student did (matric→Matriculation, etc.).
        const pathwayLabel = (code?: string | null) => (code ? t(`scholarship.apply.plan.pathway.${code}`) : null)
        // pre_u_track holds a matric TRACK (sains/kejuruteraan…) or an STPM STREAM
        // (sains/sains_sosial/not_sure). The cockpit shows the Malay term ONLY (owner 2026-07-18) —
        // "Sains Sosial", not the apply form's bilingual "Social Science (Sains Sosial)".
        // ⚠ SERVED, NOT MIRRORED (TD-280, code health H18). This used to be `preUTrackMalay(...)`
        // from `lib/preUPlan`, which statically imported the whole Malay catalogue — 130 kB of
        // first-load JS on this route for sixteen words. The api resolves it now; we render it.
        // ⚠ `?? null` collapses the two absences ON PURPOSE (audit 2026-09-21, finding G).
        // `null` = the api has no label for this code; `undefined` = an api revision (or a
        // cached payload) from before TD-280 that never sent the field. Both must render the
        // same nothing: a raw `sains_sosial`, or the word `undefined`, would be worse than a
        // missing suffix, and re-deriving the Malay word here is TD-280 all over again.
        const preUTrackLabel = app.pre_u_track_label ?? null
        // Help answers: render the apply-form's own words (Yes / No / Not sure) rather
        // than the raw 'yes'/'no'/'unsure' codes.
        const helpLabel = (v?: string | null) => (v ? t(`scholarship.apply.help.${v}`) : null)
        // Link a course back to its HalaTuju public page (opens in a new tab so
        // the admin doesn't lose the application). STPM degrees live under /stpm.
        // Every genuine programme has a page: a catalogue course_id → /course (or /stpm for an
        // STPM degree); a pre-U pick (no course_id) → its /pathway page, keyed by the track/stream
        // (owner 2026-07-17). Falls back to null (plain text) only when neither exists.
        const courseHref = (cid?: string) => {
          // A third-route student names a degree too (the unfiltered degree list, D2) → /stpm.
          if (cid) return isStpm || third ? `/stpm/${cid}` : `/course/${cid}`
          if (app.chosen_pathway === 'stpm') return `/pathway/stpm${app.pre_u_track ? `?stream=${app.pre_u_track}` : ''}`
          if (app.chosen_pathway === 'matric') return `/pathway/matric${app.pre_u_track ? `?track=${app.pre_u_track}` : ''}`
          return null
        }
        const courseLink = (cid: string | undefined, name: string) => {
          const href = courseHref(cid)
          return href
            ? <a href={href} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center">{name}</a>
            : name
        }
        // Course start: the offer letter's report/registration date — surfaced in the Academic card
        // so the officer sees when the student must report. Prefer the offer that actually carries a
        // reporting date; fall back to the first offer.
        // LIVE offers only — a replaced (superseded) offer's reporting date must not show (owner
        // 2026-07-16): the value shown has to come from the same current offer the tick verifies, so
        // the two can never disagree. (The course-switch note below deliberately reads superseded
        // offers separately — that's history, not the current pathway.)
        const _offers = (app.documents || []).filter((d) => d.doc_type === 'offer_letter' && !d.superseded_at)
        const _offer = _offers.find((d) => d.pathway_check?.reporting_date) || _offers[0]
        // Show the STORED date, falling back to the letter's raw string. This surface used to
        // read ONLY the document — which is how #120 displayed a ticked "10 Jun 2025" while the
        // column driving his bursary was empty. The two must not be able to disagree again.
        // An officer-entered date therefore appears here too; it renders WITHOUT the verified
        // tick, because that tick means "Matches the offer letter" and is derived from document
        // corroboration (lib/fieldVerification), so a typed date never borrows it.
        const reportingDate = app.reporting_date
          ? formatDate(app.reporting_date)
          : (_offer?.pathway_check?.reporting_date || '')
        // Apply-stage context only (owner 2026-10-05, #134/#119): from "Awaiting review" onward the
        // pathways she weighed and why she was still deciding no longer describe the application.
        // The reasons also hide once the pathway is settled (e.g. a verified offer auto-confirmed
        // it) — they would contradict the now-shown chosen pathway/programme.
        const applyStage = isApplyStage(app.status)
        const showConsidered = applyStage && app.pathways_considered?.length > 0
        const showReasons = applyStage && app.pathway_certainty !== 'sure' && app.uncertainty_reasons?.length > 0
        const addr = formatAddress([
          app.address,
          [app.postal_code, app.city].filter(Boolean).join(' '),
          app.preferred_state,
        ])
        const guardian = (app.guardians && app.guardians[0]) || null
        // #5: name the relationship precisely. The minor-consent record carries the
        // real relationship; a non-parent guardian (legal_guardian/grandparent/sibling/
        // relative) → "Guardian", father/mother (or an adult self-consent) → "Parent".
        const activeConsent = (app.consents || []).find((c) => c.is_active) || null
        const isNonParentGuardian = activeConsent?.granted_by === 'guardian'
          && NON_PARENT_RELATIONSHIPS.has(activeConsent?.guardian_relationship || '')
        const personLabel = isNonParentGuardian
          ? t('admin.scholarship.guardianLabel')
          : t('admin.scholarship.parentLabel')
        // Request #45: the name line is the parent CONTACT, not the family — the student's own
        // family answers are listed below it (FamilyAnswers). The phone keeps "Parent phone".
        const contactLabel = isNonParentGuardian
          ? t('admin.scholarship.guardianContactLabel')
          : t('admin.scholarship.parentContactLabel')
        return (
          <div className="space-y-4">
            {/* Two independent columns rather than a row-major grid, so each column
                packs its cards top-down (masonry-style). Family floats up directly
                under the shorter About card instead of waiting for the taller
                Academic card opposite it. */}
            <div className="grid gap-4 md:grid-cols-2 md:items-start">
              {/* Left column — About, then Family */}
              <div className="space-y-4">
              {/* About — contact details (NRIC is in the header above) */}
              <Card title={t('admin.scholarship.sec.contact')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.phone')} value={app.contact_phone ? formatPhone(app.contact_phone) : null} />
                  {/* Email takes the old Call-language slot (call language hidden — owner 2026-07-15).
                      Verified email only: shown once the student verifies it, else the verified
                      Google login email. */}
                  <Field label={t('admin.scholarship.email')} value={app.verified_email
                    ? <a href={`mailto:${app.verified_email}`} className="text-primary-600 hover:underline max-md:min-h-11 max-md:min-w-11 max-md:inline-flex max-md:items-center max-md:justify-center max-md:max-w-full max-md:[overflow-wrap:anywhere]">{app.verified_email}</a>
                    : null} />
                  <div className="col-span-2"><Field label={t('admin.scholarship.address')} value={addr} verifiedLabel={vtip('address')} /></div>
                </dl>
              </Card>

              {/* Family & finances — moved up under About (was below Academic) */}
              <Card title={t('admin.scholarship.sec.family')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.income')} value={incomeValue} verifiedLabel={incomeTip} note={incomeNote} />
                  <Field label={t('admin.scholarship.householdSize')} value={sizeValue} verifiedLabel={sizeTip} note={sizeNote} noteTone={sizeNoteTone} />
                  <Field label="STR" value={yn(app.receives_str)} verifiedLabel={vtip('str')} />
                  <Field label={t('admin.scholarship.perCapita')} value={perCapita != null ? `RM ${Number(perCapita).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : null} />
                  <Field label={contactLabel} value={guardian?.name} verifiedLabel={vtip('parentName')} />
                  <Field label={t('admin.scholarship.guardianPhone', { role: personLabel })} value={<>
                    {guardian?.phone ? formatPhone(guardian.phone) : '—'}
                    {canCorrectGuardian && <GuardianCorrect appId={app.id} name={guardian?.name || ''} phone={guardian?.phone || ''} t={t} onDone={onGuardianCorrected} />}
                    {canCorrectGuardian && <GuardianCallRecord appId={app.id} phone={guardian?.phone || ''} t={t} onDone={onGuardianCorrected} />}
                  </>} note={app.guardian_needs_call ? t('admin.scholarship.call.needs') : undefined} />
                </dl>
                <FamilyAnswers app={app} t={t} />
              </Card>
              </div>

              {/* Right column — Academic (tall: grades + plans), then Support */}
              <div className="space-y-4">
              {/* Academic — school / merit / grades. Plans + notes are their own boxes below. */}
              <Card title={t('admin.scholarship.sec.academic')}>
                {/* ONE slot layout for every route (owner mock, 2026-11-24): the same rows in the same
                    order for SPM, STPM, Matriculation, Asasi and Diploma. A required slot with no
                    value says N/A in a muted colour, so an empty slot is never mistaken for a hidden one. */}
                <dl className="grid grid-cols-1 gap-x-4 gap-y-2.5 sm:grid-cols-2">
                  {/* Always in capitals, as the documents print it (owner, 2026-10-30) — the student
                      types it however she likes, and the case was being read as a difference. */}
                  <Field label={t('admin.scholarship.school')} value={app.school ? app.school.toUpperCase() : app.school} verifiedLabel={vtip('school')} na={na} />
                  {/* The merit score carries the exam that produced it and its YEAR on a grey line
                      under it (request #12, owner mock 2026-11-24). SPM: the slip's year. STPM: the
                      higher-results document's year. Matriculation / Asasi / Diploma: no year is read
                      yet, so the exam name alone. Only the year is tinted, and only when it is off the
                      expected sitting — the same tone the Documents drawer chip uses. */}
                  <Field label={t('admin.scholarship.meritScore')} na={na} value={app.merit_score}
                    noteTone="muted" note={(() => {
                      const examName = third ? t(`admin.scholarship.qualificationLabel.${third}`)
                        : t(`admin.scholarship.examName.${isStpm ? 'stpm' : 'spm'}`)
                      const ey = third ? null : isStpm ? higherExamYear(app.documents) : spmExamYear(app.documents)
                      return (
                        <>
                          {examName}
                          {ey && <>{' '}<span className={ey.status === 'off' ? 'text-caution-700' : undefined}>{ey.year}</span></>}
                        </>
                      )
                    })()} />
                  {/* Matriculation / Asasi / Diploma: where she did the pre-U course. An STPM student
                      has no such row — her STPM school IS her secondary school. */}
                  {third && <Field label={t('admin.scholarship.preUInstitution')} value={app.pre_u_institution} verifiedLabel={vtip('preUInstitution')} na={na} />}
                  {/* ONE CGPA slot (STPM: the PNGK with its STPM-results mark; the third route: the
                      CGPA entered, with its results tick) beside the MUET band. */}
                  {(isStpm || third) && <>
                    <Field label={t('admin.scholarship.cgpa')} na={na}
                      value={isStpm
                        ? (app.stpm_pngk == null ? app.stpm_pngk : <>{Number(app.stpm_pngk).toFixed(2)}{cgpaMark}</>)
                        : fmt2(app.higher_cgpa)}
                      verifiedLabel={isStpm ? undefined : vtip('higherCgpa')} />
                    <Field label="MUET" value={app.muet_band} na={na} />
                  </>}
                </dl>
                <div className="mt-3">
                  {/* SPM route: her SPM grades. Post-SPM routes: the SPM grades are her PREREQUISITES
                      (owner, 2026-11-16) and, for STPM, her STPM grades come first. */}
                  {isStpm && (
                    <div className="mb-2">
                      <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">{t('admin.scholarship.stpmGrades')}</dt>
                      <Grades grades={app.stpm_grades} na={na}
                        trailing={stpmAllMatch ? stpmMark({ status: 'match', doc: '' }) ?? undefined : undefined}
                        marks={gradeMarks} />
                    </div>
                  )}
                  <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">
                    {isStpm || third ? t('admin.scholarship.spmPrereq') : t('admin.scholarship.spmGrades')}
                  </dt>
                  {/* The tick renders AFTER the subject chips (item 1). The SPM slip's tick belongs to
                      SPM chips only — never to an STPM student's STPM grades (#132), which carry the
                      STPM results' own tick instead. The slip is checked against the SPM block
                      `spm_grades_for` returns, so a post-SPM student's SPM chips earn it too. Three
                      exclusive routes (owner 2026-11-06): a post-SPM student's SPM chips are her
                      SPM prereq ONLY - never her `grades` (an earlier SPM-page entry), never merged. */}
                  <Grades
                    grades={isStpm || third ? app.spm_prereq_grades : app.grades} na={na}
                    trailing={vtip('grades') ? <VerifiedTick label={vtip('grades')!} /> : undefined}
                  />
                  {/* Third results route S3b (D13, review fix 3): what the student changed in her
                      results before submitting — "SPM results only" or a slip moved to the SPM card;
                      S4 (D15): a higher result she moved OUT of the SPM card. Always recorded, so a
                      CGPA she was shortlisted on never vanishes silently. The team's own notes are
                      not served here (owner 2026-11-06, `results_route.cockpit_notes`). */}
                  {(app.results_change_notes || []).map((n, i) => {
                    const key = resultsChangeKey(n)
                    return key && (
                      <p key={i} data-testid="results-change-note" className="mt-2 rounded-lg bg-caution-50 px-3 py-2 text-xs text-caution-800 ring-1 ring-caution-200">
                        {t(key, {
                          date: (n.at || '').slice(0, 10),
                          cleared: t(`admin.scholarship.resultsChanged.kind.${n.cleared || 'other'}`),
                          kind: t(`admin.scholarship.resultsChanged.kind.${n.results_kind || 'other'}`),
                          cgpa: n.cgpa != null ? Number(n.cgpa).toFixed(2) : '—',
                        })}
                      </p>
                    )
                  })}
                </div>

                {/* Plans — chosen programme/pathway nested into Academic (no sub-label;
                    the divider sets it off). The free-text memos live in Student's note. */}
                <div className="mt-4 border-t border-ground-100 pt-3">
                    <dl className="grid grid-cols-1 gap-x-4 gap-y-2.5 sm:grid-cols-2">
                      {/* Unified across ALL pathways (owner 2026-07-17): Chosen Programme (linked to
                          its course / pathway page) · Institution · Reporting Date. Replaces the old
                          split (Chosen Pathway + Pre-U Track + Pre-U Institution for STPM/Matric vs
                          Chosen Programme for the rest). The pre-U track (Sains Sosial / Perakaunan)
                          folds inline after the programme so no info is lost. */}
                      {/* PISMP (a degree+specialisation pathway) reads INLINE exactly like STPM/Matric:
                          the constant degree + " · {bidang}" in the one Chosen Programme field
                          ("Ijazah Sarjana Muda Perguruan · Bahasa Tamil Pendidikan Rendah (SJKT)"),
                          echoing "Tingkatan Enam · Sains Sosial". The gray suffix is the pre-U track
                          for STPM/Matric, or the bidang for PISMP; other pathways keep course_name and
                          have no suffix. One inline format across all pathways — no separate row. */}
                      {(() => {
                        const cid = app.chosen_programme?.course_id as string | undefined
                        const disp = app.chosen_programme_display
                        const degreeSplit = !isInstitutionPathway && !!disp?.stream
                        const name = degreeSplit
                          ? (disp?.title || pathwayLabel(app.chosen_pathway))
                          : ((app.chosen_programme?.course_name as string) || pathwayLabel(app.chosen_pathway))
                        const suffix = isInstitutionPathway ? preUTrackLabel : (degreeSplit ? disp?.stream : null)
                        const tick = vtip('chosenProgramme')
                        return (
                          <Field
                            label={t('admin.scholarship.chosenProgramme')}
                            na={na}
                            value={name ? (
                              <>
                                {courseLink(cid, name)}
                                {suffix && <span className="text-ground-400"> · {suffix}</span>}
                              </>
                            ) : null}
                            verifiedLabel={tick}
                            noteTone="muted"
                            note={name && !tick ? t('admin.scholarship.statedByStudent') : undefined}
                          />
                        )
                      })()}
                      {/* The reporting date always shows: N/A when no date is stored or read. */}
                      <Field label={t('admin.scholarship.reportingDate')} value={reportingDate} na={na} verifiedLabel={vtip('reportingDate')} />
                      {/* Institution on its OWN row below (col-span-2); Chosen Programme + Reporting
                          Date share the top row (owner 2026-07-18). "Stated by student" only when the
                          value is HER OWN entry that no offer letter confirms - an institution copied
                          off the letter itself is not hers to state. */}
                      <div className="sm:col-span-2">
                        {(() => {
                          const tick = isInstitutionPathway ? vtip('preUInstitution') : vtip('institution')
                          const own = ((app.chosen_programme?.institution as string) || app.pre_u_institution || '').trim()
                          return (
                            <Field
                              label={t('admin.scholarship.institution')}
                              na={na}
                              value={expandMatricInstitution(shownInstitution(app)) || null}
                              verifiedLabel={tick}
                              noteTone="muted"
                              note={own && !tick ? t('admin.scholarship.statedByStudent') : undefined}
                            />
                          )
                        })()}
                      </div>
                    </dl>
                    {app.top_choices?.length > 0 && (
                      <div className="mt-3">
                        <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">{t('admin.scholarship.topChoices')}</dt>
                        <ol className="list-decimal ml-5 text-sm text-ground-800">
                          {app.top_choices.map((c) => <li key={c.rank}>{courseLink(c.course_id, c.course_name)}{c.institution ? ` — ${c.institution}` : ''}</li>)}
                        </ol>
                      </div>
                    )}
                    {showConsidered && <div className="mt-2"><Field label={t('admin.scholarship.pathwaysConsidered')} value={joinOr(app.pathways_considered)} /></div>}
                    {showReasons && <div className="mt-2"><Field label={t('admin.scholarship.uncertaintyReasons')} value={joinOr(app.uncertainty_reasons)} /></div>}
                  </div>
              </Card>

              {/* Support required — help only. Consent-to-contact is omitted: it's a
                  hard requirement to submit, so it's always "Yes" and adds no signal. */}
              <Card title={t('admin.scholarship.sec.support')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.helpUniversity')} value={helpLabel(app.help_university)} />
                  <Field label={t('admin.scholarship.helpScholarship')} value={helpLabel(app.help_scholarship)} />
                </dl>
              </Card>
              </div>
            </div>

            {/* Student's note · Your story · Funding moved into the left column,
                under the Sponsor profile (the "show the student's own words" reveal). */}

            {/* Estimated need relocated to the right column, beside Decision (award sizing). */}
          </div>
        )
      })()}

  </>)
}
