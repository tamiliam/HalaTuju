'use client'

import { useCallback, useEffect, useState } from 'react'
import { btnGhost, btnPrimary, inputCls } from '@/components/contracts/shared'
import TermsSectionEditor from './TermsSectionEditor'
import {
  checkpointCount, isEditable, STATUS_TONE, termsErrorKey, translationProgress,
} from '@/lib/sponsorTerms'
import {
  createSponsorTerms, generateSponsorTermsQuiz, getSponsorTerms, getSponsorTermsList,
  publishSponsorTerms, putSponsorTermsSections, updateSponsorTermsIntro, validateSponsorTerms,
  type SponsorTermsDetail, type SponsorTermsListPayload, type SponsorTermsSection,
  type SponsorTermsValidation,
} from '@/lib/admin-api'

/**
 * The Terms panel: every version down the left, the selected one edited on the right.
 *
 * Nothing here is sponsor-facing — a sponsor meets this document in T3. What this panel does is
 * let an org_admin author it and a super make it binding, which is the same two-person split the
 * credit chain and the contract deploy already use.
 */
export default function SponsorTermsCard({ token, isSuper, t }: {
  token: string | null
  isSuper: boolean
  t: (k: string, p?: Record<string, string>) => string
}) {
  const [list, setList] = useState<SponsorTermsListPayload | null>(null)
  const [current, setCurrent] = useState<SponsorTermsDetail | null>(null)
  const [sections, setSections] = useState<SponsorTermsSection[]>([])
  const [validation, setValidation] = useState<SponsorTermsValidation | null>(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState<number | null>(null)
  const [error, setError] = useState('')
  const [newVersion, setNewVersion] = useState('')

  const editable = isEditable(current)

  const loadList = useCallback(() => {
    if (!token) return
    getSponsorTermsList({ token })
      .then(setList)
      .catch(() => setError(t('admin.sponsors.terms.loadError')))
  }, [token, t])

  useEffect(() => { loadList() }, [loadList])

  const open = useCallback((id: number) => {
    if (!token) return
    setError('')
    getSponsorTerms(id, { token }).then((d) => {
      setCurrent(d)
      setSections(d.sections)
      setDirty(false)
      return validateSponsorTerms(id, { token }).then(setValidation)
    }).catch(() => setError(t('admin.sponsors.terms.loadError')))
  }, [token, t])

  const fail = (e: unknown) => {
    const code = (e as { code?: string })?.code
    setError(t(termsErrorKey(code)))
  }

  const save = async () => {
    if (!token || !current) return
    setBusy(true); setError('')
    try {
      await putSponsorTermsSections(current.id, sections, { token })
      await updateSponsorTermsIntro(current.id, {
        title_en: current.title_en, title_ms: current.title_ms, title_ta: current.title_ta,
        intro_en: current.intro_en, intro_ms: current.intro_ms, intro_ta: current.intro_ta,
      }, { token })
      open(current.id)
      loadList()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  const generate = async (order: number) => {
    if (!token || !current) return
    setGenerating(order); setError('')
    try {
      // Save first: the server generates from what it HAS, so an unsaved edit would produce a
      // question about the previous wording.
      await putSponsorTermsSections(current.id, sections, { token })
      const d = await generateSponsorTermsQuiz(current.id, order, { token })
      setCurrent(d); setSections(d.sections); setDirty(false)
    } catch (e) { fail(e) } finally { setGenerating(null) }
  }

  const publish = async () => {
    if (!token || !current) return
    setBusy(true); setError('')
    try {
      await publishSponsorTerms(current.id, { token })
      open(current.id)
      loadList()
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  const create = async () => {
    if (!token || !newVersion.trim()) return
    setBusy(true); setError('')
    try {
      const d = await createSponsorTerms({ version: newVersion.trim() }, { token })
      setNewVersion('')
      loadList()
      open(d.id)
    } catch (e) { fail(e) } finally { setBusy(false) }
  }

  if (!list) return <p className="text-sm text-gray-500 py-8 text-center">{t('common.loading')}</p>

  const progress = current ? translationProgress(current, sections) : null

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-base font-semibold">{t('admin.sponsors.terms.title')}</h2>
        <p className="text-sm text-gray-500 mt-1">{t('admin.sponsors.terms.subtitle')}</p>
      </div>

      {!list.active_version && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <p className="font-semibold">{t('admin.sponsors.terms.noneActiveTitle')}</p>
          <p className="mt-1">{t('admin.sponsors.terms.noneActiveBody')}</p>
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid gap-5 md:grid-cols-[16rem_1fr]">
        {/* versions */}
        <div className="flex flex-col gap-2">
          {list.versions.map((v) => (
            <button key={v.id} type="button" onClick={() => open(v.id)}
              className={`text-left rounded-lg border px-3 py-2 transition-colors ${
                current?.id === v.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}>
              <span className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs">{v.version}</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                  STATUS_TONE[v.status] || STATUS_TONE.archived}`}>
                  {t(`admin.sponsors.terms.status.${v.status}`)}
                </span>
              </span>
              <span className="block text-xs text-gray-500 mt-0.5">
                {t('admin.sponsors.terms.sectionCount', { n: String(v.section_count) })}
              </span>
            </button>
          ))}

          <div className="flex gap-2 mt-2">
            <input className={inputCls} value={newVersion} disabled={busy}
              placeholder={t('admin.sponsors.terms.newVersionPh')}
              onChange={(e) => setNewVersion(e.target.value)} />
            <button type="button" className={btnGhost} disabled={busy || !newVersion.trim()}
              onClick={create}>{t('admin.sponsors.terms.create')}</button>
          </div>
        </div>

        {/* the selected version */}
        {!current ? (
          <p className="text-sm text-gray-500">{t('admin.sponsors.terms.pickOne')}</p>
        ) : (
          <div className="flex flex-col gap-4">
            {!editable && (
              <p className="text-xs text-gray-500 rounded-lg bg-gray-50 border border-gray-200 px-3 py-2">
                {t('admin.sponsors.terms.readOnly', { status: t(`admin.sponsors.terms.status.${current.status}`) })}
              </p>
            )}

            <input className={inputCls} disabled={!editable} value={current.title_en}
              placeholder={t('admin.sponsors.terms.titlePh')}
              onChange={(e) => { setCurrent({ ...current, title_en: e.target.value }); setDirty(true) }} />
            <textarea className={inputCls} rows={2} disabled={!editable} value={current.intro_en}
              placeholder={t('admin.sponsors.terms.introPh')}
              onChange={(e) => { setCurrent({ ...current, intro_en: e.target.value }); setDirty(true) }} />

            <TermsSectionEditor
              sections={sections} disabled={!editable} generating={generating}
              onChange={(next) => { setSections(next); setDirty(true) }}
              onGenerate={generate} t={t}
            />

            <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
              <span>{t('admin.sponsors.terms.checkpointCount', { n: String(checkpointCount(sections)) })}</span>
              {progress && (['ms', 'ta'] as const).map((loc) => (
                <span key={loc} className={progress[loc].complete ? 'text-green-700' : ''}>
                  {t('admin.sponsors.terms.translated', {
                    loc: loc.toUpperCase(),
                    done: String(progress[loc].done),
                    total: String(progress[loc].total),
                  })}
                </span>
              ))}
            </div>

            {editable && (
              <div className="flex gap-2">
                <button type="button" className={btnPrimary} disabled={busy || !dirty} onClick={save}>
                  {busy ? t('admin.sources.saving') : t('admin.sources.save')}
                </button>
              </div>
            )}

            {/* the publish checklist — labels come from the server, so the panel knows no rules */}
            {validation && (
              <div className="rounded-xl border border-gray-200 p-4 flex flex-col gap-2">
                <h3 className="text-sm font-semibold">{t('admin.sponsors.terms.checklist')}</h3>
                {validation.errors.map((e) => (
                  <p key={e.code} className="text-xs text-red-600">✗ {e.label}</p>
                ))}
                {validation.warnings.map((w) => (
                  <p key={w.code} className="text-xs text-amber-700">! {w.label}</p>
                ))}
                {validation.ok && validation.warnings.length === 0 && (
                  <p className="text-xs text-green-700">✓ {t('admin.sponsors.terms.allClear')}</p>
                )}

                {editable && (
                  isSuper ? (
                    <button type="button" className={`${btnPrimary} mt-2 self-start`}
                      disabled={busy || !validation.ok || dirty} onClick={publish}>
                      {t('admin.sponsors.terms.publish')}
                    </button>
                  ) : (
                    <p className="text-xs text-gray-500 mt-2">{t('admin.sponsors.terms.superOnly')}</p>
                  )
                )}
                {editable && dirty && (
                  <p className="text-xs text-gray-500">{t('admin.sponsors.terms.saveFirst')}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
