# IC Gate + Profile Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the school name input in AuthGateModal with a compulsory IC number gate, redesign the profile page with view/edit per-section, and add an incompleteness badge in the nav.

**Architecture:** Three connected features: (1) IC input component with auto-dash formatting and validation, wired into AuthGateModal as a new step after auth; (2) Profile page sections switch between read-only view mode and per-section edit mode; (3) Badge in AppHeader showing count of unfilled profile fields. Backend already has `nric` field — no model changes needed.

**Tech Stack:** Next.js 14 (App Router), React, TypeScript, Tailwind CSS, Supabase Auth, Django REST backend

---

## IC Number Validation Rules (Domain Knowledge)

Malaysian NRIC format: `YYMMDD-SS-NNNN`

- **First 6 digits (YYMMDD)**: Date of birth. Must be a valid date. Student age must be 15–23 (born 2003–2011 for year 2026).
- **Digits 7–8 (SS)**: State/country code. Valid Malaysian state codes: 01–16 (states), 21–22 (Sabah regions), 23–24 (Sarawak regions), 82 (unknown/undetermined), 71–72 (foreign born). See full list in implementation.
- **Last 4 digits (NNNN)**: Sequential number. Any 4 digits — no further validation.
- **Display format**: `XXXXXX-XX-XXXX` (auto-insert dashes after 6th and 8th digit)
- **Masked display on profile**: `****-**-1234` (show only last 4 digits)

## Profile Completeness Fields (for badge count)

Count unfilled fields from this list:
1. `name` — empty string
2. `nric` — empty string
3. `gender` — empty string
4. `preferred_state` — empty string
5. `phone` — empty string
6. `family_income` — empty string
7. `siblings` — null/undefined
8. `address` — empty string

Total possible: 8. Badge shows count of unfilled fields. Badge disappears when count = 0.

---

### Task 1: IC Input Component

**Files:**
- Create: `halatuju-web/src/components/IcInput.tsx`
- Create: `halatuju-web/src/lib/ic-utils.ts`
- Create: `halatuju-web/src/lib/__tests__/ic-utils.test.ts`

**Step 1: Write the IC validation utility with tests**

Create `halatuju-web/src/lib/ic-utils.ts`:

```typescript
/**
 * Malaysian NRIC utilities.
 * Format: YYMMDD-SS-NNNN
 */

// Valid Malaysian state/country codes (digits 7-8)
const VALID_STATE_CODES = new Set([
  '01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
  '11', '12', '13', '14', '15', '16',  // 16 states
  '21', '22', '23', '24',              // Sabah/Sarawak regions
  '71', '72',                           // Foreign born
  '82',                                 // Unknown
])

/** Strip dashes from NRIC string */
export function stripDashes(value: string): string {
  return value.replace(/-/g, '')
}

/** Format raw digits as XXXXXX-XX-XXXX */
export function formatIc(digits: string): string {
  const d = digits.replace(/\D/g, '').slice(0, 12)
  if (d.length <= 6) return d
  if (d.length <= 8) return `${d.slice(0, 6)}-${d.slice(6)}`
  return `${d.slice(0, 6)}-${d.slice(6, 8)}-${d.slice(8)}`
}

/** Mask NRIC for display: ****-**-1234 */
export function maskIc(nric: string): string {
  const digits = stripDashes(nric)
  if (digits.length < 12) return nric
  return `****-**-${digits.slice(8)}`
}

/** Validate NRIC. Returns error message or null if valid. */
export function validateIc(value: string): string | null {
  const digits = stripDashes(value).replace(/\D/g, '')

  if (digits.length !== 12) {
    return 'IC number must be 12 digits'
  }

  // Parse DOB (YYMMDD)
  const yy = parseInt(digits.slice(0, 2), 10)
  const mm = parseInt(digits.slice(2, 4), 10)
  const dd = parseInt(digits.slice(4, 6), 10)

  // Century: 00-11 = 2000s, 12-99 = 1900s (for student age 15-23 in 2026)
  const year = yy <= 11 ? 2000 + yy : 1900 + yy

  // Basic date validity
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31) {
    return 'Invalid date of birth in IC number'
  }

  // Check the date actually exists
  const dob = new Date(year, mm - 1, dd)
  if (dob.getFullYear() !== year || dob.getMonth() !== mm - 1 || dob.getDate() !== dd) {
    return 'Invalid date of birth in IC number'
  }

  // Age check: must be 15-23 (current year = 2026)
  const currentYear = new Date().getFullYear()
  const age = currentYear - year
  if (age < 15 || age > 23) {
    return 'IC number must belong to a student aged 15–23'
  }

  // State code check
  const stateCode = digits.slice(6, 8)
  if (!VALID_STATE_CODES.has(stateCode)) {
    return 'Invalid state code in IC number'
  }

  return null
}
```

