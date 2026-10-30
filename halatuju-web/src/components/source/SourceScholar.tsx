'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { statusLabelKey } from '@/lib/applicationStatus'
import { useT } from '@/lib/i18n'
import RecordState from '@/components/admin/RecordState'
import { getSourceScholar, type SourceScholar as Payload } from '@/lib/admin-api'
import { FactsCard, Footnote, K, PageTitle, SourceContractCard } from './shared'

/**
 * One scholar, as their source sees them (source sign-in S3): the list row plus phone and email
 * (owner ruling) and the contract. NO money, payments or results — the server sends none.
 */
export default function SourceScholar({ id }: { id: string }) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [data, setData] = useState<Payload | null>(null)
  const [missing, setMissing] = useState(false)

  useEffect(() => {
    if (!token || !id) return
    getSourceScholar(id, { token }).then(setData).catch(() => setMissing(true))
  }, [token, id])

  if (!data) return <RecordState loading={!missing} />

  return (
    <div data-testid="source-scholar">
      <Link href="/admin/scholars" className="mb-3 inline-block text-sm text-primary-600 hover:underline">
        ← {t('admin.scholars.nav')}
      </Link>
      <PageTitle title={data.student_name} />
      <FactsCard title={t(`${K}.scholars.details`)} testId="scholar-details" rows={[
        [t(`${K}.student.programme`), data.programme?.name ?? ''],
        [t(`${K}.scholars.col.institution`), data.institution],
        [t(`${K}.scholars.col.course`), data.course],
        [t(`${K}.scholars.col.status`), t(statusLabelKey(data.status))],
        [t(`${K}.student.phone`), data.phone],
        [t(`${K}.student.email`), data.email],
      ]} />
      <div className="mt-4">
        <SourceContractCard applicationId={data.id} contract={data.contract} t={t} />
      </div>
      <Footnote>{t(`${K}.scholars.footnote`)}</Footnote>
    </div>
  )
}
