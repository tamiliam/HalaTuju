'use client'

// Shared structured-family-roster editor — Father/Mother (name + coded profession),
// an optional brother/sister/guardian pool, and the two sibling steppers (which
// derive first-in-family). Used by BOTH the /scholarship/application "Your story"
// step AND the /profile Family & Background card, against the SAME field names, so
// the two surfaces are identical and stay in sync. i18n reuses the existing
// `scholarship.nextSteps.story.cardA.*` keys — no new strings.
import { PROFESSION_GROUPS, FAMILY_ROLES, MAX_OTHER_MEMBERS, type FamilyRole, type OtherMember } from '@/lib/familyRoster'
import FieldLabel from '@/components/FieldLabel'

type TFn = (key: string) => string
const CA = 'scholarship.nextSteps.story.cardA'

/** The roster sub-form shared by DetailsFormState (Story) and the /profile page. */
export interface FamilyRosterForm {
  fatherName: string
  fatherOccupation: string
  fatherOccupationOther: string
  motherName: string
  motherOccupation: string
  motherOccupationOther: string
  otherFamilyMembers: OtherMember[]
  siblingsInSchool: number
  siblingsInTertiary: number
}

/** Profession <select> with grouped options (employed / informal / not-working).
 *  Codes mirror the backend family.PROFESSION_CHOICES; labels are i18n. */