Create `halatuju-web/src/lib/__tests__/ic-utils.test.ts`:

```typescript
import { formatIc, maskIc, validateIc, stripDashes } from '../ic-utils'

describe('formatIc', () => {
  it('formats 12 digits with dashes', () => {
    expect(formatIc('031215011234')).toBe('031215-01-1234')
  })
  it('partial input: 6 digits', () => {
    expect(formatIc('031215')).toBe('031215')
  })
  it('partial input: 8 digits', () => {
    expect(formatIc('03121501')).toBe('031215-01')
  })
  it('strips non-digits', () => {
    expect(formatIc('031215-01-1234')).toBe('031215-01-1234')
  })
  it('truncates beyond 12 digits', () => {
    expect(formatIc('03121501123456')).toBe('031215-01-1234')
  })
})

describe('maskIc', () => {
  it('masks all but last 4 digits', () => {
    expect(maskIc('031215-01-1234')).toBe('****-**-1234')
  })
  it('returns original if too short', () => {
    expect(maskIc('031215')).toBe('031215')
  })
})

describe('stripDashes', () => {
  it('removes dashes', () => {
    expect(stripDashes('031215-01-1234')).toBe('031215011234')
  })
})

describe('validateIc', () => {
  it('accepts valid IC (born 2003, state 01)', () => {
    expect(validateIc('031215-01-1234')).toBeNull()
  })
  it('accepts valid IC (born 2008, state 14)', () => {
    expect(validateIc('080601-14-5678')).toBeNull()
  })
  it('rejects wrong length', () => {
    expect(validateIc('03121501')).toBe('IC number must be 12 digits')
  })
  it('rejects invalid month', () => {
    expect(validateIc('031315-01-1234')).toBe('Invalid date of birth in IC number')
  })
  it('rejects invalid day', () => {
    expect(validateIc('030230-01-1234')).toBe('Invalid date of birth in IC number')
  })
  it('rejects too young (born 2012 = age 14)', () => {
    expect(validateIc('120601-01-1234')).toBe('IC number must belong to a student aged 15–23')
  })
  it('rejects too old (born 2002 = age 24)', () => {
    expect(validateIc('020601-01-1234')).toBe('IC number must belong to a student aged 15–23')
  })
  it('rejects invalid state code', () => {
    expect(validateIc('031215-99-1234')).toBe('Invalid state code in IC number')
  })
  it('accepts foreign-born code 71', () => {
    expect(validateIc('050601-71-1234')).toBeNull()
  })
})
```

**Step 2: Run the tests to verify they pass**

Run: `cd halatuju-web && npx jest src/lib/__tests__/ic-utils.test.ts --no-cache`
Expected: All tests PASS

**Step 3: Create the IcInput component**

