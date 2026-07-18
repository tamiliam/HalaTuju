'use client'

import { useState, useEffect, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  fetchContractPreviewHtml, fetchContractPreviewPdf, type ContractTemplateDetail,
} from '@/lib/admin-api'
import { CLOCALES, CLocale, LangTabs } from './shared'

// The Preview tab — the rendered agreement HTML in a sandboxed iframe (srcDoc), with a
// language selector and an Open-PDF action. Sample particulars, PREVIEW banner.
export default function TemplatePreview({ template, token }: { template: ContractTemplateDetail; token: string }) {
  const { t } = useT()
  const [lang, setLang] = useState<CLocale>('en')
  const [html, setHtml] = useState('')
  const [err, setErr] = useState<string | null>(null)

  const load = useCallback(async (l: CLocale) => {
    setErr(null)
    try { setHtml(await fetchContractPreviewHtml(template.id, l, { token })) }
    catch { setErr(t('admin.contracts.previewFailed')) }
  }, [template.id, token, t])

  useEffect(() => { load(lang) }, [lang, load])

  const openPdf = async () => {
    try {
      const blob = await fetchContractPreviewPdf(template.id, lang, { token })
      window.open(URL.createObjectURL(blob), '_blank')
    } catch { setErr(t('admin.contracts.previewFailed')) }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{t('admin.contracts.previewLocale')}</span>
          <LangTabs value={lang} onChange={(l) => { if (CLOCALES.includes(l)) setLang(l) }} />
        </div>
        <button type="button" onClick={openPdf}
          className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-700 hover:bg-gray-50">
          {t('admin.contracts.openPdf')}
        </button>
      </div>
      {err && <div className="rounded-lg p-3 bg-red-50 border border-red-200 text-red-600 text-sm">{err}</div>}
      <iframe title="preview" srcDoc={html} className="w-full h-[70vh] rounded-xl border bg-white" sandbox="" />
    </div>
  )
}
