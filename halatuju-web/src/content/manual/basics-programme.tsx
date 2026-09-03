import type { ManualChapter } from './types'

/** Basics 1 — the programme picture (generalised from the reviewer guide's welcome). */
export const basicsProgramme: ManualChapter = {
  slug: 'basics-programme',
  title: 'The programme',
  group: 'basics',
  blurb: 'What the B40 programme is and how a case flows through it.',
  sections: [
    {
      anchor: 'what-it-is',
      title: 'What the B40 assistance programme is',
      body: (
        <>You&rsquo;re helping the <strong>B40 assistance programme</strong>, which supports students from
        lower-income families to continue into further study. Whatever your role, this is the work you&rsquo;re
        part of:
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>Students <strong>apply online</strong> at halatuju.xyz.</li>
            <li>The system checks eligibility and <strong>shortlists</strong> those who qualify — a B40
            background, a solid academic record, and a clear study pathway.</li>
            <li>Shortlisted students are <strong>guided to complete</strong> their application: uploading
            documents, confirming family and income details, and answering follow-up questions.</li>
            <li>A <strong>reviewer</strong> checks the key facts and talks to the student; a <strong>QC</strong>
            gives it a second pair of eyes; the recommendation goes to sponsors, who fund the award.</li>
          </ul></>
      ),
    },
    {
      anchor: 'how-a-case-flows',
      title: 'How a case flows',
      body: (
        <>A case moves through clear stages: <strong>Shortlisted</strong> (invited to complete the application)
        → <strong>Awaiting review</strong> (the student has confirmed everything) → <strong>Interviewing</strong>
        → <strong>Interviewed</strong> (awaiting QC) → <strong>Recommended</strong> (QC accepted) →
        <strong> Awarded</strong> and beyond. The <em>Statuses</em> chapter explains each label. Your role decides
        which of these stages you act on — the rest you can see but leave to others.</>
      ),
    },
    {
      anchor: 'finding-your-way',
      title: 'Finding your way around',
      body: (
        <>Down the left is a narrow strip of icons — that is your menu. <strong>Point at it and it opens</strong>,
        showing the name of every page you can reach; move away and it closes again, so it takes up almost no
        room while you work. If you would rather it stayed open, use the <strong>pin</strong> beside the
        HalaTuju name at the top, and the console will remember. The page you are on is the coloured one.
        <br /><br />
        The pages are grouped by what they belong to: <strong>HalaTuju</strong> (the platform),
        <strong> your organisation</strong> — the people, the money and the paperwork — and
        <strong> your programme</strong>, which is one gift: its <strong>Configuration</strong> and its
        <strong> B40 Applications</strong>. If your organisation runs more than one gift, the trail across the
        top says which one you are in, and you can switch there. You only ever see the groups your role
        reaches, so a short menu is not a fault. An entry marked <em>soon</em> is a page still being built; you
        may well see none at all.
        <br /><br />
        Two shortcuts, once the strip is familiar. Pointing at an entry shows <em>Go to…</em> with a pair of
        keys — press <strong>G</strong>, then that letter, and you are there. <strong>Ctrl&nbsp;K</strong>
        opens a search box over the menu if you would rather type the name of a page than look for it.
        <br /><br />
        This manual has a chapter for <em>your</em> role — it opens there automatically — plus these shared
        <em> Basics</em>. When something isn&rsquo;t clear, the <strong>FAQ</strong> has short answers, and the
        HalaTuju team is one email away (<strong>help@halatuju.xyz</strong>).</>
      ),
    },
  ],
}