Create `halatuju-web/src/components/IcInput.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { formatIc, validateIc, stripDashes } from '@/lib/ic-utils'

interface IcInputProps {
  value: string
  onChange: (digits: string) => void
  onValidChange?: (isValid: boolean) => void
  error?: string | null
  label?: string
  placeholder?: string
  disabled?: boolean
}

export default function IcInput({
  value,
  onChange,
  onValidChange,
  error: externalError,
  label,
  placeholder = 'XXXXXX-XX-XXXX',
  disabled = false,
}: IcInputProps) {
  const [touched, setTouched] = useState(false)

  const formatted = formatIc(value)
  const validationError = touched && value.length > 0 ? validateIc(value) : null
  const displayError = externalError || validationError

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Extract only digits from the input
    const raw = e.target.value.replace(/\D/g, '').slice(0, 12)
    onChange(raw)

    if (onValidChange) {
      onValidChange(raw.length === 12 && validateIc(raw) === null)
    }
  }

  return (
    <div>
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {label} <span className="text-red-500">*</span>
        </label>
      )}
      <input
        type="text"
        inputMode="numeric"
        value={formatted}
        onChange={handleChange}
        onBlur={() => setTouched(true)}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full px-3 py-2.5 border rounded-lg text-sm tracking-wider focus:ring-1 outline-none ${
          displayError
            ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
            : 'border-gray-300 focus:border-primary-500 focus:ring-primary-500'
        }`}
      />
      {displayError && (
        <p className="mt-1 text-xs text-red-500">{displayError}</p>
      )}
    </div>
  )
}
```

**Step 4: Commit**

```bash
git add halatuju-web/src/lib/ic-utils.ts halatuju-web/src/lib/__tests__/ic-utils.test.ts halatuju-web/src/components/IcInput.tsx
git commit -m "feat: add IC number input component with validation and auto-formatting"
```

---

### Task 2: Add i18n Keys for IC Gate and Profile Redesign

**Files:**
- Modify: `halatuju-web/src/messages/en.json`
- Modify: `halatuju-web/src/messages/ms.json`
- Modify: `halatuju-web/src/messages/ta.json`

**Step 1: Add new i18n keys to all three language files**

Add to the `authGate` section:

| Key | EN | MS | TA |
|-----|----|----|-----|
| `authGate.icTitle` | Enter Your IC Number | Masukkan Nombor IC Anda | உங்கள் IC எண்ணை உள்ளிடவும் |
| `authGate.icSubtitle` | We need your IC number to personalise your experience. Your data is kept private. | Kami memerlukan nombor IC anda untuk menyesuaikan pengalaman anda. Data anda dirahsiakan. | உங்கள் அனுபவத்தை தனிப்பயனாக்க உங்கள் IC எண் தேவை. உங்கள் தரவு ரகசியமாக பாதுகாக்கப்படும். |
| `authGate.icLabel` | IC Number (MyKad) | Nombor IC (MyKad) | IC எண் (MyKad) |
| `authGate.icContinue` | Continue | Teruskan | தொடரவும் |
| `authGate.icPrivacy` | Your IC is encrypted and never shared with third parties. | IC anda dienkripsi dan tidak dikongsi dengan pihak ketiga. | உங்கள் IC குறியாக்கம் செய்யப்பட்டு மூன்றாம் தரப்பினருடன் பகிரப்படாது. |

Add to the `profile` section:

| Key | EN | MS | TA |
|-----|----|----|-----|
| `profile.edit` | Edit | Sunting | திருத்து |
| `profile.save` | Save | Simpan | சேமி |
| `profile.cancel` | Cancel | Batal | ரத்துசெய் |
| `profile.identity` | Identity | Identiti | அடையாளம் |
| `profile.demographics` | Demographics | Demografi | மக்கள்தொகை |
| `profile.education` | Education | Pendidikan | கல்வி |
| `profile.family` | Family | Keluarga | குடும்பம் |
| `profile.icMasked` | IC Number | Nombor IC | IC எண் |
| `profile.incompleteFields` | {count} fields to complete | {count} medan belum diisi | {count} புலங்கள் நிரப்பப்படவில்லை |
| `profile.profileComplete` | Profile complete | Profil lengkap | சுயவிவரம் முழுமை |
| `profile.school` | School | Sekolah | பள்ளி |

**Step 2: Commit**

```bash
git add halatuju-web/src/messages/en.json halatuju-web/src/messages/ms.json halatuju-web/src/messages/ta.json
git commit -m "feat: add i18n keys for IC gate and profile view/edit redesign (EN/MS/TA)"
```

---

### Task 3: Wire IC Gate into AuthGateModal

**Files:**
- Modify: `halatuju-web/src/components/AuthGateModal.tsx`
- Modify: `halatuju-web/src/lib/api.ts`

**Step 1: Add `nric` to SyncProfileData**

In `halatuju-web/src/lib/api.ts`, add `nric?: string` to the `SyncProfileData` interface (line 475):

```typescript
export interface SyncProfileData {
  grades?: Record<string, string>
  gender?: string
  nationality?: string
  colorblind?: string
  disability?: string
  student_signals?: Record<string, Record<string, number>>
  preferred_state?: string
  name?: string
  school?: string
  nric?: string  // <-- add this
}
```

**Step 2: Replace school input with IC gate step in AuthGateModal**

Modify `halatuju-web/src/components/AuthGateModal.tsx`:

1. Change `ModalStep` type:
```typescript
type ModalStep = 'login' | 'otp' | 'ic' | 'profile'
```

2. Add IC state and import:
```typescript
import IcInput from './IcInput'
import { validateIc } from '@/lib/ic-utils'

