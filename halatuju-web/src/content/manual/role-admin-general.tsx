import type { ManualChapter } from './types'

/** General admin chapter — the view-only remit. */
export const roleAdminGeneral: ManualChapter = {
  slug: 'role-admin-general',
  title: 'General admin',
  group: 'role',
  role: 'admin',
  blurb: 'A read-only window on your whole organisation.',
  sections: [
    {
      anchor: 'admin-general-remit',
      title: 'Your read-only remit',
      body: (
        <>As a <strong>general admin</strong> you have a <strong>read-only</strong> view of everything in your
        organisation. You can see all applications, the Sponsors list, and the Administration staff list — but you
        don&rsquo;t <em>act</em> on them. It&rsquo;s oversight without operational control.</>
      ),
    },
    {
      anchor: 'admin-general-what-you-see',
      title: 'What you can see',
      body: (
        <>Your organisation&rsquo;s <strong>B40 Applications</strong> (all of them, to read), the
        <strong> Sponsors</strong> list, and the <strong>Administration</strong> page&rsquo;s organisation staff
        table. You won&rsquo;t see another organisation&rsquo;s data, and you won&rsquo;t see the platform-only
        tools.</>
      ),
    },
    {
      anchor: 'admin-general-why-no-buttons',
      title: 'Why action buttons don’t appear',
      body: (
        <>Because your role is view-only, the buttons that <em>change</em> things simply aren&rsquo;t shown to
        you — no invite, resend or revoke on the staff table, no approve/reject on sponsors, no verdict controls on
        a case. If you need something done, ask your <strong>organisation admin</strong> (or the HalaTuju team).
        This keeps a clean line between who <em>sees</em> and who <em>acts</em>.</>
      ),
    },
  ],
}
