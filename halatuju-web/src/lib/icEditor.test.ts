import {
  canEditIc, hasIcFlags, icFieldValue, icFixableSide, icFlags,
} from './icEditor'

/**
 * The padlock rule. These exist because the padlock was hard-coded from the day the field was
 * built and nobody noticed: `disabled` was a bare attribute, so 85 of 143 production applicants
 * were being told their IC was locked when nothing had locked it.
 */
describe('canEditIc', () => {
  it('allows editing only when the STORED lock says unlocked', () => {
    expect(canEditIc({ nric_locked: false })).toBe(true)
    expect(canEditIc({ nric_locked: true })).toBe(false)
  })

  it('treats a payload without the field as LOCKED', () => {
    // An old client offering an edit the server would refuse is worse than offering none.
    expect(canEditIc({})).toBe(false)
    expect(canEditIc(null)).toBe(false)
    expect(canEditIc(undefined)).toBe(false)
  })

  it('ignores identity_verified entirely', () => {
    // The trap this whole sprint turns on: identity_verified is broader AND derived, so keying
    // the padlock on it would lock with no genuineness check and unlock on card deletion.
    const badge = { nric_locked: false, identity_verified: true } as Parameters<typeof canEditIc>[0]
    expect(canEditIc(badge)).toBe(true)
  })
})

describe('icFieldValue', () => {
  it('shows the real number while editing and the mask at rest', () => {
    expect(icFieldValue('080722-14-1140', '****-**-1140', true)).toBe('080722-14-1140')
    expect(icFieldValue('080722-14-1140', '****-**-1140', false)).toBe('****-**-1140')
  })

  it('never puts the mask into an editable box', () => {
    // Enabling the old field as-is would have let a student edit '****-**-2022' and submit
    // asterisks. Asserted directly because it is the failure that would look like it worked.
    const editing = icFieldValue('080722-14-1140', '****-**-1140', true)
    expect(editing).not.toContain('*')
  })

  it('is empty when there is no number yet', () => {
    expect(icFieldValue('', '', true)).toBe('')
  })
})

describe('icFlags', () => {
  it('keeps the codes we have copy for', () => {
    expect(icFlags(['nric_one_digit', 'name_incomplete']))
      .toEqual(['nric_one_digit', 'name_incomplete'])
  })

  it('drops anything unrecognised rather than rendering a raw key', () => {
    // A new server-side code must not surface as 'profile.icFlag.some_new_thing' on screen —
    // that exact failure shipped on this project before (47 raw key paths, four sprints).
    expect(icFlags(['nric_differs', 'invented_later'])).toEqual(['nric_differs'])
  })

  it('handles nothing at all', () => {
    expect(icFlags(undefined)).toEqual([])
    expect(icFlags([])).toEqual([])
    expect(hasIcFlags(undefined)).toBe(false)
    expect(hasIcFlags(['nric_one_digit'])).toBe(true)
  })
})

describe('icFixableSide', () => {
  it('points at the number when it differs and the record is unlocked', () => {
    expect(icFixableSide(['nric_one_digit'], true)).toBe('nric')
  })

  it('points at the name whether or not the IC is locked', () => {
    // The name field has always been editable and the lock does not cover it.
    expect(icFixableSide(['name_incomplete'], false)).toBe('name')
    expect(icFixableSide(['name_differs'], true)).toBe('name')
  })

  it('points at both when both differ and the number is still editable', () => {
    expect(icFixableSide(['nric_differs', 'name_differs'], true)).toBe('both')
  })

  it('says NEITHER on a locked record whose number differs', () => {
    // The orphaned-claim case. Telling them to correct a field they cannot change would be
    // the same dead end Gopal already sends them into.
    expect(icFixableSide(['nric_differs'], false)).toBe('neither')
  })

  it('says neither when nothing differs', () => {
    expect(icFixableSide([], true)).toBe('neither')
    expect(icFixableSide(undefined, true)).toBe('neither')
  })
})