// Inside the component, add state:
const [ic, setIc] = useState('')
const [icValid, setIcValid] = useState(false)
```

3. Update the `useEffect` that advances to profile step (line 48-58): Change target from `'profile'` to `'ic'`:
```typescript
useEffect(() => {
  if (isAuthenticated && authGateReason && step !== 'ic' && step !== 'profile') {
    const googleName = session?.user?.user_metadata?.full_name
      || session?.user?.user_metadata?.name
    if (googleName && !name) {
      setName(googleName)
    }
    setStep('ic')
    setError(null)
  }
}, [isAuthenticated, authGateReason, step, session, name])
```

4. Add IC submit handler (after `handleOtpSubmit`):
```typescript
const handleIcSubmit = async (e: React.FormEvent) => {
  e.preventDefault()
  const err = validateIc(ic)
  if (err) {
    setError(err)
    return
  }
  setError(null)
  setStep('profile')
}
```

5. Add IC step UI (between OTP and Profile step render blocks):
```tsx
{/* IC Step */}
{step === 'ic' && (
  <form onSubmit={handleIcSubmit} className="space-y-4">
    <p className="text-gray-600 text-center mb-2">
      {t('authGate.icSubtitle')}
    </p>
    <IcInput
      value={ic}
      onChange={setIc}
      onValidChange={setIcValid}
      label={t('authGate.icLabel')}
    />
    <button
      type="submit"
      disabled={!icValid}
      className="btn-primary w-full disabled:opacity-50"
    >
      {t('authGate.icContinue')}
    </button>
    <p className="text-xs text-gray-400 text-center">
      {t('authGate.icPrivacy')}
    </p>
  </form>
)}
```

6. Remove the school input from the profile step (lines 345-355). Keep name input. The profile step header changes to:
```tsx
{step === 'profile' && (
  <form onSubmit={handleProfileSubmit} className="space-y-4">
    <p className="text-gray-600 text-center mb-2">
      {t('authGate.almostDone')}
    </p>
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {t('authGate.nameLabel')}
      </label>
      <input
        type="text"
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={t('authGate.namePlaceholder')}
        className="input"
      />
    </div>
    <button
      type="submit"
      disabled={loading}
      className="btn-primary w-full disabled:opacity-50"
    >
      {loading ? '...' : t('authGate.completeProfile')}
    </button>
  </form>
)}
```

7. In `handleProfileSubmit`, include the IC number in the sync data (around line 159):
```typescript
if (name.trim()) syncData.name = name.trim()
if (ic) syncData.nric = ic  // <-- add this (raw 12 digits, no dashes)
// Remove: if (school.trim()) syncData.school = school.trim()
```

8. Remove the `school` state variable (line 29) and its reset in the useEffect (line 40).

**Step 3: Reset IC state in modal reset useEffect**

In the `useEffect` that resets state when modal opens (line 34-45), add:
```typescript
setIc('')
setIcValid(false)
```

**Step 4: Test manually**

- Open the app, trigger auth gate (e.g., click Load More)
- After Gmail login, should see IC step instead of going straight to profile
- Enter invalid IC → error shown
- Enter valid IC → advances to name-only profile step
- Complete → modal closes, IC saved to backend

**Step 5: Commit**

```bash
git add halatuju-web/src/components/AuthGateModal.tsx halatuju-web/src/lib/api.ts
git commit -m "feat: IC gate step in AuthGateModal — replaces school input, validates NRIC"
```

---

### Task 4: Profile Completeness Hook

**Files:**
- Create: `halatuju-web/src/lib/useProfileCompleteness.ts`

**Step 1: Create the hook**

```typescript
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '@/lib/auth-context'
import { getProfile } from '@/lib/api'

