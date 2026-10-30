'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'

import { useAdminAuth } from '@/lib/admin-auth-context'
import { formatDate } from '@/lib/formatDate'
import { useT } from '@/lib/i18n'
import { levelLabelKey, partLabel, stageLabelKey } from '@/lib/sourceConsole'
import RecordState from '@/components/admin/RecordState'
import SourceWitness from './SourceWitness'
import { getSourceApplication, type SourceApplication } from '@/lib/admin-api'
import { FactsCard, Footnote, K, PageTitle, SourceContractCard, StageBadge } from './shared'

/**
 * One student, as a source sees them (source sign-in S3 + S4) — where the witness email's link
 * (`/admin/scholarship/<id>`) lands.
 *
 * A LISTED application (its student named this source): Profile (school, state, level, phone,
 * email — owner ruling), Application (gift, sent, stage with the date the student was told, the
 * names of the parts still missing) and the contract. A case this source only WITNESSES
 * (`witness_only`, another source's student, C14): the name, the gift and the contract — nothing
 * else. Out of scope is a 404, shown neutrally by `RecordState`.
 *
 * ⚠ THE WITNESS STEP IS IN THIS PAGE (`?step=witness`, read on arrival — the Overview's and the
 * Scholars' links carry it): "Review and witness" opens it in place and Back returns, re-reading the
 * application so the contract card shows what the witness changed. The address keeps the step, so
 * a reload stays on it.
 */
export default function SourceStudent({ id }: { id: string }) {
  const { token } = useAdminAuth()
  const { t } = useT()
  const [app, setApp] = useState<SourceApplication | null>(null)
  const [missing, setMissing] = useState(false)
  const [witnessing, setWitnessing] = useState(false)
  const [reads, setReads] = useState(0)

  // `?step=witness` (the Overview's and the Scholars' "witness" links) opens the step on arrival.
  useEffect(() => {
    setWitnessing(new URLSearchParams(window.location.search).get('step') === 'witness')
  }, [])

  useEffect(() => {
    if (!token || !id) return
    getSourceApplication(id, { token }).then(setApp).catch(() => setMissing(true))
  }, [token, id, reads])

  const step = (on: boolean) => {
    setWitnessing(on)
    window.history.replaceState(null, '', `${window.location.pathname}${on ? '?step=witness' : ''}`)
    if (!on) setReads((n) => n + 1)
  }

  // The step waits for the application, so a witness-only case is worded as one from the start.
  if (witnessing) {
    if (!app && !missing) return <RecordState loading />
    return <SourceWitness id={id} witnessOnly={app?.kind === 'witness_only'}
      onBack={() => step(false)} onChanged={() => setReads((n) => n + 1)} />
  }
  if (!app) return <RecordState loading={!missing} />

  const back = (
    <Link href="/admin/scholarship" className="mb-3 inline-block text-sm text-primary-600 hover:underline">
      ← {t('admin.scholarship.nav')}
    </Link>
  )

  if (app.kind === 'witness_only') {
    return (
      <div data-testid="source-student">
        {back}
        <PageTitle title={app.student_name} subtitle={t(`${K}.student.witnessOnly`)} />
        <div className="space-y-4">
          <FactsCard title={t(`${K}.student.application`)}
            rows={[[t(`${K}.student.programme`), app.programme?.name ?? '']]} />
          <SourceContractCard applicationId={app.id} contract={app.contract} t={t} onWitness={() => step(true)} />
        </div>
      </div>
    )
  }

  const stage = t(stageLabelKey(app.stage))
  return (
    <div data-testid="source-student">
      {back}
      <PageTitle title={app.student_name}><StageBadge stage={app.stage} t={t} /></PageTitle>
      <div className="grid gap-4 md:grid-cols-2">
        <FactsCard title={t(`${K}.student.profile`)} testId="student-profile" rows={[
          [t(`${K}.student.school`), app.school],
          [t(`${K}.student.state`), app.state],
          [t(`${K}.student.level`), t(levelLabelKey(app.level))],
          [t(`${K}.student.phone`), app.phone],
          [t(`${K}.student.email`), app.email],
        ]} />
        <FactsCard title={t(`${K}.student.application`)} testId="student-application" rows={[
          [t(`${K}.student.programme`), app.programme?.name ?? ''],
          [t(`${K}.student.sent`), formatDate(app.submitted_at)],
          [t(`${K}.student.stage`), app.told_at
            ? t(`${K}.student.toldOn`, { stage, date: formatDate(app.told_at) }) : stage],
          [t(`${K}.student.missing`), app.missing_items.length
            ? app.missing_items.map((p) => partLabel(t, p)).join(', ') : t(`${K}.student.none`)],
        ]} />
      </div>
      <div className="mt-4">
        <SourceContractCard applicationId={app.id} contract={app.contract} t={t} onWitness={() => step(true)} />
      </div>
      <Footnote>{t(`${K}.student.footnote`)}</Footnote>
    </div>
  )
}
