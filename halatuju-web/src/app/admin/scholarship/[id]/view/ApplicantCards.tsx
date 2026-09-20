'use client'

/**
 * THE APPLICANT SUMMARY — About, Family & finances, Academic (with Plans folded in) and Support,
 * in two masonry columns.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was; the
 * document-verified income and household-size readings are still computed in the cockpit and
 * arrive here as props, because the header uses them too.
 */
import VerifiedTick from '@/components/VerifiedTick'
import {
  formatPhone,
  formatAddress,
  expandMatricInstitution,
} from '@/lib/scholarship'
import { spmExamYear } from '@/lib/officerCockpit'
import { formatDate } from '@/lib/formatDate'
import type { AdminScholarshipDetail } from '@/lib/admin-api'

import { Card, Field, Grades, joinOr, yn, NON_PARENT_RELATIONSHIPS, type T, type Vtip } from './shared'

export function ApplicantCards({
  app, t, vtip, incomeValue, incomeTip, incomeNote,
  sizeValue, sizeTip, sizeNote, sizeNoteTone, perCapita,
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
}) {
  return (<>

      {/* Applicant info — three explicit columns (About+Family / Academic / Support…) */}
      {(() => {
        const isStpm = app.qualification === 'stpm'
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
        const preUTrackLabel = app.pre_u_track_label
        // Help answers: render the apply-form's own words (Yes / No / Not sure) rather
        // than the raw 'yes'/'no'/'unsure' codes.
        const helpLabel = (v?: string | null) => (v ? t(`scholarship.apply.help.${v}`) : null)
        // Link a course back to its HalaTuju public page (opens in a new tab so
        // the admin doesn't lose the application). STPM degrees live under /stpm.
        // Every genuine programme has a page: a catalogue course_id → /course (or /stpm for an
        // STPM degree); a pre-U pick (no course_id) → its /pathway page, keyed by the track/stream
        // (owner 2026-07-17). Falls back to null (plain text) only when neither exists.
        const courseHref = (cid?: string) => {
          if (cid) return isStpm ? `/stpm/${cid}` : `/course/${cid}`
          if (app.chosen_pathway === 'stpm') return `/pathway/stpm${app.pre_u_track ? `?stream=${app.pre_u_track}` : ''}`
          if (app.chosen_pathway === 'matric') return `/pathway/matric${app.pre_u_track ? `?track=${app.pre_u_track}` : ''}`
          return null
        }
        const courseLink = (cid: string | undefined, name: string) => {
          const href = courseHref(cid)
          return href
            ? <a href={href} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">{name}</a>
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
        const hasPlans = !!(app.chosen_pathway || app.chosen_programme?.course_name || reportingDate
          || app.top_choices?.length || app.pathways_considered?.length || app.uncertainty_reasons?.length)
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
                    ? <a href={`mailto:${app.verified_email}`} className="text-primary-600 hover:underline">{app.verified_email}</a>
                    : null} />
                  <div className="col-span-2"><Field label={t('admin.scholarship.address')} value={addr} verifiedLabel={vtip('address')} /></div>
                </dl>
              </Card>

              {/* Family & finances — moved up under About (was below Academic) */}
              <Card title={t('admin.scholarship.sec.family')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.income')} value={incomeValue} verifiedLabel={incomeTip} note={incomeNote} noteTone="muted" />
                  <Field label={t('admin.scholarship.householdSize')} value={sizeValue} verifiedLabel={sizeTip} note={sizeNote} noteTone={sizeNoteTone} />
                  <Field label="STR" value={yn(app.receives_str)} verifiedLabel={vtip('str')} />
                  <Field label={t('admin.scholarship.perCapita')} value={perCapita != null ? `RM ${Number(perCapita).toLocaleString('en-US', { maximumFractionDigits: 0 })}` : null} />
                  <Field label={personLabel} value={guardian?.name} verifiedLabel={vtip('parentName')} />
                  <Field label={t('admin.scholarship.guardianPhone', { role: personLabel })} value={guardian?.phone ? formatPhone(guardian.phone) : null} />
                </dl>
              </Card>
              </div>

              {/* Right column — Academic (tall: grades + plans), then Support */}
              <div className="space-y-4">
              {/* Academic — school / merit / grades. Plans + notes are their own boxes below. */}
              <Card title={t('admin.scholarship.sec.academic')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.school')} value={app.school} verifiedLabel={vtip('school')} />
                  {/* The merit score carries the YEAR of the SPM that produced it (request #12).
                      Always shown when we can read it, never only on the odd ones: a qualifier that
                      appears solely when something is unusual reads as an alarm, and a reviewer
                      never learns what the ordinary case looks like. Only the year is tinted, and
                      only when it is off the expected sitting — the same tone the Documents drawer
                      chip uses, so the two surfaces cannot disagree. NOT attached for an STPM
                      student: that merit comes from STPM, so an SPM year would misstate its source. */}
                  <Field label={t('admin.scholarship.meritScore')} value={(() => {
                    if (app.merit_score == null) return app.merit_score
                    const sy = isStpm ? null : spmExamYear(app.documents)
                    if (!sy) return app.merit_score
                    return (
                      <>
                        {app.merit_score}{' '}
                        <span className={sy.status === 'off' ? 'text-caution-700' : 'text-ground-500'}>
                          ({t('admin.scholarship.docsDrawer.examYear', { year: sy.year })})
                        </span>
                      </>
                    )
                  })()} />
                  {isStpm && <Field label="MUET" value={app.muet_band} />}
                </dl>
                <div className="mt-3">
                  <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">
                    {isStpm ? t('admin.scholarship.stpmGrades') : t('admin.scholarship.spmGrades')}
                  </dt>
                  {/* The tick renders AFTER the subject chips (item 1). It verifies the SPM slip
                      against the SPM `grades`, so it only belongs to an SPM student's grades — an
                      STPM student's STPM grades are NOT what academic_check verifies (it would sit
                      on a match against the separate SPM slip → misattribution, #132). */}
                  <Grades
                    grades={isStpm ? app.stpm_grades : app.grades}
                    trailing={!isStpm && vtip('grades') ? <VerifiedTick label={vtip('grades')!} /> : undefined}
                  />
                  {isStpm && Object.keys(app.spm_prereq_grades || {}).length > 0 && (
                    <div className="mt-2">
                      <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">{t('admin.scholarship.spmPrereq')}</dt>
                      <Grades grades={app.spm_prereq_grades} />
                    </div>
                  )}
                </div>

                {/* Plans — chosen programme/pathway nested into Academic (no sub-label;
                    the divider sets it off). The free-text memos live in Student's note. */}
                {hasPlans && (
                  <div className="mt-4 border-t border-ground-100 pt-3">
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                      {/* Unified across ALL pathways (owner 2026-07-17): Chosen Programme (linked to
                          its course / pathway page) · Institution · Reporting Date. Replaces the old
                          split (Chosen Pathway + Pre-U Track + Pre-U Institution for STPM/Matric vs
                          Chosen Programme for the rest). The pre-U track (Sains Sosial / Perakaunan)
                          folds inline after the programme so no info is lost. */}
                      {/* PISMP (a degree+specialisation pathway) reads INLINE exactly like STPM/Matric:
                          the constant degree + " · {bidang}" in the one Chosen Programme field
                          ("Ijazah Sarjana Muda Perguruan · Bahasa Tamil Pendidikan Rendah (SJKT)"),
                          mirroring "Tingkatan Enam · Sains Sosial". The gray suffix is the pre-U track
                          for STPM/Matric, or the bidang for PISMP; other pathways keep course_name and
                          have no suffix. One inline format across all pathways — no separate row. */}
                      {(() => {
                        const cid = app.chosen_programme?.course_id as string | undefined
                        const disp = app.chosen_programme_display
                        const degreeSplit = !isInstitutionPathway && !!disp?.stream
                        const name = degreeSplit
                          ? (disp?.title || pathwayLabel(app.chosen_pathway))
                          : ((app.chosen_programme?.course_name as string) || pathwayLabel(app.chosen_pathway))
                        if (!name) return null
                        const suffix = isInstitutionPathway ? preUTrackLabel : (degreeSplit ? disp?.stream : null)
                        return (
                          <Field
                            label={t('admin.scholarship.chosenProgramme')}
                            value={
                              <>
                                {courseLink(cid, name)}
                                {suffix && <span className="text-ground-400"> · {suffix}</span>}
                              </>
                            }
                            verifiedLabel={vtip('chosenProgramme')}
                          />
                        )
                      })()}
                      {reportingDate && <Field label={t('admin.scholarship.reportingDate')} value={reportingDate} verifiedLabel={vtip('reportingDate')} />}
                      {/* Institution on its OWN row below (col-span-2); Chosen Programme + Reporting
                          Date share the top row (owner 2026-07-18). */}
                      <div className="col-span-2">
                        <Field
                          label={t('admin.scholarship.institution')}
                          value={expandMatricInstitution((app.chosen_programme?.institution as string) || app.pre_u_institution || '') || null}
                          verifiedLabel={isInstitutionPathway ? vtip('preUInstitution') : vtip('institution')}
                        />
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
                    {app.pathways_considered?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.pathwaysConsidered')} value={joinOr(app.pathways_considered)} /></div>}
                    {/* "Still deciding" reasons are hidden once the pathway is settled
                        (e.g. a verified offer letter auto-confirmed it) — they'd contradict
                        the now-shown chosen pathway/programme. */}
                    {app.pathway_certainty !== 'sure' && app.uncertainty_reasons?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.uncertaintyReasons')} value={joinOr(app.uncertainty_reasons)} /></div>}
                  </div>
                )}
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
