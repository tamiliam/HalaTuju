'use client'

import { useState, useEffect } from 'react'
import { useT } from '@/lib/i18n'
import {
  getConsentStatus, recordConsent, listDocuments,
  type ApplicantDocument, type ConsentStatus,
} from '@/lib/api'
import Toggle from '@/components/Toggle'
import FieldLabel from '@/components/FieldLabel'

/** S17 — the 5 structured codes that match Consent.GUARDIAN_RELATIONSHIPS on
 *  the backend. Kept inline (no shared module) because this is the only FE
 *  surface that uses them. `father` / `mother` skip the guardianship-letter
 *  requirement; everything else needs it. */
const GUARDIAN_RELATIONSHIPS = [
  'father', 'mother', 'legal_guardian', 'grandparent', 'older_sibling', 'other_relative',
] as const
type GuardianRelationship = typeof GUARDIAN_RELATIONSHIPS[number]
const PARENT_RELATIONSHIPS = new Set<GuardianRelationship>(['father', 'mother'])

export default function ScholarshipConsent({
  token,
  locale,
}: {
  token: string | null
  locale: string
}) {
  const { t } = useT()
  const [status, setStatus] = useState<ConsentStatus | null>(null)
  const [documents, setDocuments] = useState<ApplicantDocument[]>([])
  const [checked, setChecked] = useState(false)
  const [guardianName, setGuardianName] = useState('')
  const [relationship, setRelationship] = useState<GuardianRelationship | ''>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getConsentStatus({ token }).then(setStatus).catch(() => { /* ignore */ })
    // S17: we read the docs list here too so we can warn when the parent_ic /
    // guardianship_letter prerequisites aren't satisfied. Re-fetched if the
    // student uploads docs in step 4 then comes back; the form blurs/re-renders
    // before submit anyway, but worth refreshing on mount.
    listDocuments({ token }).then((d) => setDocuments(d.documents || [])).catch(() => { /* ignore */ })
  }, [token])

  const isMinor = !!status?.is_minor
  const hasActive = !!status?.consents?.some((c) => c.is_active)
  const hasParentIc = documents.some((d) => d.doc_type === 'parent_ic')
  const hasGuardianshipLetter = documents.some((d) => d.doc_type === 'guardianship_letter')
  const needsLetter = isMinor && relationship !== '' && !PARENT_RELATIONSHIPS.has(relationship)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token) return
    setSaving(true)
    setError(null)
    try {
      await recordConsent({
        locale,
        granted_by: isMinor ? 'guardian' : 'self',
        guardian_name: isMinor ? guardianName : '',
        guardian_relationship: isMinor ? (relationship || '') : '',
      }, { token })
      setStatus(await getConsentStatus({ token }))
    } catch {
      setError(t('scholarship.consent.error'))
    } finally {
      setSaving(false)
    }
  }

  if (hasActive) {
    return <p className="text-green-700 text-sm">{t('scholarship.consent.given')}</p>
  }

  // Adult-only fields are blocked when the toggle is off; minor adds: relationship
  // picked + guardian name typed + the prerequisite doc(s) uploaded.
  const adultIncomplete = !checked
  const minorIncomplete =
    !checked || !guardianName.trim() || !relationship
    || !hasParentIc || (needsLetter && !hasGuardianshipLetter)
  const submitDisabled = saving || (isMinor ? minorIncomplete : adultIncomplete)

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Consent text body — voice differs for minors */}
      <div className="bg-gray-50 border rounded-lg p-3 text-sm text-gray-700 max-h-48 overflow-y-auto">
        <p className="text-xs font-medium text-amber-700 mb-1">{t('scholarship.consent.draftNotice')}</p>
        {t(isMinor ? 'scholarship.consent.textMinor' : 'scholarship.consent.text')}
      </div>

      {isMinor && (
        <>
          <p className="text-sm text-gray-700">{t('scholarship.consent.guardianNotice')}</p>

          {/* Guardian name */}
          <div>
            <FieldLabel required>{t('scholarship.consent.guardianName')}</FieldLabel>
            <input
              className="input"
              placeholder={t('scholarship.consent.guardianNamePlaceholder')}
              value={guardianName}
              onChange={(e) => setGuardianName(e.target.value)}
            />
          </div>

          {/* Relationship dropdown (replaces free text) */}
          <div>
            <FieldLabel required>{t('scholarship.consent.guardianRelationship')}</FieldLabel>
            <select
              className="input"
              value={relationship}
              onChange={(e) => setRelationship(e.target.value as GuardianRelationship | '')}
            >
              <option value="">{t('scholarship.consent.relationshipPlaceholder')}</option>
              {GUARDIAN_RELATIONSHIPS.map((r) => (
                <option key={r} value={r}>
                  {t(`scholarship.consent.relationship.${r}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Prerequisite-doc warnings — point the student back to Documents step. */}
          {!hasParentIc && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {t('scholarship.consent.needParentIc')}
            </div>
          )}
          {needsLetter && !hasGuardianshipLetter && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
              {t('scholarship.consent.needGuardianshipLetter')}
            </div>
          )}
        </>
      )}

      {/* Toggle attestation — label switches for adult vs guardian voice */}
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm text-gray-700">
          {isMinor ? t('scholarship.consent.agreeGuardian') : t('scholarship.consent.agree')}
        </span>
        <Toggle
          on={checked}
          onChange={setChecked}
          label={isMinor ? t('scholarship.consent.agreeGuardian') : t('scholarship.consent.agree')}
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button type="submit" disabled={submitDisabled}
        className="btn-primary disabled:opacity-50">
        {saving ? t('scholarship.consent.saving') : t('scholarship.consent.submit')}
      </button>
    </form>
  )
}
