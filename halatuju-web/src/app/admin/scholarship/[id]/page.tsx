'use client'

import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { formatPhone, formatAddress } from '@/lib/scholarship'
import {
  getScholarshipApplication,
  generateSponsorProfile,
  finaliseSponsorProfile,
  suggestInterviewGaps,
  saveSponsorProfile,
  publishSponsorProfile,
  verifyAcceptApplication,
  setMentoringCandidate,
  addReferee,
  deleteReferee,
  reRunVision,
  assignApplication,
  getInterview,
  saveInterview,
  submitInterview,
  requestMoreInfo,
  getAssignableAdmins,
  type AdminScholarshipDetail,
  type AdminSponsorProfile,
  type AdminApplicantDocument,
  type AdminInterviewSession,
} from '@/lib/admin-api'

const VERDICTS = ['resolved', 'still_unclear', 'new_concern'] as const
const RUBRIC_DIMS = ['clarity_of_plan', 'financial_need', 'resilience'] as const
const COMPLETENESS_PARTS = ['quiz_done', 'details_done', 'funding_done', 'documents_done', 'consent_done', 'address_done', 'guardian_docs_done'] as const

const EMPTY_REFEREE = { name: '', role: '', relationship: '', phone: '', email: '' }

const VERIFY_ITEMS = ['nric', 'name', 'results', 'document'] as const

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-gray-400 uppercase tracking-wider">{label}</dt>
      <dd className="text-sm text-gray-800 break-words">{value === null || value === undefined || value === '' ? '—' : value}</dd>
    </div>
  )
}