const COMPLETENESS_FIELDS = [
  'name', 'nric', 'gender', 'preferred_state',
  'phone', 'family_income', 'siblings', 'address',
] as const

export function useProfileCompleteness() {
  const { token, isAuthenticated } = useAuth()
  const [incompleteCount, setIncompleteCount] = useState(0)
  const [loaded, setLoaded] = useState(false)

  const refresh = useCallback(async () => {
    if (!token) return
    try {
      const profile = await getProfile({ token })
      let count = 0
      for (const field of COMPLETENESS_FIELDS) {
        const val = profile[field]
        if (val === null || val === undefined || val === '') count++
      }
      setIncompleteCount(count)
      setLoaded(true)
    } catch {
      // Non-critical
    }
  }, [token])

  useEffect(() => {
    if (isAuthenticated && token) refresh()
  }, [isAuthenticated, token, refresh])

  return { incompleteCount, loaded, refresh }
}
```

**Step 2: Commit**

```bash
git add halatuju-web/src/lib/useProfileCompleteness.ts
git commit -m "feat: useProfileCompleteness hook — counts unfilled profile fields"
```

---

### Task 5: Add Incompleteness Badge to AppHeader

**Files:**
- Modify: `halatuju-web/src/components/AppHeader.tsx`

**Step 1: Wire the badge into AppHeader**

1. Import the hook:
```typescript
import { useProfileCompleteness } from '@/lib/useProfileCompleteness'
```

2. Call it in the component:
```typescript
const { incompleteCount } = useProfileCompleteness()
```

3. Add the badge next to the "My Profile" nav link. Find the `navLinks` array (line 40-45). After the profile link text, render a badge:

In the desktop nav rendering, find where `link.label` is rendered and add:
```tsx
{link.label}
{link.href === '/profile' && isAuthenticated && incompleteCount > 0 && (
  <span className="ml-1.5 inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-red-500 rounded-full">
    {incompleteCount}
  </span>
)}
```

Do the same in the mobile nav rendering.

4. Also show the badge on the profile dropdown initials avatar (desktop). Wrap the initials circle and add an absolute-positioned badge:
```tsx
<div className="relative">
  {/* existing initials circle */}
  {incompleteCount > 0 && (
    <span className="absolute -top-1 -right-1 w-4 h-4 text-[10px] font-bold text-white bg-red-500 rounded-full flex items-center justify-center">
      {incompleteCount}
    </span>
  )}
</div>
```

**Step 2: Test manually**

- Log in with a profile that has missing fields
- Badge should show count (e.g., "5")
- Fill all fields on profile page → badge disappears

**Step 3: Commit**

```bash
git add halatuju-web/src/components/AppHeader.tsx
git commit -m "feat: incompleteness badge on profile nav link and avatar"
```

---

### Task 6: Profile Page — View/Edit Per-Section Redesign

**Files:**
- Modify: `halatuju-web/src/app/profile/page.tsx`

This is the largest task. The profile page currently has all fields always editable with a single "Save Changes" button at the bottom. We're changing to:

- Each section shows values as **read-only text** by default
- Each section header has an **Edit button**
- Clicking Edit makes that section's fields editable, shows **Save** and **Cancel** buttons
- IC is always view-only (masked display `****-**-1234`)
- Only one section can be in edit mode at a time

**Step 1: Add section edit state**

Replace the existing single `saving` state with per-section state:

```typescript
type EditingSection = 'identity' | 'contact' | 'family' | null

const [editingSection, setEditingSection] = useState<EditingSection>(null)
const [saving, setSaving] = useState(false)

// Snapshot of original values for cancel
const [snapshot, setSnapshot] = useState<Record<string, unknown>>({})
```

Add enter/cancel/save helpers:

```typescript
const startEditing = (section: EditingSection) => {
  // Save current values for cancel
  setSnapshot({ name, nric, gender, nationality, state, address, phone, familyIncome, siblings, colorblind, disability })
  setEditingSection(section)
}

