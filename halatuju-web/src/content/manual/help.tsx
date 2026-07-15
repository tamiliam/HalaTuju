import type { ManualChapter } from './types'

/** Help group — where to go next. */
export const helpChapter: ManualChapter = {
  slug: 'help-getting-help',
  title: 'Getting help',
  group: 'help',
  blurb: 'The FAQ, and how to reach the team.',
  sections: [
    {
      anchor: 'help-faq',
      title: 'The FAQ',
      body: (
        <>For short, specific answers, see the <strong>FAQ</strong> (in the top menu). It&rsquo;s grouped by role,
        so you can filter to the questions that apply to you — plus the ones everyone asks.</>
      ),
    },
    {
      anchor: 'help-contact',
      title: 'Contact the team',
      body: (
        <>Anything else — a login problem, something that looks wrong on a case, or a question this manual
        doesn&rsquo;t answer — email <strong>help@halatuju.xyz</strong>. We&rsquo;re glad to help.</>
      ),
    },
  ],
}
