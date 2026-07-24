/**
 * Officer Blockers card — pure helpers (status gate, member-qualified codes, stuck step).
 * The blocker LIST itself is the backend's consent gate; these only route it to copy.
 */
import {
  BLOCKER_BOX_STATUSES, showsBlockerBox, parseBlocker, stepOf, stuckStep, blockerLabelKey,
  nudgeButton, NudgeState,
} from '@/lib/blockers'

describe('showsBlockerBox', () => {
  test('shows for shortlisted and profile_complete only', () => {
    expect(showsBlockerBox('shortlisted')).toBe(true)
    expect(showsBlockerBox('profile_complete')).toBe(true)
    for (const s of ['interviewing', 'interviewed', 'recommended', 'awarded', 'active', 'declined', '']) {
      expect(showsBlockerBox(s)).toBe(false)
    }
    expect(showsBlockerBox(null)).toBe(false)
    expect(showsBlockerBox(undefined)).toBe(false)
  })

  test('the gate is driven by one editable list (profile_complete is droppable)', () => {
    expect([...BLOCKER_BOX_STATUSES]).toEqual(['shortlisted', 'profile_complete'])
  })
})

describe('parseBlocker', () => {
  test('splits a member-qualified income code', () => {
    expect(parseBlocker('parent_ic_missing:mother')).toEqual({ code: 'parent_ic_missing', member: 'mother' })
    expect(parseBlocker('salary_slip_missing:father')).toEqual({ code: 'salary_slip_missing', member: 'father' })
  })
  test('leaves a bare code alone', () => {
    expect(parseBlocker('ic_missing')).toEqual({ code: 'ic_missing', member: '' })
  })
})

describe('blockerLabelKey', () => {
  test('member-qualified codes use the _member variant', () => {
    expect(blockerLabelKey('parent_ic_missing:mother'))
      .toBe('admin.scholarship.blockers.item.parent_ic_missing_member')
  })
  test('bare codes use the plain key', () => {
    expect(blockerLabelKey('str_missing')).toBe('admin.scholarship.blockers.item.str_missing')
  })
})

describe('stepOf', () => {
  test('section codes map to their own step', () => {
    expect(stepOf('quiz_incomplete')).toBe('quiz')
    expect(stepOf('story_incomplete')).toBe('story')
    expect(stepOf('family_incomplete')).toBe('story')
    expect(stepOf('address_incomplete')).toBe('story')
    expect(stepOf('funding_incomplete')).toBe('funding')
  })
  test('every document / identity / income code falls to Documents', () => {
    for (const c of ['ic_missing', 'results_slip_missing', 'offer_letter_missing', 'offer_not_official',
      'str_missing', 'parent_ic_missing', 'birth_certificate_missing', 'income_incomplete',
      'ic_name_mismatch', 'results_slip_unreadable']) {
      expect(stepOf(c)).toBe('documents')
    }
  })
  test('an unknown//future code still lands on Documents rather than breaking', () => {
    expect(stepOf('some_new_code')).toBe('documents')
  })
})

describe('stuckStep', () => {
  test('returns the EARLIEST outstanding step', () => {
    expect(stuckStep(['ic_missing', 'quiz_incomplete'])).toBe('quiz')
    expect(stuckStep(['ic_missing', 'address_incomplete'])).toBe('story')
    expect(stuckStep(['funding_incomplete', 'str_missing'])).toBe('funding')
  })
  test('documents-only blockers report Documents', () => {
    // #145's real shape: nothing uploaded at all, sections all done.
    expect(stuckStep(['ic_missing', 'results_slip_missing', 'offer_letter_missing',
      'str_missing', 'parent_ic_missing:mother', 'birth_certificate_missing'])).toBe('documents')
  })
  test('no blockers → null', () => {
    expect(stuckStep([])).toBeNull()
  })
})

describe('nudgeButton', () => {
  const base: NudgeState = { applicable: true, sent_at: null, available: false, available_at: null }

  test('hidden unless the caller can manage AND the state is applicable', () => {
    expect(nudgeButton(base, false).show).toBe(false)              // not org-admin/super
    expect(nudgeButton({ ...base, applicable: false }, true).show).toBe(false)
    expect(nudgeButton(null, true).show).toBe(false)               // null-safe
  })

  test('before the auto nudge: shown, blocked, "send", pending note', () => {
    const v = nudgeButton({ ...base, available_at: '2026-07-24T10:30:00Z' }, true)
    expect(v).toEqual({ show: true, enabled: false, label: 'send', note: 'pending' })
  })

  test('sent but inside cooldown: blocked, "again", cooldown note', () => {
    const v = nudgeButton({ ...base, sent_at: '2026-07-24T10:00:00Z', available: false,
      available_at: '2026-07-25T10:00:00Z' }, true)
    expect(v).toEqual({ show: true, enabled: false, label: 'again', note: 'cooldown' })
  })

  test('available again: enabled, "again", sent note', () => {
    const v = nudgeButton({ ...base, sent_at: '2026-07-23T10:00:00Z', available: true }, true)
    expect(v).toEqual({ show: true, enabled: true, label: 'again', note: 'sent' })
  })
})
