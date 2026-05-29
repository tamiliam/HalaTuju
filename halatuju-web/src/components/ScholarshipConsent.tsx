'use client'

import { useState, useEffect, useMemo } from 'react'
import { useT } from '@/lib/i18n'
import {
  getConsentStatus, recordConsent, listDocuments,
  type ApplicantDocument, type ConsentStatus,
} from '@/lib/api'
import Toggle from '@/components/Toggle'
import FieldLabel from '@/components/FieldLabel'
import { formatNric } from '@/lib/scholarship'

/** S19 — the 7 structured codes that match Consent.GUARDIAN_RELATIONSHIPS on
 *  the backend. `father` / `mother` skip the guardianship-letter requirement;
 *  everything else needs it. */
const GUARDIAN_RELATIONSHIPS = [
  'father', 'mother', 'legal_guardian', 'grandparent', 'brother', 'sister', 'relative',
] as const
type GuardianRelationship = typeof GUARDIAN_RELATIONSHIPS[number]
const PARENT_RELATIONSHIPS = new Set<GuardianRelationship>(['father', 'mother'])

/** Digits-only canonical form for NRIC comparison (matches backend nric_match). */
const canonicalNric = (s: string): string => s.replace(/\D/g, '')

/** Lowercase token set for name comparison (matches backend name_match). Strips
 *  Malaysian parentage tokens so "PRIYA A/P KRISHNAN" == "PRIYA KRISHNAN". */
const NAME_NOISE = /\b(bin|binti|a\/l|a\/p|al|ap|d\/o|s\/o|@)\b/gi
const canonicalNameTokens = (s: string): Set<string> => {
  if (!s) return new Set()
  return new Set(s.toLowerCase().replace(NAME_NOISE, ' ').split(/[^a-z]+/).filter(Boolean))
}
const nameSetsMatch = (a: string, b: string): boolean => {
  const sa = canonicalNameTokens(a)
  const sb = canonicalNameTokens(b)
  if (sa.size === 0 || sb.size === 0) return false
  if (sa.size !== sb.size) return false
  // Avoid Set iteration (downlevel target issue in this project's tsconfig);
  // Array.from gives a plain string[] which iterates cleanly.
  return Array.from(sa).every((t) => sb.has(t))
}

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
  const [guardianNric, setGuardianNric] = useState('')
  const [relationship, setRelationship] = useState<GuardianRelationship | ''>('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    getConsentStatus({ token }).then(setStatus).catch(() => { /* ignore */ })
    listDocuments({ token }).then((d) => setDocuments(d.documents || [])).catch(() => { /* ignore */ })
  }, [token])

  const isMinor = !!status?.is_minor
  const hasActive = !!status?.consents?.some((c) => c.is_active)
  const hasParentIc = documents.some((d) => d.doc_type === 'parent_ic')
  const hasGuardianshipLetter = documents.some((d) => d.doc_type === 'guardianship_letter')
  const needsLetter = isMinor && relationship !== '' && !PARENT_RELATIONSHIPS.has(relationship)

  // S19 — live mismatch check against parent_ic Vision OCR values from the
  // status payload. Empty strings when OCR hasn't run / IC not uploaded yet.
  const ocrNric = status?.parent_ic_vision_nric || ''
  const ocrName = status?.parent_ic_vision_name || ''
  const typedNricCanonical = canonicalNric(guardianNric)
  const ocrNricCanonical = canonicalNric(ocrNric)
  const nricMismatch = !!ocrNricCanonical && !!typedNricCanonical && ocrNricCanonical !== typedNricCanonical
  const nameMismatch = !!ocrName && !!guardianName.trim() && !nameSetsMatch(ocrName, guardianName)

  // S19 — parent-voice consent text interpolation. The student's name + NRIC
  // are dropped into the (lawyer-reviewed) template; the pronoun is derived
  // from the NRIC's last digit (odd = male → he/his, even = female → she/her;
  // unparseable falls back to neutral they/their).
  const consentBody = useMemo(() => {
    const studentName = status?.student_name || t('scholarship.consent.fallback.student')
    const studentNric = status?.student_nric || ''
    const gender = status?.student_gender || ''
    const pronounSubject = gender === 'male'
      ? t('scholarship.consent.pronoun.he')
      : gender === 'female'
        ? t('scholarship.consent.pronoun.she')
        : t('scholarship.consent.pronoun.they')
    const pronounPossessive = gender === 'male'
      ? t('scholarship.consent.pronoun.his')
      : gender === 'female'
        ? t('scholarship.consent.pronoun.her')
        : t('scholarship.consent.pronoun.their')
    return t(isMinor ? 'scholarship.consent.textMinor' : 'scholarship.consent.text', {
      student_name: studentName,
      student_nric: studentNric,
      he_or_she: pronounSubject,
      his_or_her: pronounPossessive,
    })
  }, [isMinor, status, t])

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
        guardian_nric: isMinor ? guardianNric : '',
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

  const adultIncomplete = !checked
  const minorIncomplete =
    !checked || !guardianName.trim() || !guardianNric.trim() || !relationship
    || !hasParentIc || (needsLetter && !hasGuardianshipLetter)
    || nricMismatch || nameMismatch
  const submitDisabled = saving || (isMinor ? minorIncomplete : adultIncomplete)

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      {/* Section subtitle — student vs parent voice */}
      <p className="text-sm text-gray-700">
        {isMinor
          ? t('scholarship.consent.subtitleMinor', { student_name: status?.student_name || '' })
          : t('scholarship.consent.subtitle')}
      </p>

      {/* Consent text body — voice + content differ for minors */}
      <div className="bg-gray-50 border rounded-lg p-3 text-sm text-gray-700 max-h-48 overflow-y-auto whitespace-pre-line">
        {consentBody}
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
            {hasParentIc && nameMismatch && (
              <p className="mt-1 text-xs text-red-600">
                {t('scholarship.consent.nameMismatch')}
              </p>
            )}
          </div>

          {/* Guardian NRIC */}
          <div>
            <FieldLabel required>{t('scholarship.consent.guardianNric')}</FieldLabel>
            <input
              className="input font-mono"
              placeholder="XXXXXX-XX-XXXX"
              inputMode="numeric"
              autoComplete="off"
              value={guardianNric}
              onChange={(e) => setGuardianNric(formatNric(e.target.value))}
            />
            {hasParentIc && nricMismatch && (
              <p className="mt-1 text-xs text-red-600">
                {t('scholarship.consent.nricMismatch')}
              </p>
            )}
          </div>

          {/* Relationship dropdown — 7 options (no "Other") */}
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

          {/* Prerequisite-doc warnings — point the student back to Documents step */}
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

      {/* Toggle attestation — adult vs guardian voice */}
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
