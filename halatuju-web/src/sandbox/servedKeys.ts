/**
 * TD-623: the `page_keys` the server serves on `GET admin/role/` for the sandbox's viewers. The web
 * reads the served keys only (the role is a label), so a sandbox viewer without them would see a
 * page with every door shut — not what a real org_admin sees. Copied from the T5c served payloads
 * (`src/lib/__tests__/fixtures/t5cServedPayloads.json`, `org_admin`); a reviewer holds `review` only
 * and a mentor holds none.
 */
export const ORG_ADMIN_PAGE_KEYS: readonly string[] = [
  'invitations.view', 'invitations.edit', 'team.view', 'sources.view', 'sources.edit',
  'sponsors.view', 'sponsors.edit', 'sponsors.check', 'sponsors.approve', 'billing.view', 'billing.edit',
  'requests.view', 'requests.edit', 'requests.approve', 'settings.edit',
  'students.view', 'students.edit', 'students.approve', 'contracts.view', 'contracts.edit', 'programmes.edit',
  'announcements.view', 'announcements.edit', 'surveys.view', 'surveys.edit',
  'development.view', 'development.edit', 'mentoring.view', 'mentoring.edit',
  'payments.view', 'payments.prepare', 'payments.check', 'payments.approve', 'spending.view', 'spending.edit', 'qc',
]

export const REVIEWER_PAGE_KEYS: readonly string[] = ['review']

export const MENTOR_PAGE_KEYS: readonly string[] = []
