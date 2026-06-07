'use client'

/**
 * Student Action Centre (Sprint 4 of the verification-verdict roadmap).
 *
 * A friendly, self-service "things to finish" queue shown at the TOP of the
 * post-shortlist /application page. It consumes the resolution-ticket endpoints
 * and lets a student clear each gap in place:
 *   doc         → upload the named document
 *   explanation → type a short reply
 *   confirm     → jump to the right section to re-check a fact
 *
 * Pure logic lives in lib/actionCentre.ts (unit-tested). This file is just the
 * presentation + the three resolve flows.
 */

import { useEffect, useState, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  getResolutionItems,
  resolveResolutionItem,
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  type ResolutionItem,
} from '@/lib/api'
import {
  computeProgress,
  iconFor,
  titleSourceFor,
  confirmTargetFor,
  localiseParams,
  sortByWeight,
  type ActionIcon,
  type ConfirmTarget,
} from '@/lib/actionCentre'

// ── Icons (inline SVG, blue circle bg set by the caller) ──────────────────

function KindIcon({ icon }: { icon: ActionIcon }) {
  const paths: Record<ActionIcon, string> = {
    document: 'M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z',
    checklist: 'M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7l2 2 4-4',
    chat: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z',
  }
  return (
    <svg className="h-5 w-5 text-white" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" d={paths[icon]} />
    </svg>
  )
}

function GraduationCap() {
  return (
    <svg className="h-5 w-5 text-white" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
      <path d="M12 3L1 9l11 6 9-4.91V17h2V9L12 3zM5 13.18v4L12 21l7-3.82v-4L12 17l-7-3.82z" />
    </svg>
  )
}

// ── Per-ticket card ───────────────────────────────────────────────────────

