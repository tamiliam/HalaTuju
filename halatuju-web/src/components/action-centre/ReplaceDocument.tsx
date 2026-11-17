'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import {
  recordDocument, signUploadDocument, uploadFileToSignedUrl,
  type ApplicantDocument, type DocumentLimits,
} from '@/lib/api'
import { replaceLimitKey, replaceRefusalText, replacesLeft } from '@/lib/documentReplace'
import { UploadButtons } from './UploadButtons'

/**
 * H6: the file a student has sent, with Replace (and Take a photo) beneath it, for a Sent or Done
 * document. Goes through the same sign, upload and record calls as a normal upload (the record's
 * `replace: true` is only a hint: the server counts every upload into the slot, 3 replaces after the
 * first). Replace is hidden by the caller once documents are locked; with no replaces left (the served
 * `replaces_left`) it gives way to one plain line. The server is the judge: a 409
 * `replace_limit_reached` or `documents_locked` shows its own message (shut before consent,
 * body code `replace_limit_support`, the support line in her own language).
 */
export function ReplaceDocument({ doc, requestCode = '', member, token, limits, onDone }: {
  doc: ApplicantDocument
  requestCode?: string
  member?: string   // an officer request's own member: its slot is (code, member), which the server checks
  token: string | null
  limits?: DocumentLimits | null
  onDone: () => void
}) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const left = replacesLeft(doc)

  const onFile = async (file: File) => {
    const refusal = await import(/* webpackChunkName: 'mi' */ '@/lib/uploadCheck').then((m) => m.refusalFor(file, limits), () => null)
    if (!token || refusal) { setError(refusal ? t(refusal.key, refusal.params) : null); return }
    setBusy(true); setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(doc.doc_type, { token })
      await uploadFileToSignedUrl(upload_url, file)
      await recordDocument(
        { doc_type: doc.doc_type, household_member: member ?? doc.household_member, request_code: requestCode, replace: true,
          storage_path, original_filename: file.name, content_type: file.type, size: file.size },
        { token },
      )
      onDone()
    } catch (e) {
      const code = (e as { code?: string })?.code
      if (code === 'documents_locked' || code === 'replace_limit_reached') onDone()   // the list redraws without Replace
      setError(
        code === 'documents_locked' || code === 'replace_limit_reached'
          ? (code === 'replace_limit_reached' ? replaceRefusalText(e, t) : ((e as Error).message || t('scholarship.actionCentre.replaceLimit')))
        : code === 'unsupported_format' || code === 'upload_incomplete' || code === 'bad_file'
          ? t('scholarship.actionCentre.badFile')
        : code === 'file_too_large' ? t('scholarship.docs.file_too_large',
            { mb: String((e as { fieldErrors?: { max_mb?: number } })?.fieldErrors?.max_mb ?? limits?.max_doc_size_mb ?? 8) })
        : t('scholarship.actionCentre.uploadError'),
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-3">
      {doc.original_filename && (
        <p className="break-all rounded-lg bg-ground-50 px-3 py-2 text-sm text-ground-700">{doc.original_filename}</p>
      )}
      {left > 0 ? (
        <div className="mt-2">
          <UploadButtons busy={busy} onFile={onFile} uploadKey="scholarship.actionCentre.replace" />
          <p className="mt-2 text-sm text-ground-600">
            {t(left === 1 ? 'scholarship.actionCentre.replacesLeftOne' : 'scholarship.actionCentre.replacesLeft', { n: String(left) })}
          </p>
        </div>
      ) : (
        <p className="mt-2 text-sm text-ground-600">{t(replaceLimitKey(doc))}</p>
      )}
      {error && <p role="alert" className="mt-2 text-sm text-critical-600">{error}</p>}
    </div>
  )
}
