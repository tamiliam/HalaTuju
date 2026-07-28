'use client'

import { updatePartnerEmail, type PartnerEmailTemplate } from '@/lib/admin-api'
import { errorKey } from '@/lib/partnerComms'
import TemplateEditor from '@/components/emails/TemplateEditor'

// The partner family's binding of the shared editor (generalised 2026-07-28 when sponsor comms
// became the second family). All that is family-specific is the endpoint, the error mapper and
// the i18n prefix — the editor itself now lives in components/emails/TemplateEditor.

export default function PartnerTemplateEditor({
  template, token, onSaved, onCancel, t,
}: {
  template: PartnerEmailTemplate
  token: string | null
  onSaved: (updated: PartnerEmailTemplate) => void
  onCancel: () => void
  t: (key: string, params?: Record<string, string>) => string
}) {
  return (
    <TemplateEditor<PartnerEmailTemplate>
      template={template}
      prefix="admin.sources.emails"
      onSave={(kind, patch) => updatePartnerEmail(kind, patch, { token: token! })}
      errorKey={errorKey}
      onSaved={onSaved}
      onCancel={onCancel}
      t={t}
    />
  )
}