function ActionCard({
  item,
  token,
  onResolved,
  onConfirm,
}: {
  item: ResolutionItem
  token: string | null
  onResolved: () => void
  onConfirm: (target: ConfirmTarget) => void
}) {
  const { t } = useT()
  const src = titleSourceFor(item)
  const tParams = localiseParams(item.params, t)
  const title = src.kind === 'raw' ? src.text : t(src.titleKey, tParams)
  const desc = src.kind === 'i18n' ? t(src.descKey, tParams) : ''

  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [text, setText] = useState('')

  // doc: upload the named doc_type, then re-fetch the tickets.
  const onFile = async (file: File) => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(item.doc_type, { token })
      await uploadFileToSignedUrl(upload_url, file)
      await recordDocument(
        { doc_type: item.doc_type, storage_path, original_filename: file.name, content_type: file.type, size: file.size },
        { token },
      )
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.uploadError'))
    } finally {
      setBusy(false)
    }
  }

  // explanation: POST the typed reply, then re-fetch.
  const onSend = async () => {
    if (!token || !text.trim()) return
    setBusy(true)
    setError(null)
    try {
      await resolveResolutionItem(item.id, text.trim(), { token })
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.sendError'))
    } finally {
      setBusy(false)
    }
  }

  // pathway_confirm: the student answers Yes in place — the backend writes their
  // final chosen pathway (no navigate, no officer).
  const onAffirm = async () => {
    if (!token) return
    setBusy(true)
    setError(null)
    try {
      await resolveResolutionItem(item.id, 'confirmed', { token })
      onResolved()
    } catch {
      setError(t('scholarship.actionCentre.sendError'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-500">
          <KindIcon icon={iconFor(item.kind)} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h3 className="font-semibold text-gray-900">{title}</h3>
            <span className="shrink-0 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-amber-800">
              {t('scholarship.actionCentre.toDo')}
            </span>
          </div>
          {desc && <p className="mt-1 text-sm text-gray-500">{desc}</p>}

          {/* ── Action ─────────────────────────────────────────────── */}
          <div className="mt-4">
            {item.kind === 'doc' && (
              <label className={`block w-full cursor-pointer rounded-xl bg-primary-500 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-primary-600 ${busy ? 'opacity-50' : ''}`}>
                {busy ? t('scholarship.actionCentre.uploading') : t('scholarship.actionCentre.upload')}
                <input
                  type="file"
                  accept="image/*,.pdf"
                  className="hidden"
                  disabled={busy}
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) onFile(f)
                    e.target.value = ''
                  }}
                />
              </label>
            )}

            {(item.kind === 'explanation' || item.kind === 'clarify') && (
              <div className="space-y-2">
                <textarea
                  className="input"
                  rows={3}
                  placeholder={t('scholarship.actionCentre.explanationPlaceholder')}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  disabled={busy}
                />
                <button
                  type="button"
                  onClick={onSend}
                  disabled={busy || !text.trim()}
                  className="w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
                >
                  {busy ? t('scholarship.actionCentre.sending') : t('scholarship.actionCentre.send')}
                </button>
              </div>
            )}

            {item.kind === 'confirm' && item.code === 'pathway_confirm' && (
              <button
                type="button"
                onClick={onAffirm}
                disabled={busy}
                className="w-full rounded-xl bg-primary-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-600 disabled:opacity-50"
              >
                {busy ? t('scholarship.actionCentre.sending') : t('scholarship.actionCentre.confirmPathwayYes')}
              </button>
            )}

            {item.kind === 'confirm' && item.code !== 'pathway_confirm' && (
              <button
                type="button"
                onClick={() => onConfirm(confirmTargetFor(item.fact))}
                className="w-full rounded-xl border border-primary-500 px-4 py-2.5 text-sm font-semibold text-primary-600 transition-colors hover:bg-primary-50"
              >
                {t('scholarship.actionCentre.review')}
              </button>
            )}

            {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────

export default function ActionCentre({
  token,
  studentName,
  onConfirm,
}: {
  token: string | null
  studentName?: string
  /** Send the student to the section that resolves a `confirm` ticket. */
  onConfirm?: (target: ConfirmTarget) => void
}) {
  const { t } = useT()
  const [open, setOpen] = useState<ResolutionItem[]>([])
  const [resolved, setResolved] = useState<ResolutionItem[]>([])
  const [loaded, setLoaded] = useState(false)

  const fetchItems = useCallback(async () => {
    if (!token) return
    try {
      const r = await getResolutionItems({ token })
      setOpen(r.open)
      setResolved(r.resolved)
    } catch {
      // Treat a fetch failure as "nothing to show" — the Action Centre is
      // additive; it must never block the rest of the page.
      setOpen([])
      setResolved([])
    } finally {
      setLoaded(true)
    }
  }, [token])

  useEffect(() => { fetchItems() }, [fetchItems])

  // Don't flash anything until we've checked, and stay invisible when there is
  // genuinely nothing to finish AND nothing was ever raised (a clean applicant
  // shouldn't see an empty "all done" banner with no history).
  if (!loaded) return null
  if (open.length === 0 && resolved.length === 0) return null

  const { done, total, pct } = computeProgress(open, resolved)
  const firstName = (studentName || '').trim().split(/\s+/)[0] || ''

  return (
    <section className="mb-8">
      {/* Header */}
      <h2 className="text-xl font-bold text-gray-900">
        {t('scholarship.actionCentre.title', { name: firstName })}
      </h2>
      <p className="mt-1 text-sm text-gray-600">{t('scholarship.actionCentre.intro')}</p>

      {/* Progress */}
      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-xs font-medium text-gray-500">
          <span>{t('scholarship.actionCentre.progressDone', { done: String(done), total: String(total) })}</span>
          <span>{t('scholarship.actionCentre.percentComplete', { pct: String(pct) })}</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
          <div className="h-full rounded-full bg-primary-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {/* Open tickets — or the all-done banner */}
      {open.length === 0 ? (
        <div className="mt-4 flex items-center gap-3 rounded-2xl border border-green-200 bg-green-50 p-5">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-green-600 text-sm text-white">✓</span>
          <p className="font-medium text-green-900">{t('scholarship.actionCentre.allDone')}</p>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {sortByWeight(open).map((item) => (
            <ActionCard
              key={item.id}
              item={item}
              token={token}
              onResolved={fetchItems}
              onConfirm={(target) => onConfirm?.(target)}
            />
          ))}
        </div>
      )}

      {/* Cikgu Gopal coach bubble */}
      <div className="mt-5 flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary-500">
          <GraduationCap />
        </div>
        <div className="rounded-2xl bg-primary-50 px-4 py-3">
          <p className="text-sm text-gray-700">{t('scholarship.actionCentre.coach')}</p>
        </div>
      </div>
    </section>
  )
}
