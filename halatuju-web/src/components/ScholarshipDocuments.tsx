'use client'

import { useState, useEffect, useCallback } from 'react'
import { useT } from '@/lib/i18n'
import {
  signUploadDocument,
  uploadFileToSignedUrl,
  recordDocument,
  listDocuments,
  deleteDocument,
  type ApplicantDocument,
} from '@/lib/api'
import { DOC_TYPES, formatFileSize } from '@/lib/scholarship'

export default function ScholarshipDocuments({ token }: { token: string | null }) {
  const { t } = useT()
  const [docs, setDocs] = useState<ApplicantDocument[]>([])
  const [busyType, setBusyType] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const r = await listDocuments({ token })
      setDocs(r.documents)
    } catch { /* ignore */ }
  }, [token])

  useEffect(() => { refresh() }, [refresh])

  const handleUpload = async (docType: string, file: File) => {
    if (!token) return
    setBusyType(docType)
    setError(null)
    try {
      const { upload_url, storage_path } = await signUploadDocument(docType, { token })
      await uploadFileToSignedUrl(upload_url, file)
      await recordDocument({
        doc_type: docType, storage_path,
        original_filename: file.name, content_type: file.type, size: file.size,
      }, { token })
      await refresh()
    } catch {
      setError(t('scholarship.docs.uploadError'))
    } finally {
      setBusyType(null)
    }
  }

  const handleDelete = async (id: number) => {
    if (!token) return
    try {
      await deleteDocument(id, { token })
      await refresh()
    } catch {
      setError(t('scholarship.docs.deleteError'))
    }
  }

  return (
    <div className="space-y-3">
      {DOC_TYPES.map((dt) => {
        const existing = docs.filter((d) => d.doc_type === dt)
        return (
          <div key={dt} className="border rounded-lg p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-gray-800">{t(`scholarship.docs.type.${dt}`)}</span>
              <label className="text-sm text-primary-600 cursor-pointer hover:underline">
                {busyType === dt ? t('scholarship.docs.uploading') : t('scholarship.docs.choose')}
                <input
                  type="file" className="hidden" disabled={busyType === dt}
                  onChange={(e) => {
                    const f = e.target.files?.[0]
                    if (f) handleUpload(dt, f)
                    e.target.value = ''
                  }}
                />
              </label>
            </div>
            {existing.length > 0 && (
              <ul className="mt-2 space-y-1">
                {existing.map((d) => (
                  <li key={d.id} className="flex items-center justify-between text-sm text-gray-600">
                    <span className="truncate">
                      {d.download_url ? (
                        <a href={d.download_url} target="_blank" rel="noreferrer" className="text-primary-600 hover:underline">
                          {d.original_filename || d.doc_type}
                        </a>
                      ) : (d.original_filename || d.doc_type)}
                      {d.size ? <span className="text-gray-400"> · {formatFileSize(d.size)}</span> : null}
                    </span>
                    <button onClick={() => handleDelete(d.id)} className="text-red-500 hover:underline ml-2">
                      {t('scholarship.docs.remove')}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
      {error && <p className="text-red-600 text-sm">{error}</p>}
    </div>
  )
}
