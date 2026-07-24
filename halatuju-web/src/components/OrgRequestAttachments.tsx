'use client'

// Screenshot attachments on the Requests DETAIL page (Sprint 15.1). Renders the request's images as
// inline thumbnails (signed URL) with a filename + size caption, and — while the request is
// non-terminal and the caller may act — an add/remove control. Each add runs the sign → PUT → record
// chain (admin-api.uploadOrgRequestAttachment); the server re-gates everything (images-only, ≤5,
// non-terminal, org-fence), so this only decides what to SHOW.
import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { formatFileSize } from '@/lib/scholarship'
import {
  uploadOrgRequestAttachment, deleteOrgRequestAttachment,
  type OrgRequestAttachment, type OrgRequestDetail,
} from '@/lib/admin-api'

const MAX_ATTACHMENTS = 5

export default function OrgRequestAttachments({
  requestId, attachments, editable, token, onChange,
}: {
  requestId: number
  attachments: OrgRequestAttachment[]
  editable: boolean
  token: string | null
  onChange: (req: OrgRequestDetail) => void
}) {
  const { t } = useT()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''   // let the same file be re-picked after a failure
    if (!file || !token) return
    if (attachments.length >= MAX_ATTACHMENTS) {
      setError(t('admin.requests.attachments.limitReached')); return
    }
    setBusy(true); setError('')
    try {
      onChange(await uploadOrgRequestAttachment(requestId, file, { token }))
    } catch {
      setError(t('admin.requests.attachments.uploadFailed'))
    } finally {
      setBusy(false)
    }
  }

  const remove = async (attId: number) => {
    if (!token) return
    setBusy(true); setError('')
    try {
      onChange(await deleteOrgRequestAttachment(requestId, attId, { token }))
    } catch {
      setError(t('admin.requests.attachments.uploadFailed'))
    } finally {
      setBusy(false)
    }
  }

  // Nothing to show and nothing to add → render nothing (keeps the page clean on old requests).
  if (!editable && attachments.length === 0) return null

  return (
    <div className="bg-white rounded-xl border p-5 mb-4">
      <h2 className="text-sm font-semibold text-gray-500 mb-3">{t('admin.requests.attachments.title')}</h2>
      {attachments.length === 0 ? (
        <p className="text-sm text-gray-400">{t('admin.requests.attachments.none')}</p>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {attachments.map((a) => (
            <figure key={a.id} className="border rounded-lg overflow-hidden">
              {a.download_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={a.download_url} alt={a.original_filename}
                  className="w-full h-32 object-cover bg-gray-50" />
              ) : (
                <div className="w-full h-32 bg-gray-100 flex items-center justify-center text-xs text-gray-400">—</div>
              )}
              <figcaption className="p-2 text-xs text-gray-600 truncate" title={a.original_filename}>
                {a.original_filename || t('admin.requests.attachments.image')} · {formatFileSize(a.size)}
              </figcaption>
              {editable && (
                <button type="button" disabled={busy} onClick={() => remove(a.id)}
                  className="w-full text-xs text-red-600 hover:text-red-800 py-1 border-t disabled:opacity-50">
                  {t('admin.requests.attachments.remove')}
                </button>
              )}
            </figure>
          ))}
        </div>
      )}
      {editable && attachments.length < MAX_ATTACHMENTS && (
        <div className="mt-3">
          <label className="inline-block text-sm font-medium text-blue-600 hover:text-blue-800 cursor-pointer">
            {busy ? t('admin.requests.attachments.uploading') : `+ ${t('admin.requests.attachments.add')}`}
            <input type="file" accept="image/*" className="hidden" disabled={busy} onChange={onFile} />
          </label>
          <p className="text-xs text-gray-400 mt-1">{t('admin.requests.attachments.hint')}</p>
        </div>
      )}
      {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
    </div>
  )
}
