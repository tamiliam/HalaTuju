'use client'

/**
 * THE STUDENT'S "ABOUT YOUR FAMILY" ANSWERS, read-only, inside the Family & finances card
 * (request #45, 2026-10-25).
 *
 * The student fills these after shortlisting — father / mother / other members and their
 * occupations, who earns, a declared monthly wage, and why and since when a member is not
 * working — and the cockpit used to show none of it: only the parent CONTACT box, which officers
 * then read as "the family". This lists what the student said, in the student form's own words
 * (`scholarship.nextSteps.story.cardA.*`), with no ticks: these are claims, not checked facts.
 *
 * ⚠ NO NEW AUDIENCE. It sits in the same card as the household income and is gated exactly as
 * that is: by the page gate. The payload is role-invariant by owner decision
 * (`test_admin_detail_payload.py`), so nothing here is shown to anyone who could not already read
 * the income beside it.
 */
import type { AdminScholarshipDetail } from '@/lib/admin-api'
import type { T } from './shared'

const CA = 'scholarship.nextSteps.story.cardA'
const FA = 'admin.scholarship.familyAnswers'
const OTHER_ROLES = new Set(['brother', 'sister', 'guardian'])

type Member = { key: string; role: string; name?: string; occupation?: string; occupationOther?: string }

/** The members the student listed, in the form's order. Empty = the section is not filled in. */
export function familyMembers(app: AdminScholarshipDetail): Member[] {
  const out: Member[] = []
  for (const who of ['father', 'mother'] as const) {
    const name = (app[`${who}_name`] || '').trim()
    const occupation = app[`${who}_occupation`] || ''
    if (name || occupation) {
      out.push({ key: who, role: who, name, occupation, occupationOther: app[`${who}_occupation_other`] || '' })
    }
  }
  ;(Array.isArray(app.other_family_members) ? app.other_family_members : []).forEach((m, i) => {
    if (!m || !OTHER_ROLES.has(m.role || '')) return
    out.push({ key: `other-${i}`, role: m.role!, name: (m.name || '').trim(), occupation: m.occupation || '', occupationOther: m.occupation_other || '' })
  })
  return out
}

/** Who the income wizard names as earning: the STR route's one earner, or the salary route's
 *  working members. `null` when the student has not answered it yet (no line is shown). */
export function householdEarners(app: AdminScholarshipDetail): string[] | null {
  if (app.income_route === 'str') return app.income_earner ? [app.income_earner] : []
  if (app.income_route === 'salary') return Array.isArray(app.income_working_members) ? app.income_working_members : []
  return null
}

/** 'YYYY-MM' → 'MM/YYYY' (language-neutral); anything else is shown as typed. */
const monthYear = (s: string) => (/^\d{4}-\d{2}$/.test(s) ? `${s.slice(5)}/${s.slice(0, 4)}` : s)

export function FamilyAnswers({ app, t }: { app: AdminScholarshipDetail; t: T }) {
  const members = familyMembers(app)
  const earners = householdEarners(app)
  const declared = app.income_declared || {}
  const nonEarning = app.income_nonearning || {}
  const roleLabel = (role: string) => t(OTHER_ROLES.has(role) ? `${CA}.role.${role}` : `${CA}.${role}`)
  const occupationLabel = (m: Member) => {
    if (!m.occupation) return null
    if (m.occupation === 'other' && m.occupationOther?.trim()) return m.occupationOther.trim()
    return t(`${CA}.prof.${m.occupation}`)
  }

  return (
    <div className="mt-4 border-t border-ground-100 pt-3" data-testid="family-answers">
      <p className="mb-2 text-xs text-ground-400 uppercase tracking-wider">{t(`${FA}.title`)}</p>
      {members.length === 0 ? (
        <p className="text-sm text-ground-400">{t(`${FA}.notFilled`)}</p>
      ) : (
        <ul className="space-y-2">
          {members.map((m) => {
            const earns = !!earners?.includes(m.role)
            const amount = declared[m.role]
            const gone = nonEarning[m.role]
            return (
              <li key={m.key} className="text-sm text-ground-800">
                <span className="font-medium">{roleLabel(m.role)}</span>
                {m.name && <span> · {m.name}</span>}
                {occupationLabel(m) && <span className="text-ground-500"> · {occupationLabel(m)}</span>}
                {earns && <span className="ml-1.5 rounded bg-positive-50 px-1.5 py-0.5 text-xs text-positive-700">{t(`${FA}.earns`)}</span>}
                {typeof amount === 'number' && amount > 0 && (
                  <p className="text-xs text-ground-500">{t(`${FA}.declared`, { amount: Number(amount).toLocaleString('en-US') })}</p>
                )}
                {gone && (gone.since || gone.reason) && (
                  <p className="text-xs text-ground-500">
                    {gone.since && t(`${FA}.notWorkingSince`, { since: monthYear(gone.since) })}
                    {gone.since && gone.reason && ' · '}
                    {gone.reason && t(`${FA}.reason`, { reason: gone.reason })}
                  </p>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {earners && (
        <p className="mt-2 text-sm text-ground-800">
          <span className="text-xs text-ground-400 uppercase tracking-wider">{t(`${FA}.earners`)}: </span>
          {earners.length ? earners.map(roleLabel).join(', ') : t(`${FA}.noEarner`)}
        </p>
      )}
    </div>
  )
}
