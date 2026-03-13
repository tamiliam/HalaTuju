'use client'

import { useState } from 'react'
import { useT } from '@/lib/i18n'
import { getSubjectName } from '@/lib/subjects'

// --- Types matching backend CourseRequirementSerializer output ---

interface ReqItem {
  key: string
  label: string
  value?: number
}

interface OrGroup {
  count: number
  grade: string
  subjects: string[]
}

interface ComplexRequirements {
  or_groups?: OrGroup[]
}

// PISMP subject_group_req: flat array of rule objects
interface SubjectGroupRule {
  min_grade: string
  min_count: number
  subjects: string[]  // empty = any subjects
}

export interface CourseRequirements {
  source_type: string
  general: ReqItem[]
  special: ReqItem[]
  complex_requirements: ComplexRequirements | null
  subject_group_req: SubjectGroupRule[] | null
  merit_cutoff: number | null
  remarks: string
  pismp_languages?: string[]  // e.g. ["Bahasa Cina", "Bahasa Tamil"]
}

// --- Helpers ---

function gradeLabel(grade: string, locale: string): string {
  const map: Record<string, { bm: string; en: string }> = {
    credit: { bm: 'Kredit', en: 'Credit' },
    pass: { bm: 'Lulus', en: 'Pass' },
  }
  const entry = map[grade]
  if (entry) return locale === 'en' ? entry.en : entry.bm
  return grade
}

function requirementDesc(
  count: number,
  grade: string,
  totalSubjects: number,
  locale: string,
): string {
  const g = gradeLabel(grade, locale)
  if (totalSubjects === 0) {
    return locale === 'en'
      ? `${g} or better in any ${count} subject${count > 1 ? 's' : ''}`
      : `${g} atau lebih dalam mana-mana ${count} subjek`
  }
  if (count >= totalSubjects) {
    return locale === 'en'
      ? `${g} or better in all of:`
      : `${g} atau lebih dalam semua:`
  }
  return locale === 'en'
    ? `${g} or better in ${count} of:`
    : `${g} atau lebih dalam ${count} daripada:`
}

// Source type display labels
const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ua: { label: 'Universiti', color: 'bg-purple-100 text-purple-700' },
  poly: { label: 'Polytechnic', color: 'bg-emerald-100 text-emerald-700' },
  kkom: { label: 'Community College', color: 'bg-teal-100 text-teal-700' },
  pismp: { label: 'PISMP', color: 'bg-purple-100 text-purple-700' },
  ILJTM: { label: 'ILJTM', color: 'bg-green-100 text-green-700' },
  ILKBS: { label: 'ILKBS', color: 'bg-lime-100 text-lime-700' },
}

// Language codes that indicate medium-of-instruction variants (PISMP)
const MEDIUM_LANGUAGES: Record<string, { bm: string; en: string }> = {
  BC: { bm: 'Bahasa Cina', en: 'Chinese Language' },
  BT: { bm: 'Bahasa Tamil', en: 'Tamil Language' },
}

/** Extract medium-of-instruction languages from PISMP subject_group_req. */
function extractPismpLanguages(
  rules: SubjectGroupRule[] | null,
): string[] {
  if (!rules) return []
  const langs: string[] = []
  for (const rule of rules) {
    for (const subj of rule.subjects) {
      if (subj in MEDIUM_LANGUAGES && !langs.includes(subj)) {
        langs.push(subj)
      }
    }
  }
  return langs
}

// --- Component ---

