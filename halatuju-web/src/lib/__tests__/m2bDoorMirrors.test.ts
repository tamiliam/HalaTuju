/**
 * Sprint M2b (D11): the four web label mirrors read the SERVER'S door from the served `page_keys`, and
 * an older payload (no `page_keys`) answers by the role list it had before.
 *
 *   Mentors tab (`mayReadMentors`)            -> `mentors_read`   (`mentor_invite.may_read`)
 *   a scholar's mentor (scholars list + file) -> `mentoring_read` (`mentoring.may_read_mentoring`)
 *   Team -> Emails (`mayEditEmails`)          -> `sources`        (`_SourcesBase`, the partner emails)
 *   the cockpit's witness card                -> `sources`        (`AdminApplicationWitnessView`)
 *
 * The door's KEYS are held to the server by `teamTablesT5cDoors.test.ts`; this pins that each web gate
 * asks the same door its endpoint asks, so a door renamed on one side fails here.
 */
import fs from 'fs'
import path from 'path'
import { mayReadMentors, opensDoorOr } from '../pageGuard'

const WEB = path.join(__dirname, '..', '..')
const API = path.join(WEB, '..', '..', 'halatuju_api', 'apps', 'scholarship')
const read = (...p: string[]) => fs.readFileSync(path.join(...p), 'utf8')

describe('mayReadMentors reads the served door', () => {
  it('a served payload answers by `mentoring.view`, whatever the label', () => {
    expect(mayReadMentors({ role: 'reviewer', page_keys: ['mentoring.view'] })).toBe(true)
    expect(mayReadMentors({ role: 'admin', page_keys: ['team.view', 'sponsors.view'] })).toBe(false)
    expect(mayReadMentors({ role: 'finance', page_keys: ['invitations.view', 'team.view'] })).toBe(false)
  })

  it('an older payload keeps the role list', () => {
    expect(mayReadMentors({ role: 'admin' })).toBe(true)
    expect(mayReadMentors({ role: 'finance' })).toBe(false)
  })
})

describe('each web gate asks the door its endpoint asks', () => {
  it('the server doors', () => {
    expect(read(API, 'mentor_invite.py')).toMatch(/def may_read\(caller\):[\s\S]*?opens_door\(caller, 'mentors_read'\)/)
    expect(read(API, 'mentoring.py')).toMatch(
      /def may_read_mentoring\(caller\):[\s\S]*?opens_door\(caller, 'mentoring_read'\)/)
    const sources = read(API, 'views_admin', 'sources.py')
    expect(sources).toMatch(/class _SourcesBase[\s\S]*?def may_open\(admin\):\s*return staff_tables\.opens_door\(admin, 'sources'\)/)
    expect(read(API, 'views_admin', 'lifecycle.py')).toMatch(/class AdminApplicationWitnessView\(_SourcesBase\)/)
    expect(read(API, 'views_admin', 'org_emails.py')).toMatch(/class AdminPartnerEmailsView\(_SourcesBase\)/)
  })

  it('the web gates', () => {
    const app = path.join(WEB, 'app', 'admin')
    for (const f of [['scholars', 'page.tsx'], ['scholars', '[id]', 'page.tsx']]) {
      expect(read(app, ...f)).toContain("opensDoorOr(role, 'mentoring_read', MENTORING_ROLES)")
    }
    expect(read(app, 'organisation', 'team', 'page.tsx')).toContain("mayEditEmails = opensDoorOr(role, 'sources',")
    expect(read(app, 'scholarship', '[id]', 'view.tsx')).toContain("canManageSources = opensDoorOr(role, 'sources',")
  })

  it('the served door decides; the role list answers only an older payload', () => {
    const ROLES = ['super', 'org_admin', 'admin']
    expect(opensDoorOr({ role: 'admin', page_keys: ['sources.view'] }, 'sources', ROLES)).toBe(false)
    expect(opensDoorOr({ role: 'reviewer', page_keys: ['sources.view', 'sources.edit'] }, 'sources', ROLES)).toBe(true)
    expect(opensDoorOr({ role: 'admin' }, 'sources', ROLES)).toBe(true)
    expect(opensDoorOr({ role: 'finance', page_keys: ['mentoring.view'] }, 'mentoring_read', ROLES)).toBe(true)
  })
})
