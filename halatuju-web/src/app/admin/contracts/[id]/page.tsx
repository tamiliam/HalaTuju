'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAdminAuth } from '@/lib/admin-auth-context'
import { useT } from '@/lib/i18n'
import { getContractTemplate, type ContractTemplateDetail, type ContractStatus } from '@/lib/admin-api'
import ConfigForm from '@/components/contracts/ConfigForm'
import ClauseEditor from '@/components/contracts/ClauseEditor'
import QuizEditor from '@/components/contracts/QuizEditor'
import ScheduleEditor from '@/components/contracts/ScheduleEditor'
import TemplatePreview from '@/components/contracts/TemplatePreview'
import DeployPanel from '@/components/contracts/DeployPanel'

const TABS = ['config', 'clauses', 'quiz', 'schedule', 'preview', 'deploy'] as const
type Tab = typeof TABS[number]

const STATUS_TONE: Record<ContractStatus, string> = {
  draft: 'bg-gray-100 text-gray-600',
  pending_deployment: 'bg-amber-100 text-amber-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-slate-100 text-slate-500',
}

export default function ContractEditorPage() {
  const params = useParams()
  const templateId = Number(params?.id)
  const { token, role } = useAdminAuth()
  const { t } = useT()
  const router = useRouter()

  const isSuper = !!(role?.is_super_admin || role?.role === 'super')
  const [tpl, setTpl] = useState<ContractTemplateDetail | null>(null)
  const [tab, setTab] = useState<Tab>('config')
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  const reload = useCallback(async () => {
    if (!token) return
    const d = await getContractTemplate(templateId, { token })
    setTpl(d)
  }, [token, templateId])

  useEffect(() => {
    if (!token) return
    getContractTemplate(templateId, { token })
      .then(setTpl).catch(() => setNotFound(true)).finally(() => setLoading(false))
  }, [token, templateId])

  if (loading) return <p className="text-gray-400">{t('admin.contracts.loading')}</p>
  if (notFound || !tpl) return <p className="text-red-600">{t('admin.contracts.actionFailed')}</p>

  const shared = { template: tpl, token: token!, onChange: setTpl }

  return (
    <div className="max-w-5xl font-plex">
      <button type="button" onClick={() => router.push('/admin/contracts')}
        className="text-sm text-blue-600 hover:text-blue-800">{t('admin.contracts.backToList')}</button>

      <div className="flex items-center gap-3 mt-2 mb-1">
        <h1 className="text-2xl font-bold text-gray-900">{tpl.version}</h1>
        <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${STATUS_TONE[tpl.status]}`}>
          {t(`admin.contracts.status.${tpl.status}`)}
        </span>
        <span className="text-xs text-gray-400 uppercase">{tpl.organisation}</span>
      </div>

      <div className="border-b border-gray-200 mb-6 flex gap-1 overflow-x-auto">
        {TABS.map((tb) => (
          <button key={tb} type="button" onClick={() => setTab(tb)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${
              tab === tb ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-800'}`}>
            {t(`admin.contracts.tab.${tb}`)}
          </button>
        ))}
      </div>

      {tab === 'config' && <ConfigForm {...shared} />}
      {tab === 'clauses' && <ClauseEditor {...shared} />}
      {tab === 'quiz' && <QuizEditor {...shared} />}
      {tab === 'schedule' && <ScheduleEditor {...shared} />}
      {tab === 'preview' && <TemplatePreview template={tpl} token={token!} />}
      {tab === 'deploy' && <DeployPanel {...shared} isSuper={isSuper} reload={reload} />}
    </div>
  )
}