const cancelEditing = () => {
  // Restore snapshot
  setName(snapshot.name as string || '')
  setGender(snapshot.gender as '' | 'male' | 'female' || '')
  setNationality(snapshot.nationality as 'malaysian' | 'non_malaysian' || 'malaysian')
  setState(snapshot.state as string || '')
  setAddress(snapshot.address as string || '')
  setPhone(snapshot.phone as string || '')
  setFamilyIncome(snapshot.familyIncome as string || '')
  setSiblings(snapshot.siblings as string || '')
  setColorblind(snapshot.colorblind as boolean || false)
  setDisability(snapshot.disability as boolean || false)
  setEditingSection(null)
}

const saveSection = async () => {
  // Reuse existing handleSave logic
  await handleSave()
  setEditingSection(null)
}
```

**Step 2: Refactor each section to support view/edit modes**

Create a reusable section header pattern:

```tsx
function SectionHeader({ icon, title, section, editingSection, onEdit }: {
  icon: React.ReactNode
  title: string
  section: EditingSection
  editingSection: EditingSection
  onEdit: () => void
}) {
  const isEditing = editingSection === section
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-sm shadow-primary-500/20">
          {icon}
        </div>
        <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      </div>
      {!isEditing && editingSection === null && (
        <button onClick={onEdit} className="text-sm text-primary-600 hover:text-primary-700 font-medium">
          {t('profile.edit')}
        </button>
      )}
    </div>
  )
}
```

**Step 3: Section 1 (Identity) — view/edit**

View mode shows:
- IC: masked (`****-**-1234`) — always view-only, no edit button for IC
- Name: plain text
- Gender: badge (Male/Female)
- Nationality: badge

Edit mode shows:
- IC: masked, greyed out (not editable)
- Name: text input
- Gender: toggle buttons
- Nationality: toggle buttons

The IC field is **never editable** on the profile page (it was set during the IC gate). Display it masked always.

```tsx
{/* View mode */}
{editingSection !== 'identity' && (
  <div className="space-y-3">
    <div className="flex justify-between">
      <span className="text-sm text-gray-500">{t('profile.icMasked')}</span>
      <span className="text-sm text-gray-900 font-mono">{nric ? maskIc(nric) : '—'}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-sm text-gray-500">{t('onboarding.name')}</span>
      <span className="text-sm text-gray-900">{name || '—'}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-sm text-gray-500">{t('onboarding.gender')}</span>
      <span className="text-sm text-gray-900">{gender ? t(`onboarding.${gender}`) : '—'}</span>
    </div>
    <div className="flex justify-between">
      <span className="text-sm text-gray-500">{t('onboarding.nationality')}</span>
      <span className="text-sm text-gray-900">{nationality === 'malaysian' ? t('onboarding.malaysian') : t('onboarding.nonMalaysian')}</span>
    </div>
  </div>
)}

