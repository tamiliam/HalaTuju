'use client'

import { useCallback, useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { effectiveRole } from '@/lib/navigation'
import { STATUS_TONE, isEditable, termsErrorKey } from '@/lib/sponsorTerms'
import ClausesTab from '@/components/sponsors/terms/ClausesTab'
import QuizRehearsal from '@/components/sponsors/terms/QuizRehearsal'
import PreviewTab from '@/components/sponsors/terms/PreviewTab'
import DeployTab from '@/components/sponsors/terms/DeployTab'
import {
  generateSponsorTermsQuiz, getSponsorTerms, publishSponsorTerms, putSponsorTermsSections,
  updateSponsorTermsIntro, validateSponsorTerms,
  type SponsorTermsDetail, type SponsorTermsSection, type SponsorTermsValidation,
} from '@/lib/admin-api'

/**
 * The sponsor-terms editor, adopting the contract-template shell (owner, 2026-07-28) with four
 * tabs instead of six: no Config (the title and intro live at the top of Clauses) and no Schedule
 * (there is no money in this document).
 *
 * A NESTED route under /admin/sponsors, so `activeItem` resolves it to the Sponsors nav entry by
 * longest match — no registry entry, exactly as /admin/contracts/9 behaves.
 */
const TABS = ['clauses', 'quiz', 'preview', 'deploy'] as const
type Tab = (typeof TABS)[number]

export default function SponsorTermsEditorPage() {
  const params = useParams()
  const id = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()

  const isSuper = effectiveRole(role) === 'super'
  const [terms, setTerms] = useState<SponsorTermsDetail | null>(null)
  const [sections, setSections] = useState<SponsorTermsSection[]>([])
  const [validation, setValidation] = useState<SponsorTermsValidation | null>(null)
  const [tab, setTab] = useState<Tab>('clauses')
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    if (!token) return
    getSponsorTerms(id, { token }).then((d) => {
      setTerms(d)
      setSections(d.sections)
      setDirty(false)
      return validateSponsorTerms(id, { token }).then(setValidation)
    }).catch(() => setNotFound(true))
  }, [token, id])

  useEffect(() => { load() }, [load])

  const fail = (e: unknown) => setError(t(termsErrorKey((e as { code?: string })?.code)))

  const save = async () => {
    if (!token || !terms) return
    setBusy(true); setError('')
    try {
      await putSponsorTermsSections(id, sections, { token })
      await updateSponsorTermsIntro(id, {
        title_en: terms.title_en, title_ms: terms.title_ms, title_ta: terms.title_ta,
        intro_en: terms.intro_en, intro_ms: terms.intro_ms, intro_ta: terms.intro_ta,
      }, { token })
      load()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  const generate = async (order: number) => {
    if (!token) return
    setGenerating(order); setError('')
    try {
      // Save first: the server drafts from what it HAS, so an unsaved edit would produce a
      // question about the previous wording.
      await putSponsorTermsSections(id, sections, { token })
      const d = await generateSponsorTermsQuiz(id, order, { token })
      setTerms(d); setSections(d.sections); setDirty(false)
    } catch (e) { fail(e) } finally { setGenerating(null) }
  }

  const publish = async () => {
    if (!token) return
    setBusy(true); setError('')
    try {
      await publishSponsorTerms(id, { token })
      load()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  if (notFound) return <p className="text-red-600">{t('admin.sponsors.terms.error.not_found')}</p>
  if (!terms) return <p className="text-gray-400">{t('common.loading')}</p>

  const editable = isEditable(terms)

  return (
    <div className="max-w-5xl font-plex">
      <button type="button" onClick={() => router.push('/admin/sponsors?panel=terms')}
        className="text-sm text-blue-600 hover:text-blue-800">
        {t('admin.sponsors.terms.backToList')}
      </button>

      <div className="flex items-center gap-3 mt-2 mb-1">
        <h1 className="text-2xl font-bold text-gray-900">{terms.version}</h1>
        <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
          STATUS_TONE[terms.status] || STATUS_TONE.archived}`}>
          {t(`admin.sponsors.terms.status.${terms.status}`)}
        </span>
      </div>

      {error && <p className="text-sm text-red-600 my-2">{error}</p>}

      <div className="border-b border-gray-200 mb-6 flex gap-1 overflow-x-auto">
        {TABS.map((tb) => (
          <button key={tb} type="button" role="tab" aria-selected={tab === tb}
            onClick={() => setTab(tb)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${
              tab === tb ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'}`}>
            {t(`admin.sponsors.terms.tab.${tb}`)}
          </button>
        ))}
      </div>

      {tab === 'clauses' && (
        <ClausesTab terms={terms} sections={sections} disabled={!editable} busy={busy} dirty={dirty}
          onTerms={(next) => { setTerms(next); setDirty(true) }}
          onSections={(next) => { setSections(next); setDirty(true) }}
          onSave={save} onGenerate={generate} generating={generating} t={t} />
      )}
      {/* Not a second form — the quiz is WRITTEN inline on Clauses and TAKEN here, off the
          sections currently on screen, so an unsaved edit can be rehearsed before saving. */}
      {tab === 'quiz' && <QuizRehearsal sections={sections} t={t} />}
      {tab === 'preview' && <PreviewTab id={id} token={token!} t={t} />}
      {tab === 'deploy' && (
        <DeployTab terms={terms} validation={validation} isSuper={isSuper} dirty={dirty}
          busy={busy} onPublish={publish} t={t} />
      )}
    </div>
  )
}
