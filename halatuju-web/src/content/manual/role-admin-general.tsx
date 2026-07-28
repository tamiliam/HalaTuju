import type { ManualChapter } from './types'

/** General admin chapter — the view-only remit. */
export const roleAdminGeneral: ManualChapter = {
  slug: 'role-admin-general',
  title: 'General admin',
  group: 'role',
  role: 'admin',
  blurb: 'Oversight of your whole organisation — and you prepare the money.',
  sections: [
    {
      anchor: 'admin-general-remit',
      title: 'Your remit',
      body: (
        <>As a <strong>general admin</strong> you can <strong>read</strong> everything in your organisation — all
        applications, the Sponsors list, the Administration staff table — without acting on any of it. No verdicts,
        no assignments, no staff changes. There is <strong>one exception, and it is money in</strong>: you are the
        person who <em>prepares</em> it. See <em>Money: you prepare, someone else approves</em> below.</>
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
      anchor: 'admin-general-money',
      title: 'Money: you prepare, someone else approves',
      body: (
        <>On both money paths you are the <strong>maker</strong> — the person who prepares the entry and signs it
        first. Nothing you prepare pays out or becomes spendable on your signature alone.
        <br /><br />
        <strong>A payment run</strong> (Administration → Payments): you build the month&rsquo;s run and sign it,
        then your <strong>organisation admin countersigns</strong> — and only at their countersignature is the
        instruction emailed out.
        <br /><br />
        <strong>A wallet credit</strong> (Sponsors → open a sponsor → <em>Record a credit</em>): when a sponsor
        transfers money to us off the platform, you record it against the gift it was given to, with the
        <strong> bank transfer reference</strong> — one row per transfer, so every credit can be matched back to a
        line on the statement. It is recorded as a <em>draft</em> and you then <strong>sign as recorder</strong>;
        your organisation admin countersigns, and only then is the money spendable on a student. Type your full
        name exactly as it appears on your account — a click on its own is not a signature.
        <br /><br />
        If you mis-key an amount or a reference, <strong>Void this credit</strong> while it is still unconfirmed;
        the row stays on the record as history. Once a credit is confirmed it can never be voided — a mistake
        after that is corrected by recording a balancing entry, so the trail always shows what happened.</>
      ),
    },
    {
      anchor: 'admin-general-why-no-buttons',
      title: 'Why other action buttons don’t appear',
      body: (
        <>Outside the money paths above, the buttons that <em>change</em> things simply aren&rsquo;t shown to
        you — no invite, resend or revoke on the staff table, no approve/reject on sponsors, no verdict controls on
        a case. If you need something done, ask your <strong>organisation admin</strong> (or the HalaTuju team).
        This keeps a clean line between who <em>sees</em> and who <em>acts</em>, and it is also why you cannot
        countersign your own work: every step of a money chain needs a different person.</>
      ),
    },
  ],
}