function ProfessionSelect({ value, onChange, t }: { value: string; onChange: (v: string) => void; t: TFn }) {
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{t(`${CA}.professionPlaceholder`)}</option>
      {PROFESSION_GROUPS.map((g) => (
        <optgroup key={g.groupKey} label={t(`${CA}.group.${g.groupKey}`)}>
          {g.codes.map((code) => (
            <option key={code} value={code}>{t(`${CA}.prof.${code}`)}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

/** A +/− stepper for a sibling count. Defaults to 0 (a real "none" answer). */
function CountStepper({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const btn = 'h-9 w-9 rounded-full border border-gray-300 text-lg leading-none text-gray-600 hover:bg-gray-100 disabled:opacity-40'
  return (
    <div className="flex items-center gap-3">
      <button type="button" aria-label="decrease" className={btn}
        onClick={() => onChange(Math.max(0, value - 1))}>−</button>
      <span className="w-6 text-center text-sm font-semibold tabular-nums">{value}</span>
      <button type="button" aria-label="increase" className={btn}
        onClick={() => onChange(value + 1)}>+</button>
    </div>
  )
}

export default function FamilyRosterFields({
  form, onUpdate, onUpdateMember, onAddMember, onRemoveMember, t, profileStyle = false,
}: {
  form: FamilyRosterForm
  // Non-generic so both callers' updaters (Story's wider DetailsFormState updater and
  // /profile's FamilyRosterForm updater) are assignable. The roster only updates string
  // (name/occupation) and number (sibling counts) fields via this; the member-pool
  // array goes through onUpdateMember.
  onUpdate: (key: keyof FamilyRosterForm, value: string | number) => void
  onUpdateMember: (i: number, patch: Partial<OtherMember>) => void
  onAddMember: () => void
  onRemoveMember: (i: number) => void
  t: TFn
  // /profile variant: nothing here is compulsory (no required asterisks), Father/Mother
  // render as small uppercase grey sub-headings (matching "YOUR BROTHERS & SISTERS"),
  // and the top separator above the siblings block is dropped. Story (/apply) keeps the
  // default (required + plain labels + separator).
  profileStyle?: boolean
}) {
  const req = !profileStyle
  const parentLabelClass = profileStyle
    ? 'text-[11px] font-semibold uppercase tracking-wider text-gray-500'
    : 'text-sm font-medium text-gray-700'
  return (
    <div className="space-y-5">
      {/* ── Parents / guardians ─────────────────────────────────────────── */}
      <div className="space-y-4">
        {(['father', 'mother'] as const).map((who) => {
          const nameKey = `${who}Name` as const
          const occKey = `${who}Occupation` as const
          const otherKey = `${who}OccupationOther` as const
          return (
            <div key={who} className="space-y-2">
              <p className={parentLabelClass}>{t(`${CA}.${who}`)}</p>
              <div className="grid gap-2 sm:grid-cols-2">
                <div>
                  <FieldLabel required={req}>{t(`${CA}.name`)}</FieldLabel>
                  <input className="input" maxLength={200}
                    value={form[nameKey]} onChange={(e) => onUpdate(nameKey, e.target.value)} />
                </div>
                <div>
                  <FieldLabel required={req}>{t(`${CA}.profession`)}</FieldLabel>
                  <ProfessionSelect value={form[occKey]} onChange={(v) => onUpdate(occKey, v)} t={t} />
                </div>
              </div>
              {form[occKey] === 'other' && (
                <input className="input" maxLength={120}
                  placeholder={t(`${CA}.otherSpecify`)}
                  value={form[otherKey]} onChange={(e) => onUpdate(otherKey, e.target.value)} />
              )}
            </div>
          )
        })}

        {/* Optional member pool */}
        {form.otherFamilyMembers.map((m, i) => (
          <div key={i} className="rounded-lg border border-gray-200 bg-white p-3 space-y-2">
            <div className="flex items-start gap-2">
              <div className="flex-1 grid gap-2 sm:grid-cols-2">
                <select className="input" value={m.role}
                  onChange={(e) => onUpdateMember(i, { role: e.target.value as FamilyRole })}>
                  {FAMILY_ROLES.map((r) => {
                    const guardianTaken = r === 'guardian'
                      && form.otherFamilyMembers.some((mm, j) => j !== i && mm.role === 'guardian')
                    return <option key={r} value={r} disabled={guardianTaken}>{t(`${CA}.role.${r}`)}</option>
                  })}
                </select>
                <ProfessionSelect value={m.occupation} onChange={(v) => onUpdateMember(i, { occupation: v })} t={t} />
              </div>
              <button type="button" onClick={() => onRemoveMember(i)} aria-label={t(`${CA}.remove`)}
                className="mt-1.5 shrink-0 text-gray-400 hover:text-red-500 text-lg leading-none">×</button>
            </div>
            {m.occupation === 'other' && (
              <input className="input" maxLength={120}
                placeholder={t(`${CA}.otherSpecify`)}
                value={m.occupation_other || ''}
                onChange={(e) => onUpdateMember(i, { occupation_other: e.target.value })} />
            )}
          </div>
        ))}
        {form.otherFamilyMembers.length < MAX_OTHER_MEMBERS && (
          <button type="button" onClick={onAddMember}
            className="w-full rounded-lg border border-dashed border-gray-300 py-2 text-sm font-medium text-primary-600 hover:bg-white">
            + {t(`${CA}.addMember`)}
          </button>
        )}
      </div>

      {/* ── Brothers & sisters (compulsory steppers; derive first-in-family) ── */}
      <div className={profileStyle ? 'space-y-3 pt-4' : 'space-y-3 border-t border-gray-200 pt-4'}>
        <p className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          {t(`${CA}.siblingsHeading`)}
        </p>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-gray-700">{t(`${CA}.siblingsSchool`)}</span>
          <CountStepper value={form.siblingsInSchool} onChange={(v) => onUpdate('siblingsInSchool', v)} />
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm text-gray-700">{t(`${CA}.siblingsTertiary`)}</span>
          <CountStepper value={form.siblingsInTertiary} onChange={(v) => onUpdate('siblingsInTertiary', v)} />
        </div>
        {form.siblingsInTertiary === 0 && (
          <div className="flex items-center gap-1.5 rounded-lg border border-green-200 bg-green-50 p-2 text-sm text-green-700">
            <span aria-hidden>✓</span> {t(`${CA}.firstInFamilyNote`)}
          </div>
        )}
      </div>
    </div>
  )
}