function Card({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-gray-200 bg-white p-4 shadow-sm ${className}`}>
      <h2 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400">{title}</h2>
      {children}
    </div>
  )
}

/** Section heading for a group of panels (e.g. "Review & actions"). */
function GroupLabel({ children }: { children: ReactNode }) {
  return <h2 className="mb-2 mt-2 text-xs font-semibold uppercase tracking-wider text-gray-500">{children}</h2>
}

const yn = (v: boolean | null | undefined) => (v === true ? 'Yes' : v === false ? 'No' : '—')
const joinOr = (a?: string[] | null) => (a && a.length ? a.join(', ') : '—')

/** Grade dict → readable chips (subject key uppercased · grade). */
function Grades({ grades }: { grades?: Record<string, string> | null }) {
  const entries = Object.entries(grades || {}).filter(([, g]) => g)
  if (!entries.length) return <span className="text-gray-400 text-sm">—</span>
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, g]) => (
        <span key={k} className="inline-flex items-center gap-1 rounded-md bg-gray-100 px-2 py-0.5 text-xs">
          <span className="text-gray-500 uppercase">{k.replace(/_/g, ' ')}</span>
          <span className="font-semibold text-gray-800">{g}</span>
        </span>
      ))}
    </div>
  )
}

export default function AdminScholarshipDetailPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const canWrite = (role?.role ?? (role?.is_super_admin ? 'super' : 'reviewer')) !== 'viewer'
  const [app, setApp] = useState<AdminScholarshipDetail | null>(null)
  const [profile, setProfile] = useState<AdminSponsorProfile | null>(null)
  const [markdown, setMarkdown] = useState('')
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [checklist, setChecklist] = useState<Record<string, boolean>>({})
  const [refForm, setRefForm] = useState({ ...EMPTY_REFEREE })
  const [genLang, setGenLang] = useState('en')
  // Phase C
  const [admins, setAdmins] = useState<Array<{ id: number; name: string }>>([])
  const [findings, setFindings] = useState<Record<string, { verdict: string; rationale: string }>>({})
  const [rubric, setRubric] = useState<Record<string, number>>({})
  const [note, setNote] = useState('')
  const [infoNote, setInfoNote] = useState('')

  const loadInterviewState = (d: AdminScholarshipDetail) => {
    const s = d.interview_session
    setFindings(s?.findings ?? {})
    setRubric(s?.rubric ?? {})
    setNote(s?.overall_note ?? '')
  }

  useEffect(() => {
    if (!token || !id) return
    getScholarshipApplication(id, { token })
      .then((d) => {
        setApp(d)
        setProfile(d.sponsor_profile)
        setMarkdown(d.sponsor_profile?.current_markdown || '')
        loadInterviewState(d)
      })
      .catch(() => setError(t('admin.scholarship.loadFailed')))
    getAssignableAdmins({ token }).then((r) => setAdmins(r.admins)).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, id])

  const doGenerate = async () => {
    if (!token) return
    setBusy('gen'); setError('')
    try {
      const p = await generateSponsorProfile(id, genLang, { token })
      setProfile(p); setMarkdown(p.current_markdown || p.draft_markdown)
    } catch { setError(t('admin.scholarship.genError')) } finally { setBusy('') }
  }

  const doSuggestGaps = async () => {
    if (!token) return
    setBusy('gaps'); setError('')
    try {
      setApp(await suggestInterviewGaps(id, undefined, { token }))
    } catch { setError(t('admin.scholarship.gaps.error')) } finally { setBusy('') }
  }

  const doFinalise = async () => {
    if (!token) return
    setBusy('final'); setError('')
    try {
      setProfile(await finaliseSponsorProfile(id, genLang, { token }))
    } catch { setError(t('admin.scholarship.finalProfile.error')) } finally { setBusy('') }
  }

  const doSave = async () => {
    if (!token) return
    setBusy('save'); setError('')
    try {
      const p = await saveSponsorProfile(id, { edited_markdown: markdown, status: 'approved' }, { token })
      setProfile(p)
    } catch { setError(t('admin.scholarship.saveError')) } finally { setBusy('') }
  }

  const doPublish = async () => {
    if (!token) return
    setBusy('pub'); setError('')
    try {
      const p = await publishSponsorProfile(id, { token })
      setProfile(p)
    } catch { setError(t('admin.scholarship.publishError')) } finally { setBusy('') }
  }

  const doVerifyAccept = async () => {
    if (!token) return
    setBusy('verify'); setError('')
    try {
      setApp(await verifyAcceptApplication(id, checklist, { token }))
    } catch (e) {
      setError(e instanceof Error ? e.message : t('admin.scholarship.acceptError'))
    } finally { setBusy('') }
  }

  const doAssign = async (adminId: number | null) => {
    if (!token) return
    setBusy('assign'); setError('')
    try { setApp(await assignApplication(id, adminId, { token })) }
    catch { setError(t('admin.scholarship.assignError')) } finally { setBusy('') }
  }

  const doSaveInterview = async () => {
    if (!token) return
    setBusy('iv'); setError('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.interview.saveError')) } finally { setBusy('') }
  }

  const doSubmitInterview = async () => {
    if (!token) return
    setBusy('ivs'); setError('')
    try {
      await saveInterview(id, { findings, rubric, overall_note: note }, { token })
      const d = await submitInterview(id, { token })
      setApp(d); loadInterviewState(d)
    } catch { setError(t('admin.scholarship.interview.submitError')) } finally { setBusy('') }
  }

  const doRequestInfo = async () => {
    if (!token || !infoNote.trim()) return
    setBusy('info'); setError('')
    try {
      setApp(await requestMoreInfo(id, infoNote.trim(), { token }))
      setInfoNote('')
    } catch { setError(t('admin.scholarship.requestInfoError')) } finally { setBusy('') }
  }

  const toggleMentoring = async (value: boolean) => {
    if (!token) return
    setBusy('mentor'); setError('')
    try {
      setApp(await setMentoringCandidate(id, value, { token }))
    } catch { setError(t('admin.scholarship.mentorError')) } finally { setBusy('') }
  }

  const refreshApp = async () => {
    if (!token) return
    setApp(await getScholarshipApplication(id, { token }))
  }

  const doAddReferee = async () => {
    if (!token || !refForm.name.trim()) return
    setBusy('ref'); setError('')
    try {
      await addReferee(id, refForm, { token })
      setRefForm({ ...EMPTY_REFEREE })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doDeleteReferee = async (refId: number) => {
    if (!token) return
    setBusy('ref'); setError('')
    try {
      await deleteReferee(id, refId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.refError')) } finally { setBusy('') }
  }

  const doReRunVision = async (docId: number) => {
    if (!token) return
    setBusy('vision'); setError('')
    try {
      await reRunVision(id, docId, { token })
      await refreshApp()
    } catch { setError(t('admin.scholarship.visionError')) } finally { setBusy('') }
  }

  if (error && !app) return <div className="text-red-600 mt-8">{error}</div>
  if (!app) return <div className="text-center text-gray-500 mt-8">{t('common.loading')}</div>

  return (
    <div className="mx-auto max-w-6xl space-y-4 pb-10">
      {/* Header — applicant identity, status, and key facts at a glance */}
      <header className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <Link href="/admin/scholarship" className="text-xs text-gray-400 hover:text-gray-600">‹ {t('admin.scholarship.back')}</Link>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-2">
          <h1 className="text-xl font-bold tracking-tight text-gray-900 sm:text-2xl">{app.name || '—'}</h1>
          <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-semibold text-blue-700">{app.status}</span>
          {app.bucket && (
            <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-amber-100 px-1.5 text-xs font-bold text-amber-700">{app.bucket}</span>
          )}
          {app.qualification && (
            <span className="rounded-full border border-gray-200 px-2 py-0.5 text-xs font-medium text-gray-500">{app.qualification.toUpperCase()}</span>
          )}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500">
          <span>NRIC <span className="font-mono text-gray-700">{app.nric || '—'}</span></span>
          {app.merit_score != null && (
            <span>{t('admin.scholarship.meritScore')} <span className="font-semibold text-gray-800">{app.merit_score}</span></span>
          )}
          {app.submitted_at && (
            <span>{t('admin.scholarship.submitted')} {new Date(app.submitted_at).toLocaleDateString()}</span>
          )}
          <span>{t('admin.scholarship.assigned')} <span className="text-gray-700">{app.assigned_to_name || '—'}</span></span>
        </div>
      </header>

      {/* Applicant info — three explicit columns (About+Family / Academic / Support…) */}
      {(() => {
        const isStpm = app.qualification === 'stpm'
        // Pathway context: matric/stpm are INSTITUTION pathways (track + school);
        // everything else (asasi, university, poly, pismp…) is a PROGRAMME pathway
        // (a chosen course), so Pre-U track doesn't apply.
        const isInstitutionPathway = app.chosen_pathway === 'matric' || app.chosen_pathway === 'stpm'
        // Human labels for the stored codes — reuse the apply-form's own i18n maps so
        // the admin sees the same words the student did (matric→Matriculation, etc.).
        const callLangLabel = app.preferred_call_language ? t(`scholarship.apply.callLang.${app.preferred_call_language}`) : null
        const pathwayLabel = (code?: string | null) => (code ? t(`scholarship.apply.plan.pathway.${code}`) : null)
        // pre_u_track holds a matric TRACK (sains/kejuruteraan…) for matric, or an STPM
        // STREAM (sains/sains_sosial/not_sure) for STPM — both under scholarship.apply.plan.
        const preUTrackLabel = app.pre_u_track
          ? t(`scholarship.apply.plan.${app.chosen_pathway === 'stpm' ? 'stream' : 'track'}.${app.pre_u_track}`)
          : null
        // Help answers: render the apply-form's own words (Yes / No / Not sure) rather
        // than the raw 'yes'/'no'/'unsure' codes.
        const helpLabel = (v?: string | null) => (v ? t(`scholarship.apply.help.${v}`) : null)
        // Link a course back to its HalaTuju public page (opens in a new tab so
        // the admin doesn't lose the application). STPM degrees live under /stpm.
        const courseHref = (cid?: string) => (cid ? (isStpm ? `/stpm/${cid}` : `/course/${cid}`) : null)
        const courseLink = (cid: string | undefined, name: string) => {
          const href = courseHref(cid)
          return href
            ? <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{name}</a>
            : name
        }
        const hasStory = !!(app.aspirations || app.plans || app.fears || app.justification
          || app.daily_life || app.first_in_family || app.parents_occupation
          || app.siblings_studying_count || app.family_context)
        const hasPlans = !!(app.chosen_pathway || app.chosen_programme?.course_name
          || app.top_choices?.length || app.pathways_considered?.length || app.uncertainty_reasons?.length)
        const addr = formatAddress([
          app.address,
          [app.postal_code, app.city].filter(Boolean).join(' '),
          app.preferred_state,
        ])
        const guardian = (app.guardians && app.guardians[0]) || null
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
                  <Field label={t('admin.scholarship.callLanguage')} value={callLangLabel} />
                  {/* Verified email only — shown once the student verifies it, else the
                      verified Google login email. Full-width rows. */}
                  <div className="col-span-2"><Field label={t('admin.scholarship.email')} value={app.verified_email
                    ? <a href={`mailto:${app.verified_email}`} className="text-blue-600 hover:underline">{app.verified_email}</a>
                    : null} /></div>
                  <div className="col-span-2"><Field label={t('admin.scholarship.address')} value={addr} /></div>
                </dl>
              </Card>

              {/* Family & finances — moved up under About (was below Academic) */}
              <Card title={t('admin.scholarship.sec.family')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.income')} value={app.household_income ? `RM ${Number(app.household_income).toLocaleString('en-US')}` : null} />
                  <Field label={t('admin.scholarship.householdSize')} value={app.household_size} />
                  <Field label="STR" value={yn(app.receives_str)} />
                  <Field label="JKM" value={yn(app.receives_jkm)} />
                  <Field label={t('admin.scholarship.guardianName')} value={guardian?.name} />
                  <Field label={t('admin.scholarship.guardianPhone')} value={guardian?.phone ? formatPhone(guardian.phone) : null} />
                </dl>
              </Card>
              </div>

              {/* Right column — Academic (tall: grades + plans), then Support */}
              <div className="space-y-4">
              {/* Academic — school / merit / grades. Plans + notes are their own boxes below. */}
              <Card title={t('admin.scholarship.sec.academic')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                  <Field label={t('admin.scholarship.school')} value={app.school} />
                  <Field label={t('admin.scholarship.meritScore')} value={app.merit_score} />
                  {isStpm && <Field label="MUET" value={app.muet_band} />}
                </dl>
                <div className="mt-3">
                  <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">
                    {isStpm ? t('admin.scholarship.stpmGrades') : t('admin.scholarship.spmGrades')}
                  </dt>
                  <Grades grades={isStpm ? app.stpm_grades : app.grades} />
                  {isStpm && Object.keys(app.spm_prereq_grades || {}).length > 0 && (
                    <div className="mt-2">
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('admin.scholarship.spmPrereq')}</dt>
                      <Grades grades={app.spm_prereq_grades} />
                    </div>
                  )}
                </div>

                {/* Plans — chosen programme/pathway nested into Academic (no sub-label;
                    the divider sets it off). The free-text memos live in Student's note. */}
                {hasPlans && (
                  <div className="mt-4 border-t border-gray-100 pt-3">
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
                      {isInstitutionPathway ? (
                        <>
                          <Field label={t('admin.scholarship.chosenPathway')} value={pathwayLabel(app.chosen_pathway)} />
                          <Field label={t('admin.scholarship.preUTrack')} value={preUTrackLabel} />
                          <Field label={t('admin.scholarship.preUInstitution')} value={app.pre_u_institution} />
                        </>
                      ) : (
                        <Field
                          label={t('admin.scholarship.chosenProgramme')}
                          value={app.chosen_programme?.course_name
                            ? courseLink(app.chosen_programme.course_id as string | undefined, app.chosen_programme.course_name as string)
                            : pathwayLabel(app.chosen_pathway)}
                        />
                      )}
                    </dl>
                    {app.top_choices?.length > 0 && (
                      <div className="mt-3">
                        <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('admin.scholarship.topChoices')}</dt>
                        <ol className="list-decimal ml-5 text-sm text-gray-800">
                          {app.top_choices.map((c) => <li key={c.rank}>{courseLink(c.course_id, c.course_name)}{c.institution ? ` — ${c.institution}` : ''}</li>)}
                        </ol>
                      </div>
                    )}
                    {app.pathways_considered?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.pathwaysConsidered')} value={joinOr(app.pathways_considered)} /></div>}
                    {app.uncertainty_reasons?.length > 0 && <div className="mt-2"><Field label={t('admin.scholarship.uncertaintyReasons')} value={joinOr(app.uncertainty_reasons)} /></div>}
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

            {/* Student's note — both free-text memos in one box, each question labelled.
                "Anything you'd like to add?" (uncertainty_note, from Plans) +
                "Anything else you'd like us to know?" (anything_else, from Support).
                Hidden when the student wrote neither. */}
            {(app.uncertainty_note || app.anything_else) && (
              <Card title={t('admin.scholarship.studentNote')}>
                <div className="space-y-3">
                  {app.uncertainty_note && (
                    <div>
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('scholarship.apply.plan.uncertainNoteLabel')}</dt>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{app.uncertainty_note}</p>
                    </div>
                  )}
                  {app.anything_else && (
                    <div>
                      <dt className="text-xs text-gray-400 uppercase tracking-wider mb-1">{t('scholarship.apply.anythingElseLabel')}</dt>
                      <p className="text-sm text-gray-800 whitespace-pre-wrap">{app.anything_else}</p>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* Your story — full-width, post-shortlist; hidden until the student fills it */}
            {hasStory && (
              <Card title={t('admin.scholarship.sec.story')}>
                <div className="space-y-2">
                  <Field label={t('admin.scholarship.aspirations')} value={app.aspirations} />
                  <Field label={t('admin.scholarship.plans')} value={app.plans} />
                  <Field label={t('admin.scholarship.fears')} value={app.fears} />
                  <Field label={t('admin.scholarship.dailyLife')} value={app.daily_life} />
                  <Field label={t('admin.scholarship.justification')} value={app.justification} />
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 pt-1 md:grid-cols-3">
                    <Field label={t('admin.scholarship.firstInFamily')} value={yn(app.first_in_family)} />
                    <Field label={t('admin.scholarship.parentsOccupation')} value={app.parents_occupation} />
                    <Field label={t('admin.scholarship.siblingsStudying')} value={app.siblings_studying_count} />
                  </dl>
                  <Field label={t('admin.scholarship.familyContext')} value={app.family_context} />
                </div>
              </Card>
            )}

            {/* Funding — full-width, hidden when empty */}
            {app.funding_need && (
              <Card title={t('admin.scholarship.sec.funding')}>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5 md:grid-cols-3">
                  <Field label={t('admin.scholarship.funding')} value={joinOr(app.funding_need.categories)} />
                  <Field label={t('admin.scholarship.programmeMonths')} value={app.funding_need.programme_months} />
                </dl>
                {app.funding_need.funding_note && <div className="mt-2"><Field label={t('admin.scholarship.fundingNote')} value={app.funding_need.funding_note} /></div>}
              </Card>
            )}
          </div>
        )
      })()}

      {/* Review & actions — interactive panels */}
      <GroupLabel>{t('admin.scholarship.reviewActions')}</GroupLabel>
      <div className="grid items-start gap-4 lg:grid-cols-2">

      {/* Documents / referees / consent */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm lg:col-span-2">
        <h3 className="font-semibold text-sm mb-2">{t('admin.scholarship.documents')} ({app.documents.length})</h3>
        <ul className="text-sm text-gray-600 space-y-1">
          {app.documents.map((d) => (
            <li key={d.id}>
              {d.doc_type}: {d.download_url
                ? <a href={d.download_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">{d.original_filename || 'view'}</a>
                : (d.original_filename || '—')}{' '}
              <span className="text-gray-400">[{d.verification_status}]</span>
              {/* Soft OCR name/address presence check (results slip, income docs,
                  bills, offer letter). Never blocks — a flag for the reviewer. */}
              {d.vision_name_match && (
                <span className={`ml-1 rounded px-1.5 py-0.5 text-xs ${
                  d.vision_name_match === 'found' ? 'bg-green-50 text-green-700'
                  : d.vision_name_match === 'unreadable' ? 'bg-gray-100 text-gray-500'
                  : 'bg-amber-50 text-amber-700'}`}>
                  name {d.vision_name_match === 'found' ? '✓' : d.vision_name_match === 'unreadable' ? '?' : '✗'}
                </span>
              )}
              {d.vision_address_match && (
                <span className={`ml-1 rounded px-1.5 py-0.5 text-xs ${
                  d.vision_address_match === 'found' ? 'bg-green-50 text-green-700'
                  : d.vision_address_match === 'unreadable' ? 'bg-gray-100 text-gray-500'
                  : 'bg-amber-50 text-amber-700'}`}>
                  addr {d.vision_address_match === 'found' ? '✓' : d.vision_address_match === 'unreadable' ? '?' : '✗'}
                </span>
              )}
              {/* Document-assist: Gemini-extracted fields for verification. */}
              {d.vision_fields?.fields && Object.keys(d.vision_fields.fields).length > 0 && (
                <div className="mt-1 rounded bg-gray-50 p-2 text-xs text-gray-600">
                  <span className="font-medium text-gray-500">{t('admin.scholarship.extractFields.title')}: </span>
                  {Object.entries(d.vision_fields.fields)
                    .filter(([, v]) => v && (Array.isArray(v) ? v.length : String(v).trim()))
                    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
                    .join(' · ')}
                  {d.vision_fields.warnings && d.vision_fields.warnings.length > 0 && (
                    <span className="text-amber-600"> ⚠ {d.vision_fields.warnings.join('; ')}</span>
                  )}
                </div>
              )}
            </li>
          ))}
          {app.documents.length === 0 && <li className="text-gray-400">{t('admin.scholarship.none')}</li>}
        </ul>

        <h3 className="font-semibold text-sm mt-4 mb-1">{t('admin.scholarship.referees')}</h3>
        <p className="text-xs text-gray-400 mb-2">{t('admin.scholarship.refHint')}</p>
        <ul className="text-sm text-gray-600 space-y-1">
          {app.referees.map((r) => (
            <li key={r.id} className="flex items-start justify-between gap-2">
              <span>
                {r.name}{r.role ? ` (${r.role})` : ''}{r.relationship ? ` · ${r.relationship}` : ''}
                {r.phone ? ` — ${r.phone}` : ''}{r.email ? ` · ${r.email}` : ''}
              </span>
              <button onClick={() => doDeleteReferee(r.id)} disabled={!!busy}
                className="text-red-500 hover:underline text-xs shrink-0 disabled:opacity-50">
                {t('admin.scholarship.refRemove')}
              </button>
            </li>
          ))}
          {app.referees.length === 0 && <li className="text-gray-400">{t('admin.scholarship.none')}</li>}
        </ul>
        {/* Add referee (coordinator records it at verify-&-accept) */}
        <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-2">
          <input value={refForm.name} onChange={(e) => setRefForm((f) => ({ ...f, name: e.target.value }))}
            placeholder={t('admin.scholarship.refName')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.role} onChange={(e) => setRefForm((f) => ({ ...f, role: e.target.value }))}
            placeholder={t('admin.scholarship.refRole')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.relationship} onChange={(e) => setRefForm((f) => ({ ...f, relationship: e.target.value }))}
            placeholder={t('admin.scholarship.refRelationship')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.phone} onChange={(e) => setRefForm((f) => ({ ...f, phone: e.target.value }))}
            placeholder={t('admin.scholarship.refPhone')} className="border rounded-lg px-2 py-1 text-sm" />
          <input value={refForm.email} onChange={(e) => setRefForm((f) => ({ ...f, email: e.target.value }))}
            placeholder={t('admin.scholarship.refEmail')} className="border rounded-lg px-2 py-1 text-sm sm:col-span-2" />
        </div>
        <button onClick={doAddReferee} disabled={!!busy || !refForm.name.trim()}
          className="mt-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
          {busy === 'ref' ? t('admin.scholarship.refAdding') : t('admin.scholarship.refAdd')}
        </button>

        <h3 className="font-semibold text-sm mt-4 mb-2">{t('admin.scholarship.consent')}</h3>
        <p className="text-sm text-gray-600">
          {app.consents.some((c) => c.is_active) ? t('admin.scholarship.consentGiven') : t('admin.scholarship.consentNone')}
        </p>
      </div>

      {/* S16 Phase A: deterministic pre-interview flag list. Each flag = a
          data inconsistency worth asking about during the interview. Empty
          state when nothing flags — the engine is honest about silence. */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold">{t('admin.scholarship.anomaly.title')}</h2>
          <div className="flex items-center gap-2">
            {app.anomalies && app.anomalies.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700">
                {app.anomalies.length} {app.anomalies.length === 1 ? t('admin.scholarship.anomaly.flagOne') : t('admin.scholarship.anomaly.flagMany')}
              </span>
            )}
            {/* Phase B: admin-on-demand Gemini gap-spotter (billable — one call). */}
            {canWrite && (
              <button onClick={doSuggestGaps} disabled={!!busy}
                className="px-2.5 py-1 rounded-lg text-xs bg-indigo-600 text-white disabled:opacity-50">
                {busy === 'gaps' ? t('admin.scholarship.gaps.running') : t('admin.scholarship.gaps.button')}
              </button>
            )}
          </div>
        </div>
        <p className="text-xs text-gray-500">{t('admin.scholarship.anomaly.intro')}</p>
        {!app.anomalies || app.anomalies.length === 0 ? (
          <p className="text-sm text-gray-400 italic">{t('admin.scholarship.anomaly.empty')}</p>
        ) : (
          <ul className="space-y-3">
            {app.anomalies.map((a) => (
              <li key={a.code} className="rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-1.5">
                <div className="flex items-start gap-2">
                  <span className="text-amber-600 shrink-0" aria-hidden>⚠</span>
                  <div className="space-y-1">
                    <p className="text-sm text-gray-800">
                      {t(`admin.scholarship.anomaly.${a.code}.fact`, Object.fromEntries(Object.entries(a.params).map(([k, v]) => [k, String(v)])))}
                    </p>
                    <p className="text-sm text-gray-700 italic">
                      <span className="font-semibold not-italic">{t('admin.scholarship.anomaly.askLabel')}:</span>{' '}
                      {t(`admin.scholarship.anomaly.${a.code}.question`, Object.fromEntries(Object.entries(a.params).map(([k, v]) => [k, String(v)])))}
                    </p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {/* Phase B: Gemini-suggested interview gaps — carry their own dynamic
            text (not i18n by code, unlike the deterministic flags above). */}
        {app.interview_gaps && app.interview_gaps.length > 0 && (
          <div className="space-y-2 border-t border-gray-100 pt-3">
            <p className="text-xs font-medium text-gray-500">{t('admin.scholarship.gaps.title')}</p>
            <ul className="space-y-2">
              {app.interview_gaps.map((g) => (
                <li key={g.code} className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
                  <div className="flex items-start gap-2">
                    <span className="shrink-0 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white" aria-hidden>
                      {t('admin.scholarship.gaps.aiBadge')}
                    </span>
                    <div className="space-y-1">
                      <p className="text-sm text-gray-800">{g.question}</p>
                      {g.why && <p className="text-xs text-gray-500">{t('admin.scholarship.gaps.whyLabel')}: {g.why}</p>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Phase C: assignment */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-2">
        <h2 className="font-semibold">{t('admin.scholarship.assignTitle')}</h2>
        <select
          value={app.assigned_to_id ?? ''}
          disabled={!canWrite || !!busy}
          onChange={(e) => doAssign(e.target.value ? Number(e.target.value) : null)}
          className="border rounded-lg px-3 py-2 text-sm w-full sm:w-auto"
        >
          <option value="">{t('admin.scholarship.unassigned')}</option>
          {admins.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </div>

      {/* Phase C: interview capture — verdict + rationale per pre-interview flag */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3 lg:col-span-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('admin.scholarship.interview.title')}</h2>
          {app.interview_session?.status === 'submitted' && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700">
              {t('admin.scholarship.interview.submitted')}
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500">{t('admin.scholarship.interview.intro')}</p>
        {(() => {
          // Capture verdicts on BOTH the deterministic flags (label = i18n fact)
          // and the Gemini gaps (label = the gap's own question). Same findings
          // dict, keyed by code — the backend stores any key.
          const items = [
            ...app.anomalies.map((a) => ({
              code: a.code,
              label: t(`admin.scholarship.anomaly.${a.code}.fact`, Object.fromEntries(Object.entries(a.params).map(([k, v]) => [k, String(v)]))),
              ai: false,
            })),
            ...(app.interview_gaps || []).map((g) => ({ code: g.code, label: g.question, ai: true })),
          ]
          if (items.length === 0) {
            return <p className="text-sm text-gray-400 italic">{t('admin.scholarship.interview.noFlags')}</p>
          }
          return (
            <ul className="space-y-3">
              {items.map((it) => {
                const f = findings[it.code] ?? { verdict: '', rationale: '' }
                const setF = (patch: Partial<{ verdict: string; rationale: string }>) =>
                  setFindings((prev) => ({ ...prev, [it.code]: { ...f, ...patch } }))
                return (
                  <li key={it.code} className="border rounded-lg p-3">
                    <p className="text-sm text-gray-800">
                      {it.ai && <span className="mr-1 rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-semibold text-white align-middle">{t('admin.scholarship.gaps.aiBadge')}</span>}
                      {it.label}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {VERDICTS.map((v) => (
                        <label key={v} className={`cursor-pointer rounded-full border px-3 py-1 text-xs ${f.verdict === v ? 'border-primary-600 bg-primary-600 text-white' : 'border-gray-300 text-gray-700'}`}>
                          <input type="radio" name={`v-${it.code}`} className="sr-only" disabled={!canWrite}
                            checked={f.verdict === v} onChange={() => setF({ verdict: v })} />
                          {t(`admin.scholarship.interview.verdict.${v}`)}
                        </label>
                      ))}
                    </div>
                    <input
                      value={f.rationale} maxLength={140} disabled={!canWrite}
                      onChange={(e) => setF({ rationale: e.target.value })}
                      placeholder={t('admin.scholarship.interview.rationalePlaceholder')}
                      className="mt-2 w-full border rounded-lg px-3 py-1.5 text-sm"
                    />
                  </li>
                )
              })}
            </ul>
          )
        })()}
        {/* Rubric */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {RUBRIC_DIMS.map((dim) => (
            <div key={dim}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{t(`admin.scholarship.interview.rubric.${dim}`)}</label>
              <select value={rubric[dim] ?? ''} disabled={!canWrite}
                onChange={(e) => setRubric((r) => ({ ...r, [dim]: Number(e.target.value) }))}
                className="border rounded-lg px-2 py-1.5 text-sm w-full">
                <option value="">—</option>
                {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
          ))}
        </div>
        <textarea value={note} disabled={!canWrite} rows={2}
          onChange={(e) => setNote(e.target.value)}
          placeholder={t('admin.scholarship.interview.notePlaceholder')}
          className="w-full border rounded-lg px-3 py-2 text-sm" />
        {canWrite && (
          <div className="flex gap-2">
            <button onClick={doSaveInterview} disabled={!!busy}
              className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50">
              {busy === 'iv' ? t('common.loading') : t('admin.scholarship.interview.saveDraft')}
            </button>
            <button onClick={doSubmitInterview} disabled={!!busy}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
              {busy === 'ivs' ? t('common.loading') : t('admin.scholarship.interview.submit')}
            </button>
          </div>
        )}
      </div>

      {/* Phase C: request more documentation from the student */}
      {canWrite && (
        <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-2">
          <h2 className="font-semibold">{t('admin.scholarship.requestInfoTitle')}</h2>
          <p className="text-xs text-gray-500">{t('admin.scholarship.requestInfoIntro')}</p>
          {app.info_request_note && (
            <p className="text-xs text-gray-500 italic">
              {t('admin.scholarship.requestInfoLast')}: {app.info_request_note}
            </p>
          )}
          <textarea value={infoNote} rows={2} onChange={(e) => setInfoNote(e.target.value)}
            placeholder={t('admin.scholarship.requestInfoPlaceholder')}
            className="w-full border rounded-lg px-3 py-2 text-sm" />
          <button onClick={doRequestInfo} disabled={!!busy || !infoNote.trim()}
            className="px-4 py-2 border rounded-lg text-sm disabled:opacity-50">
            {busy === 'info' ? t('common.loading') : t('admin.scholarship.requestInfoSend')}
          </button>
        </div>
      )}

      {/* Verify & accept (human gate — locks the NRIC, advances → accepted) */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3 lg:col-span-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">{t('admin.scholarship.verifyTitle')}</h2>
          {app.nric_verified && (
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700">
              {t('admin.scholarship.nricLocked')}
            </span>
          )}
        </div>

        {app.status === 'accepted' ? (
          <p className="text-sm text-gray-600">
            {t('admin.scholarship.acceptedBy')} {app.verified_by || '—'}
            {app.verified_at ? ` · ${new Date(app.verified_at).toLocaleDateString()}` : ''}
          </p>
        ) : ['shortlisted', 'profile_complete', 'interviewing', 'interviewed'].includes(app.status) ? (
          <>
            {/* Phase C hard gate: cannot accept until every compulsory part is in. */}
            {!app.completeness.complete && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                <p className="font-medium text-amber-900">{t('admin.scholarship.incompleteTitle')}</p>
                <ul className="mt-1 list-disc ml-5 text-amber-800">
                  {COMPLETENESS_PARTS.filter((p) => !app.completeness[p]).map((p) => (
                    <li key={p}>{t(`admin.scholarship.completeness.${p}`)}</li>
                  ))}
                </ul>
              </div>
            )}
            <p className="text-sm text-gray-500">{t('admin.scholarship.verifyHint')}</p>
            <div className="space-y-2">
              {VERIFY_ITEMS.map((key) => (
                <label key={key} className="flex items-start gap-2 text-sm text-gray-700">
                  <input type="checkbox" className="mt-1" checked={!!checklist[key]} disabled={!canWrite}
                    onChange={(e) => setChecklist((c) => ({ ...c, [key]: e.target.checked }))} />
                  <span>
                    {t(`admin.scholarship.check_${key}`)}
                    {key === 'nric' && <span className="ml-1 font-mono text-gray-500">{app.nric || '—'}</span>}
                    {key === 'name' && <span className="ml-1 text-gray-500">{app.name || '—'}</span>}
                  </span>
                </label>
              ))}
            </div>
            <button onClick={doVerifyAccept}
              disabled={!!busy || !canWrite || !app.completeness.complete || !VERIFY_ITEMS.every((k) => checklist[k])}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
              {busy === 'verify' ? t('admin.scholarship.accepting') : t('admin.scholarship.verifyAccept')}
            </button>
          </>
        ) : (
          <p className="text-sm text-gray-400">{t('admin.scholarship.notShortlisted')}</p>
        )}

        {/* S13: Vision OCR (soft signal next to the manual checklist) */}
        {(() => {
          const ic = app.documents.find((d: AdminApplicantDocument) => d.doc_type === 'ic' && d.vision_run_at)
          if (!ic) return null
          const pill = (verdict: string) => {
            const palette: Record<string, string> = {
              match: 'bg-green-100 text-green-700',
              partial: 'bg-amber-100 text-amber-700',
              mismatch: 'bg-red-100 text-red-700',
              unreadable: 'bg-gray-100 text-gray-600',
            }
            return palette[verdict] || 'bg-gray-100 text-gray-600'
          }
          return (
            <div className="mt-2 border-t pt-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-700">{t('admin.scholarship.visionTitle')}</span>
                <button onClick={() => doReRunVision(ic.id)} disabled={!!busy}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-50">
                  {busy === 'vision' ? t('admin.scholarship.visionRunning') : t('admin.scholarship.visionRerun')}
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded-full ${pill(ic.vision_nric_verdict)}`}>
                  NRIC {ic.vision_nric_verdict || '—'}
                </span>
                <span className={`px-2 py-0.5 rounded-full ${pill(ic.vision_name_verdict)}`}>
                  Name {ic.vision_name_verdict || '—'}
                </span>
              </div>
              {(ic.vision_nric || ic.vision_name) && (
                <p className="text-xs text-gray-500 font-mono break-words">
                  {t('admin.scholarship.visionExtracted')}: {ic.vision_nric || '—'} · {ic.vision_name || '—'}
                </p>
              )}
              {/* Post-S14: surface MyKad address (no matcher — interviewer eyeballs it). */}
              {ic.vision_address && (
                <div className="mt-1 rounded-md border border-gray-200 bg-gray-50 p-2">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
                    {t('admin.scholarship.visionAddressTitle')}
                  </p>
                  <p className="text-xs text-gray-700 mt-0.5 break-words">{ic.vision_address}</p>
                  {app.address && (
                    <p className="text-[11px] text-gray-500 mt-1">
                      {t('admin.scholarship.visionAddressVsProfile')}:{' '}
                      <span className="text-gray-700">{app.address}</span>
                    </p>
                  )}
                </div>
              )}
              {ic.vision_error && <p className="text-xs text-amber-700">{ic.vision_error}</p>}
              {app.declaration_name && ic.vision_name && (
                <p className="text-xs text-gray-500">
                  {t('admin.scholarship.visionDeclaration')}: <span className="font-medium">{app.declaration_name}</span>
                </p>
              )}
            </div>
          )
        })()}

        {/* S17: parent/guardian IC Vision row — shown when the minor uploaded
            their parent's IC. No automated verdicts here (the anomaly engine
            cross-checks against the typed guardian name + adult-age threshold
            and surfaces flags in the Pre-interview flags card above). */}
        {(() => {
          const pic = app.documents.find(
            (d: AdminApplicantDocument) => d.doc_type === 'parent_ic' && d.vision_run_at,
          )
          if (!pic) return null
          return (
            <div className="mt-2 border-t pt-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-gray-700">
                  {t('admin.scholarship.parentIcTitle')}
                </span>
                <button onClick={() => doReRunVision(pic.id)} disabled={!!busy}
                  className="text-xs text-blue-600 hover:underline disabled:opacity-50">
                  {busy === 'vision' ? t('admin.scholarship.visionRunning') : t('admin.scholarship.visionRerun')}
                </button>
              </div>
              {(pic.vision_nric || pic.vision_name) && (
                <p className="text-xs text-gray-500 font-mono break-words">
                  {t('admin.scholarship.visionExtracted')}: {pic.vision_nric || '—'} · {pic.vision_name || '—'}
                </p>
              )}
              {pic.vision_address && (
                <p className="text-[11px] text-gray-500 break-words">
                  {pic.vision_address}
                </p>
              )}
              {pic.vision_error && <p className="text-xs text-amber-700">{pic.vision_error}</p>}
            </div>
          )
        })()}

        <label className="mt-2 flex items-center gap-2 border-t pt-3 text-sm text-gray-700">
          <input type="checkbox" checked={app.mentoring_candidate} disabled={!!busy}
            onChange={(e) => toggleMentoring(e.target.checked)} />
          {t('admin.scholarship.mentoring')}
        </label>
      </div>

      {/* AI sponsor profile */}
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm space-y-3 lg:col-span-2">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold">{t('admin.scholarship.profileTitle')}</h2>
          <div className="flex items-center gap-2">
            <label className="text-xs text-gray-500">{t('admin.scholarship.genLang')}</label>
            <select value={genLang} onChange={(e) => setGenLang(e.target.value)} disabled={!!busy}
              className="border rounded-lg px-2 py-1 text-sm">
              <option value="en">English</option>
              <option value="ms">Bahasa Melayu</option>
            </select>
            {profile && <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-700">{profile.status}</span>}
          </div>
        </div>

        {!profile ? (
          <button onClick={doGenerate} disabled={busy === 'gen'} className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
            {busy === 'gen' ? t('admin.scholarship.generating') : t('admin.scholarship.generate')}
          </button>
        ) : (
          <>
            <textarea
              value={markdown} onChange={(e) => setMarkdown(e.target.value)} rows={14}
              className="w-full border rounded-lg p-3 font-mono text-sm"
            />
            <p className="text-xs text-gray-400">{t('admin.scholarship.model')}: {profile.model_used || '—'}</p>
            <div className="flex flex-wrap gap-2">
              <button onClick={doGenerate} disabled={!!busy} className="px-3 py-2 border rounded-lg text-sm disabled:opacity-50">
                {busy === 'gen' ? t('admin.scholarship.generating') : t('admin.scholarship.regenerate')}
              </button>
              <button onClick={doSave} disabled={!!busy} className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'save' ? t('admin.scholarship.saving') : t('admin.scholarship.save')}
              </button>
              <button onClick={doPublish} disabled={!!busy} className="px-3 py-2 bg-green-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'pub' ? t('admin.scholarship.publishing') : t('admin.scholarship.publish')}
              </button>
              <button onClick={doFinalise} disabled={!!busy || app?.interview_session?.status !== 'submitted'}
                title={app?.interview_session?.status !== 'submitted' ? t('admin.scholarship.finalProfile.needInterview') : undefined}
                className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm disabled:opacity-50">
                {busy === 'final' ? t('admin.scholarship.finalProfile.running') : t('admin.scholarship.finalProfile.button')}
              </button>
            </div>
            {app?.interview_session?.status !== 'submitted' && (
              <p className="text-xs text-gray-400">{t('admin.scholarship.finalProfile.needInterview')}</p>
            )}
            {profile.final_markdown && (
              <div className="mt-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 space-y-1">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-indigo-900">{t('admin.scholarship.finalProfile.title')}</h3>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-600 text-white">{t('admin.scholarship.finalProfile.aiBadge')}</span>
                </div>
                <p className="text-[11px] text-indigo-700">
                  {t('admin.scholarship.finalProfile.finalisedAt')}: {profile.finalised_at ? new Date(profile.finalised_at).toLocaleString() : '—'} · {profile.final_model_used || '—'}
                </p>
                <pre className="whitespace-pre-wrap text-sm text-gray-800 font-sans">{profile.final_markdown}</pre>
              </div>
            )}
          </>
        )}
        {error && <p className="text-red-600 text-sm">{error}</p>}
      </div>
      </div>
    </div>
  )
}
