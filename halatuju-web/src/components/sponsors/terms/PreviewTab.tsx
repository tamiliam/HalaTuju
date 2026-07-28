'use client'

import { useCallback, useEffect, useState } from 'react'
import { LangTabs, type CLocale } from '@/components/contracts/shared'
import { previewSponsorTerms } from '@/lib/admin-api'

type Preview = Awaited<ReturnType<typeof previewSponsorTerms>>

/**
 * Preview — what a sponsor will actually read.
 *
 * Served by the same `sponsor_terms.document()` the sponsor-facing page will call in T3, so the
 * preview cannot drift from the real thing. Blank lines become paragraphs, exactly as the sponsor
 * will see them; the checkpoints are listed underneath so the whole experience is reviewable in
 * one place before publishing.
 */
export default function PreviewTab({ id, token, t }: {
  id: number
  token: string
  t: (k: string, p?: Record<string, string>) => string
}) {
  const [lang, setLang] = useState<CLocale>('en')
  const [data, setData] = useState<Preview | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    setError('')
    previewSponsorTerms(id, lang, { token })
      .then(setData)
      .catch(() => setError(t('admin.sponsors.terms.loadError')))
  }, [id, lang, token, t])

  useEffect(() => { load() }, [load])

  if (error) return <p className="text-sm text-red-600">{error}</p>
  if (!data) return <p className="text-sm text-gray-500">{t('common.loading')}</p>

  const doc = data.document

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-gray-500">{t('admin.sponsors.terms.previewIntro')}</p>
        <LangTabs value={lang} onChange={setLang} />
      </div>

      {doc.locale_used !== lang && (
        // Honest rather than silent: a half-translated version is served whole in English, and the
        // reviewer needs to know that is what a sponsor would get.
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          {t('admin.sponsors.terms.previewFallback', { loc: lang.toUpperCase() })}
        </p>
      )}

      <article className="bg-white border border-gray-200 rounded-xl p-6 max-w-2xl">
        <h3 className="text-xl font-bold text-gray-900 mb-2">{doc.title || '—'}</h3>
        {doc.intro && <p className="text-gray-600 italic mb-6">{doc.intro}</p>}
        <div className="flex flex-col gap-5">
          {doc.sections.map((s) => (
            <section key={s.order}>
              <h4 className="font-semibold text-gray-900">
                <span className="font-mono text-xs text-gray-400 mr-2">{s.order}</span>
                {s.heading}
                {s.has_quiz && (
                  <span className="ml-2 text-[10px] uppercase tracking-wider text-blue-600 bg-blue-50 rounded px-1.5 py-0.5">
                    {t('admin.sponsors.terms.tab.quiz')}
                  </span>
                )}
              </h4>
              {s.body.split('\n\n').map((para, pi) => (
                <p key={pi} className="text-gray-700 mt-1.5 whitespace-pre-wrap">{para}</p>
              ))}
            </section>
          ))}
        </div>
      </article>

      {data.checkpoints.length > 0 && (
        <div className="max-w-2xl flex flex-col gap-3">
          <h4 className="text-sm font-semibold text-gray-800">
            {t('admin.sponsors.terms.checkpointCount', { n: String(data.checkpoints.length) })}
          </h4>
          {data.checkpoints.map((c) => (
            <div key={c.order} className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <p className="text-[11px] uppercase tracking-wider text-gray-500">{c.tag}</p>
              <p className="text-sm font-medium text-gray-900 mt-1">{c.question}</p>
              <ul className="mt-2 flex flex-col gap-1">
                {(c.options || []).map((o, oi) => (
                  <li key={oi} className={`text-sm ${
                    oi === c.correct ? 'text-green-700 font-medium' : 'text-gray-600'}`}>
                    {oi === c.correct ? '✓ ' : '· '}{o}
                  </li>
                ))}
              </ul>
              {c.why && <p className="text-xs text-gray-500 mt-2">{c.why}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
