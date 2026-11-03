'use client'

import { useEffect, useState } from 'react'
import { useT } from '@/lib/i18n'
import { getScholarGrowth, taskFileLink, type WorkRow } from '@/lib/admin-api/development'
import GrowthWork from '@/components/development/GrowthWork'
import { openSigned } from '@/components/development/shared'

const K = 'admin.scholars.growth'

/**
 * The scholar file's **Growth** tab (student maintenance S10): each development module this scholar can see or
 * started, with their work (lessons read, the task, the review, "Late"). Read-only; the review is on the module's
 * Progress page.
 *
 * ⚠ THE SERVER'S FENCE: the file's own (`_file_for`) AND the module makers' roles (super, org_admin, admin); the
 * page draws the tab only for them. An uploaded task opens through a short signed link fetched on the tap. Its
 * own chunk, fetched the first time the tab is opened.
 */
export default function ScholarGrowth({ id, token }: { id: number; token: string | null }) {
  const { t } = useT()
  const [rows, setRows] = useState<WorkRow[] | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    if (!token) return
    let live = true
    getScholarGrowth(id, { token })
      .then((d) => { if (live) { setRows(d.modules); setFailed(false) } })
      .catch(() => { if (live) setFailed(true) })
    return () => { live = false }
  }, [id, token])

  const openFile = (row: WorkRow) => openSigned(() => taskFileLink(row.id, id, { token: token ?? undefined }), () => setFailed(true))

  if (failed) return <p className="text-sm text-critical-600" role="alert">{t(`${K}.loadError`)}</p>
  if (!rows) return <p className="text-sm text-ground-500">{t('common.loading')}</p>
  return (
    <section className="md:rounded-xl md:border md:border-ground-200 md:bg-ground-0 md:px-5 py-2" data-testid="scholar-growth">
      <GrowthWork rows={rows} t={t} openFile={openFile} progressLinks />
    </section>
  )
}
