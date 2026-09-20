'use client'

/**
 * THE SYSTEM-GENERATED STUDENT PROFILE (draft at handoff, final at the verdict) and, folded
 * under it, THE STUDENT'S OWN WORDS — the note, the story and the funding need the reviewer
 * reveals on demand.
 *
 * ⚠ Lifted out of `view.tsx` whole at code health H14. Every line below is the line it was.
 */
import type { Dispatch, SetStateAction } from 'react'
import { showsGeneratedProfileCard } from '@/lib/officerCockpit'
import type { AdminScholarshipDetail, AdminSponsorProfile } from '@/lib/admin-api'

import { Field, joinOr, yn, type T } from './shared'

export function GeneratedProfile({
  app, t, profile, genLang, setGenLang, busy, error, decisionReopened,
  showOwnWords, setShowOwnWords,
}: {
  app: AdminScholarshipDetail
  t: T
  profile: AdminSponsorProfile | null
  genLang: string
  setGenLang: Dispatch<SetStateAction<string>>
  busy: string
  error: string
  decisionReopened: boolean
  showOwnWords: boolean
  setShowOwnWords: Dispatch<SetStateAction<boolean>>
}) {
  return (<>

      {/* ── Student profile (system-generated: draft at handoff → final at verdict) ── */}
      {/* Hidden at shortlisted (pre-submission): only generated at the verdict.
          Hidden on a CLOSED case holding no profile: empty, every line of this card describes a
          future that cannot happen, and its language selector feeds a call that is now refused. */}
      {showsGeneratedProfileCard({
        status: app.status,
        decisionReopened,
        hasProfile: !!(profile?.final_markdown || profile?.current_markdown),
      }) && (
      <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold tracking-tight text-ground-900">
            {t(profile?.final_markdown ? 'admin.scholarship.profileFinalTitle' : 'admin.scholarship.profileTitle')}
          </h2>
          <div className="flex items-center gap-2">
            <label className="text-xs text-ground-500">{t('admin.scholarship.genLang')}</label>
            <select value={genLang} onChange={(e) => setGenLang(e.target.value)} disabled={!!busy}
              className="border rounded-lg px-2 py-1 text-sm">
              <option value="en">English</option>
              <option value="ms">Bahasa Melayu</option>
            </select>
          </div>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-primary-100 bg-primary-50 p-2 text-xs text-primary-800">
          <span aria-hidden>ⓘ</span>
          <span>{t(profile?.final_markdown ? 'admin.scholarship.profileFinalHint' : 'admin.scholarship.profileDraftHint')}</span>
        </div>

        {!profile || !(profile.final_markdown || profile.current_markdown) ? (
          <p className="text-sm text-ground-400">{t('admin.scholarship.profilePending')}</p>
        ) : (
          <>
            <div className="whitespace-pre-wrap text-sm leading-relaxed text-ground-800">
              {profile.final_markdown || profile.current_markdown}
            </div>
            <p className="text-xs text-ground-400">
              {profile.final_markdown
                ? `${t('admin.scholarship.finalProfile.title')} · ${profile.final_model_used || '—'}`
                : `${t('admin.scholarship.model')}: ${profile.model_used || '—'}`}
            </p>
          </>
        )}
        {error && <p className="text-critical-600 text-sm">{error}</p>}
      </div>
      )}

      {/* ── The student's own words — collapsed by default. The reviewer's job is to
           check & sign off the AI profile above; the raw note/story/funding is the
           safety valve, revealed on demand. ──────────────────────────────────────── */}
      {(() => {
        const hasStory = !!(app.aspirations || app.plans || app.fears || app.justification
          || app.daily_life || app.first_in_family || app.parents_occupation
          || app.siblings_studying_count || app.siblings_in_school || app.siblings_in_tertiary
          || app.family_context)
        // #6: the legacy single "siblings studying" count is superseded by the
        // school/tertiary split. Show it ONLY as a fallback for old rows that have a
        // positive legacy count but no split yet (migration 0044 left those null) —
        // captioned so the officer knows to confirm the breakdown at interview.
        const showLegacySiblings = app.siblings_in_school == null
          && app.siblings_in_tertiary == null
          && (app.siblings_studying_count ?? 0) > 0
        if (!(app.uncertainty_note || app.anything_else || hasStory || app.funding_need)) return null
        return (
        <div className="space-y-4">
          <button
            onClick={() => setShowOwnWords((v) => !v)}
            className="flex items-center gap-1.5 text-sm text-primary-600 hover:underline"
          >
            <span aria-hidden>{showOwnWords ? '▾' : '▸'}</span>
            {t(showOwnWords ? 'admin.scholarship.ownWords.hide' : 'admin.scholarship.ownWords.toggle')}
          </button>
          {showOwnWords && (
            /* One box, three labelled sections (note · story · funding), split by hairlines. */
            <div className="rounded-2xl border border-ground-200 bg-ground-0 p-5 shadow-sm divide-y divide-ground-100">
              {/* Student's note — both free-text memos, each question labelled. */}
              {(app.uncertainty_note || app.anything_else) && (
                <div className="py-4 first:pt-0 last:pb-0">
                  <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-400">{t('admin.scholarship.studentNote')}</h3>
                  <div className="space-y-3">
                    {app.uncertainty_note && (
                      <div>
                        <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">{t('scholarship.apply.plan.uncertainNoteLabel')}</dt>
                        <p className="text-sm text-ground-800 whitespace-pre-wrap">{app.uncertainty_note}</p>
                      </div>
                    )}
                    {app.anything_else && (
                      <div>
                        <dt className="text-xs text-ground-400 uppercase tracking-wider mb-1">{t('scholarship.apply.anythingElseLabel')}</dt>
                        <p className="text-sm text-ground-800 whitespace-pre-wrap">{app.anything_else}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Student's Story — post-shortlist; hidden until the student fills it */}
              {hasStory && (
                <div className="py-4 first:pt-0 last:pb-0">
                  <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-400">{t('admin.scholarship.sec.story')}</h3>
                  <div className="space-y-2">
                    <Field label={t('admin.scholarship.aspirations')} value={app.aspirations} />
                    <Field label={t('admin.scholarship.plans')} value={app.plans} />
                    <Field label={t('admin.scholarship.fears')} value={app.fears} />
                    <Field label={t('admin.scholarship.dailyLife')} value={app.daily_life} />
                    <Field label={t('admin.scholarship.justification')} value={app.justification} />
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 pt-1 md:grid-cols-3">
                      <Field label={t('admin.scholarship.firstInFamily')} value={yn(app.first_in_family)} />
                      <Field label={t('admin.scholarship.parentsOccupation')} value={app.parents_occupation} />
                      <Field label={t('admin.scholarship.siblingsInSchool')} value={app.siblings_in_school} />
                      <Field label={t('admin.scholarship.siblingsInTertiary')} value={app.siblings_in_tertiary} />
                      {showLegacySiblings && (
                        <Field label={t('admin.scholarship.siblingsStudying')} value={`${app.siblings_studying_count} — ${t('admin.scholarship.siblingsLegacyNote')}`} />
                      )}
                    </dl>
                    <Field label={t('admin.scholarship.familyContext')} value={app.family_context} />
                  </div>
                </div>
              )}

              {/* Funding — hidden when empty */}
              {app.funding_need && (
                <div className="py-4 first:pt-0 last:pb-0">
                  <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ground-400">{t('admin.scholarship.sec.funding')}</h3>
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 md:grid-cols-3">
                    <Field label={t('admin.scholarship.funding')} value={joinOr(app.funding_need.categories)} />
                    <Field label={t('admin.scholarship.programmeMonths')} value={app.funding_need.programme_months} />
                  </dl>
                  {app.funding_need.funding_note && <div className="mt-2"><Field label={t('admin.scholarship.fundingNote')} value={app.funding_need.funding_note} /></div>}
                </div>
              )}
            </div>
          )}
        </div>
        )
      })()}

  </>)
}