export default function RequirementsCard({
  requirements,
}: {
  requirements: CourseRequirements
}) {
  const { locale, t } = useT()
  const hasGeneral = requirements.general.length > 0
  const hasSpecial = requirements.special.length > 0
  const hasComplex = requirements.complex_requirements?.or_groups?.length
  const hasSubjectGroup = Array.isArray(requirements.subject_group_req) && requirements.subject_group_req.length > 0

  // PISMP medium-of-instruction languages: prefer API-provided list, fall back to detection
  const isPismp = requirements.source_type === 'pismp'
  const pismpLangs = isPismp
    ? (requirements.pismp_languages && requirements.pismp_languages.length > 0
      ? requirements.pismp_languages
      : extractPismpLanguages(requirements.subject_group_req))
    : []

  if (!hasGeneral && !hasSpecial && !hasComplex && !hasSubjectGroup) {
    return null
  }

  const sourceInfo = SOURCE_LABELS[requirements.source_type]
  const isTvet = requirements.source_type === 'tvet'

  return (
    <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 pt-5 pb-3 flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
          <svg className="w-[18px] h-[18px] text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {t('courseDetail.requirements')}
        </h2>
        {sourceInfo && (
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${sourceInfo.color}`}>
            {sourceInfo.label}
          </span>
        )}
      </div>

      <div className="px-5 pb-5 space-y-4">
        {/* General Requirements (Syarat Am) */}
        {hasGeneral && (
          <div>
            <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
              {t('courseDetail.generalReq')}
            </h3>
            {isTvet ? (
              // TVET: clean key-value table layout (matches Stitch design)
              <div className="rounded-lg border border-gray-100 divide-y divide-gray-100">
                {requirements.general.map((item) => (
                  <div key={item.key} className="flex justify-between items-center px-3 py-2">
                    <span className="text-xs text-gray-500">{tvetKeyLabel(item.key, locale)}</span>
                    <span className="text-xs font-medium text-gray-800">{tvetValueLabel(item, locale)}</span>
                  </div>
                ))}
              </div>
            ) : (
              // UA/Poly/PISMP: checkmark list
              <div className="space-y-2">
                {requirements.general.map((item) => (
                  <div key={item.key} className="flex items-start gap-2.5">
                    <CheckIcon color="gray" />
                    <span className="text-[13px] text-gray-700 leading-snug">{item.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Special Requirements (Syarat Khas) — simple flags */}
        {hasSpecial && (
          <div>
            <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
              {t('courseDetail.specialReq')}
            </h3>
            {isTvet ? (
              <div className="rounded-lg border border-gray-100 divide-y divide-gray-100">
                {requirements.special.map((item) => (
                  <div key={item.key} className="flex justify-between items-center px-3 py-2">
                    <span className="text-xs text-gray-500">{tvetKeyLabel(item.key, locale)}</span>
                    <span className="text-xs font-medium text-gray-800">{tvetValueLabel(item, locale)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {requirements.special.map((item) => (
                  <div key={item.key} className="flex items-start gap-2.5">
                    <CheckIcon color="blue" />
                    <span className="text-[13px] text-gray-700 leading-snug">{item.label}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* PISMP Language Requirements — removed as separate section; now injected as a rule in PismpSection */}

        {/* Complex Requirements — OR groups (UA/Asasi courses) */}
        {hasComplex && (
          <OrGroupSection
            groups={requirements.complex_requirements!.or_groups!}
            locale={locale}
            label={t('courseDetail.subjectReq')}
          />
        )}

        {/* Subject Group Requirements (PISMP) */}
        {hasSubjectGroup && (
          <PismpSection
            rules={requirements.subject_group_req!}
            locale={locale}
            label={t('courseDetail.subjectReq')}
            showHeading={!hasComplex}
            pismpLangs={pismpLangs}
          />
        )}

        {/* Remarks — skip auto-generated text */}
        {requirements.remarks && !requirements.remarks.startsWith('General:') && (
          <p className="text-[11px] text-gray-400 pt-3 border-t border-gray-100 italic leading-relaxed">
            {requirements.remarks}
          </p>
        )}
      </div>
    </section>
  )
}

// --- Shared CheckIcon ---

function CheckIcon({ color }: { color: 'gray' | 'blue' | 'green' }) {
  const styles = {
    gray: 'bg-gray-100 text-gray-500',
    blue: 'bg-blue-50 text-blue-500',
    green: 'bg-green-50 text-green-500',
  }
  return (
    <span className={`mt-0.5 flex-shrink-0 w-[18px] h-[18px] rounded-full ${styles[color]} flex items-center justify-center`}>
      <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
      </svg>
    </span>
  )
}

// --- TVET key-value helpers ---

function tvetKeyLabel(key: string, locale: string): string {
  const labels: Record<string, { bm: string; en: string }> = {
    req_malaysian: { bm: 'Warganegara', en: 'Nationality' },
    single: { bm: 'Status Perkahwinan', en: 'Marital Status' },
    min_credits: { bm: 'Kredit SPM', en: 'SPM Credits' },
    min_pass: { bm: 'Lulus SPM', en: 'SPM Passes' },
    no_colorblind: { bm: 'Penglihatan Warna', en: 'Colour Vision' },
    no_disability: { bm: 'Fizikal', en: 'Physical' },
    req_male: { bm: 'Jantina', en: 'Gender' },
    req_female: { bm: 'Jantina', en: 'Gender' },
  }
  const entry = labels[key]
  return entry ? (locale === 'en' ? entry.en : entry.bm) : key
}

function tvetValueLabel(item: ReqItem, locale: string): string {
  const values: Record<string, { bm: string; en: string }> = {
    req_malaysian: { bm: 'Malaysia', en: 'Malaysian' },
    single: { bm: 'Bujang', en: 'Single' },
    no_colorblind: { bm: 'Normal', en: 'Normal' },
    no_disability: { bm: 'Tiada Kecacatan', en: 'No Disability' },
    req_male: { bm: 'Lelaki Sahaja', en: 'Male Only' },
    req_female: { bm: 'Perempuan Sahaja', en: 'Female Only' },
  }
  if (item.key === 'min_credits' || item.key === 'min_pass') {
    return locale === 'en' ? `Min. ${item.value}` : `Min. ${item.value}`
  }
  const entry = values[item.key]
  return entry ? (locale === 'en' ? entry.en : entry.bm) : item.label
}

// --- OR Groups (complex_requirements) ---

function OrGroupSection({
  groups,
  locale,
  label,
}: {
  groups: OrGroup[]
  locale: string
  label: string
}) {
  const [expanded, setExpanded] = useState(groups.length <= 3)
  const displayGroups = expanded ? groups : groups.slice(0, 3)

  return (
    <div>
      <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
        {label}
      </h3>
      <div className="space-y-2">
        {displayGroups.map((group, idx) => (
          <div key={idx} className="bg-gradient-to-br from-gray-50 to-slate-50 rounded-lg p-3 border border-gray-100">
            <div className="flex items-start gap-2.5 mb-2">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary-500 text-white text-[11px] font-bold flex-shrink-0">
                {idx + 1}
              </span>
              <span className="text-[13px] text-gray-600 leading-snug pt-0.5">
                {requirementDesc(group.count, group.grade, group.subjects.length, locale)}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5 ml-[34px]">
              {group.subjects.map((subj) => (
                <span
                  key={subj}
                  className="px-2.5 py-1 bg-blue-50 border border-blue-100 rounded-full text-xs font-medium text-blue-700"
                >
                  {getSubjectName(subj, locale)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      {groups.length > 3 && !expanded && (
        <button
          onClick={() => setExpanded(true)}
          className="mt-2.5 w-full text-xs text-primary-600 hover:text-primary-700 font-medium flex items-center justify-center gap-1 py-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          {locale === 'en'
            ? `Show all ${groups.length} groups`
            : `Papar semua ${groups.length} kumpulan`}
        </button>
      )}
    </div>
  )
}

// --- PISMP Subject Group Requirements ---

function PismpSection({
  rules,
  locale,
  label,
  showHeading,
  pismpLangs,
}: {
  rules: SubjectGroupRule[]
  locale: string
  label: string
  showHeading: boolean
  pismpLangs: string[]
}) {
  const langCodes = new Set(Object.keys(MEDIUM_LANGUAGES))
  const hasLangs = pismpLangs.length > 0

  // Strip language subjects (BC/BT) from existing rules when we'll add a dedicated lang rule
  const displayRules: SubjectGroupRule[] = []
  let langGrade = 'C' // default grade for the language OR rule
  for (const rule of rules) {
    if (!hasLangs || rule.subjects.length === 0) {
      displayRules.push(rule)
      continue
    }
    const langSubjects = rule.subjects.filter((s) => langCodes.has(s))
    const otherSubjects = rule.subjects.filter((s) => !langCodes.has(s))
    if (langSubjects.length > 0) {
      langGrade = rule.min_grade // capture the grade that applied to the language subject
    }
    if (otherSubjects.length === 0) continue // rule only had language subjects — skip
    displayRules.push(otherSubjects.length === rule.subjects.length ? rule : { ...rule, subjects: otherSubjects })
  }

  // Build language display names for the OR rule
  const langNames = pismpLangs.map((code) => {
    const entry = MEDIUM_LANGUAGES[code]
    return entry ? (locale === 'en' ? entry.en : entry.bm) : code
  })
  const orLabel = locale === 'en' ? ' or ' : ' atau '

  return (
    <div>
      {showHeading && (
        <h3 className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">
          {label}
        </h3>
      )}
      <div className="space-y-2">
        {displayRules.map((rule, idx) => {
          const isGenericRule = rule.subjects.length === 0

          return (
            <div key={idx} className="bg-gradient-to-br from-gray-50 to-slate-50 rounded-lg p-3 border border-gray-100">
              <div className="flex items-start gap-2.5">
                <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary-500 text-white text-[11px] font-bold flex-shrink-0">
                  {idx + 1}
                </span>
                <span className="text-[13px] text-gray-600 leading-snug pt-0.5">
                  {requirementDesc(rule.min_count, rule.min_grade, rule.subjects.length, locale)}
                </span>
              </div>
              {!isGenericRule && (
                <div className="flex flex-wrap gap-1.5 ml-[34px] mt-2">
                  {rule.subjects.map((subj) => (
                    <span
                      key={subj}
                      className="px-2.5 py-1 bg-blue-50 border border-blue-100 rounded-full text-xs font-medium text-blue-700"
                    >
                      {getSubjectName(subj, locale)}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {/* Language OR rule — appended as last numbered rule */}
        {hasLangs && (
          <div className="bg-gradient-to-br from-gray-50 to-slate-50 rounded-lg p-3 border border-gray-100">
            <div className="flex items-start gap-2.5">
              <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary-500 text-white text-[11px] font-bold flex-shrink-0">
                {displayRules.length + 1}
              </span>
              <span className="text-[13px] text-gray-600 leading-snug pt-0.5">
                {gradeLabel(langGrade, locale)}{' '}
                {locale === 'en' ? 'or better in:' : 'atau lebih dalam:'}
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5 ml-[34px] mt-2">
              {langNames.map((name, i) => (
                <span key={i}>
                  <span className="px-2.5 py-1 bg-purple-50 border border-purple-100 rounded-full text-xs font-medium text-purple-700">
                    {name}
                  </span>
                  {i < langNames.length - 1 && (
                    <span className="text-xs text-gray-400 mx-1">{orLabel}</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