{/* Edit mode */}
{editingSection === 'identity' && (
  <div className="space-y-4">
    {/* IC — always read-only */}
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('profile.icMasked')}</label>
      <input type="text" value={nric ? maskIc(nric) : '—'} disabled className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm bg-gray-50 text-gray-500" />
    </div>
    {/* Name — editable */}
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('onboarding.name')}</label>
      <input type="text" value={name} onChange={e => setName(e.target.value)} className="w-full px-3 py-2.5 border border-gray-300 rounded-lg text-sm focus:border-primary-500 focus:ring-1 focus:ring-primary-500 outline-none" />
    </div>
    {/* Gender + Nationality — existing toggle buttons */}
    ...
    {/* Save/Cancel */}
    <div className="flex gap-3 pt-2">
      <button onClick={cancelEditing} className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50">{t('profile.cancel')}</button>
      <button onClick={saveSection} disabled={saving} className="flex-1 px-4 py-2.5 bg-primary-500 text-white rounded-lg text-sm font-medium hover:bg-primary-600 disabled:opacity-50">{saving ? '...' : t('profile.save')}</button>
    </div>
  </div>
)}
```

**Step 4: Section 2 (Contact & Location) — view/edit**

View mode:
- State: text
- Address: text
- Phone: text

Edit mode: existing select/textarea/input fields + Save/Cancel buttons.

**Step 5: Section 3 (Family & Background) — view/edit**

View mode:
- Income: text
- Siblings: number
- Colour blindness: Yes/No
- Disability: Yes/No

Edit mode: existing select/input/checkboxes + Save/Cancel buttons.

**Step 6: Section 4 (Course Interests) — no change**

This section stays as-is (it has its own inline editing for status).

**Step 7: Remove the global "Save Changes" button**

Delete the bottom save button and `lastSaved` display (lines 422-434). Each section now saves independently.

**Step 8: Import maskIc utility**

```typescript
import { maskIc } from '@/lib/ic-utils'
```

**Step 9: Test manually**

- View profile page — all sections show read-only values
- Click Edit on Identity → fields become editable, other sections stay view-only
- Click Cancel → values revert
- Click Save → API call, values persist, section returns to view mode
- IC always shows as `****-**-1234`
- Other sections work the same way

**Step 10: Commit**

```bash
git add halatuju-web/src/app/profile/page.tsx
git commit -m "feat: profile page view/edit per-section redesign with masked IC display"
```

---

### Task 7: Integration Testing and Polish

**Files:**
- Various (bug fixes found during testing)

**Step 1: Test the full flow end-to-end**

1. Fresh user: Landing → Start → Grades → Dashboard → Load More → Auth Gate → Gmail → IC Gate → Profile step → Dashboard
2. Verify IC is saved to backend (`getProfile` returns `nric`)
3. Verify profile page shows masked IC
4. Verify incompleteness badge shows correct count
5. Fill all fields → badge disappears

**Step 2: Test edge cases**

- IC with leading zeros (e.g., born in January)
- IC with state code 21 (Sabah)
- Phone OTP flow (instead of Gmail) → should also hit IC gate
- Returning user (already has IC) → IC gate should be skipped

**Step 3: Handle returning users — skip IC gate if NRIC already exists**

In `AuthGateModal.tsx`, modify the effect that advances step after auth:

```typescript
useEffect(() => {
  if (isAuthenticated && authGateReason && step !== 'ic' && step !== 'profile') {
    const googleName = session?.user?.user_metadata?.full_name
      || session?.user?.user_metadata?.name
    if (googleName && !name) setName(googleName)

    // If user already has NRIC, skip IC gate
    // Check via getProfile
    if (token) {
      getProfile({ token }).then(profile => {
        if (profile.nric) {
          setIc(profile.nric)
          setIcValid(true)
          setStep('profile')
        } else {
          setStep('ic')
        }
      }).catch(() => setStep('ic'))
    } else {
      setStep('ic')
    }
    setError(null)
  }
}, [isAuthenticated, authGateReason, step, session, name, token])
```

Import `getProfile` at the top of AuthGateModal.

**Step 4: Run existing tests**

Run: `cd halatuju_api && python manage.py test --parallel`
Expected: All 424 tests pass. Golden masters unchanged.

**Step 5: Commit**

```bash
git add halatuju-web/src/components/AuthGateModal.tsx
git commit -m "feat: skip IC gate for returning users who already have NRIC"
```

---

### Task 8: Final Cleanup and Sprint Close

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/technical-debt.md` (if any items resolved)

**Step 1: Update CHANGELOG**

Add entry under current sprint heading with all changes from this feature.

**Step 2: Commit and push**

```bash
git add -A
git commit -m "docs: IC gate + profile redesign sprint — changelog update"
git push
```

---

## Summary of Changes

| File | Action | What |
|------|--------|------|
| `src/lib/ic-utils.ts` | Create | IC validation, formatting, masking utilities |
| `src/lib/__tests__/ic-utils.test.ts` | Create | Unit tests for IC utilities |
| `src/components/IcInput.tsx` | Create | Reusable IC input component with auto-dash |
| `src/lib/useProfileCompleteness.ts` | Create | Hook to count unfilled profile fields |
| `src/components/AuthGateModal.tsx` | Modify | Add IC step, remove school input |
| `src/lib/api.ts` | Modify | Add `nric` to `SyncProfileData` |
| `src/components/AppHeader.tsx` | Modify | Add incompleteness badge |
| `src/app/profile/page.tsx` | Modify | View/edit per-section, masked IC |
| `src/messages/en.json` | Modify | Add ~11 new i18n keys |
| `src/messages/ms.json` | Modify | Add ~11 new i18n keys |
| `src/messages/ta.json` | Modify | Add ~11 new i18n keys |
