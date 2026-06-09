'use client'

import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

// Promise-card icons (lock / shield-check / people) — inline SVG to match the app.
const PROMISE_ICONS: Record<string, string> = {
  card1: 'M12 11V7a4 4 0 10-8 0v4M5 11h14a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7a2 2 0 012-2z',
  card2: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
  card3: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 10-4 0M19 8a3 3 0 11-6 0 3 3 0 016 0z',
}
const PROMISE_CARDS = ['card1', 'card2', 'card3'] as const
const STEPS = [1, 2, 3, 4] as const
const FAQS = [1, 2, 3, 4, 5, 6] as const

/** F1 — the public sponsor marketing landing. Rendered at /sponsor for visitors
 *  who are not signed in (and only while the programme is live, i.e. the count
 *  endpoint reports `enabled`). `count` is the number of students currently
 *  waiting in the anonymised pool — shown as a live counter in the hero. */
export default function SponsorLanding({ count }: { count: number }) {
  const { t } = useT()
  const [openFaq, setOpenFaq] = useState<number | null>(1)

  return (
    <>
      {/* Unified app header (carries the Student/Sponsor/Partner "Log in" dropdown +
          the B40 Aid nav). The page's own hero/CTAs handle "Become a sponsor". */}
      <AppHeader />

      <main className="bg-gray-50">
        {/* Hero — text + image, with a live "students waiting" counter under the CTAs */}
        <section className="container mx-auto px-6 pt-6 pb-10 lg:pt-14 lg:pb-16 max-w-2xl lg:max-w-6xl">
          <div className="lg:grid lg:grid-cols-2 lg:gap-12 lg:items-center">
            <div className="relative w-full h-60 lg:h-[26rem] rounded-2xl overflow-hidden mb-6 lg:mb-0 lg:order-2">
              <Image src="/scholarship/hero.jpg" alt="" fill priority
                className="object-cover object-center" sizes="(max-width:1024px) 100vw, 600px" />
            </div>
            <div className="lg:order-1">
              <h1 className="text-3xl lg:text-5xl font-bold text-gray-900 leading-tight">{t('sponsorLanding.hero.heading')}</h1>
              <p className="text-gray-600 mt-3 lg:mt-4 lg:text-lg">{t('sponsorLanding.hero.sub')}</p>
              <div className="mt-5 lg:mt-7 flex flex-col sm:flex-row sm:items-center gap-3">
                <Link href="/sponsor/register"
                  className="bg-blue-600 text-white font-semibold px-6 py-3 rounded-xl hover:bg-blue-700 transition-colors text-center w-full sm:w-auto">
                  {t('sponsorLanding.hero.becomeSponsor')} →
                </Link>
                <a href="#how" className="text-blue-600 text-sm text-center sm:text-left font-medium">
                  {t('sponsorLanding.hero.howItWorks')} ↓
                </a>
              </div>
              {count > 0 && (
                <div className="mt-5 inline-flex items-center gap-2 rounded-full bg-blue-50 border border-blue-100 px-4 py-2 text-sm text-blue-800">
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l6.16-3.42A12 12 0 0112 21a12 12 0 01-6.16-10.42L12 14z" />
                  </svg>
                  <span>{t('sponsorLanding.hero.counter', { count: String(count) })}</span>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Why sponsor — three promise cards */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-5xl">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 lg:mb-6">{t('sponsorLanding.promises.title')}</h2>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 md:gap-5">
            {PROMISE_CARDS.map((c) => (
              <div key={c} className="bg-white rounded-2xl p-5 shadow-sm">
                <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center mb-2">
                  <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d={PROMISE_ICONS[c]} />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-900">{t(`sponsorLanding.promises.${c}Title`)}</h3>
                <p className="text-sm text-gray-500 mt-1">{t(`sponsorLanding.promises.${c}Desc`)}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How it works — four numbered steps */}
        <section id="how" className="scroll-mt-20 container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-6xl">
          <h2 className="text-2xl font-bold text-gray-900 mb-6">{t('sponsorLanding.how.title')}</h2>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((n) => (
              <li key={n} className="bg-white rounded-2xl p-5 shadow-sm">
                <span className="w-8 h-8 rounded-full bg-blue-600 text-white text-sm font-semibold flex items-center justify-center mb-3">
                  {n}
                </span>
                <h3 className="font-semibold text-gray-900">{t(`sponsorLanding.how.step${n}Title`)}</h3>
                <p className="text-sm text-gray-500 mt-1">{t(`sponsorLanding.how.step${n}Desc`)}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* FAQ — accordion */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-5xl">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 lg:mb-6">{t('sponsorLanding.faq.title')}</h2>
          <div className="grid gap-2 lg:grid-cols-2 lg:gap-x-5 lg:items-start">
            {FAQS.map((i) => {
              const open = openFaq === i
              return (
                <div key={i} className="bg-white rounded-xl shadow-sm self-start">
                  <button type="button" aria-expanded={open}
                    onClick={() => setOpenFaq(open ? null : i)}
                    className="w-full flex items-center justify-between gap-3 p-4 text-left">
                    <span className="font-medium text-gray-900 text-sm">{t(`sponsorLanding.faq.q${i}`)}</span>
                    <svg className={`w-5 h-5 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {open && <p className="px-4 pb-4 text-sm text-gray-600 leading-relaxed">{t(`sponsorLanding.faq.a${i}`)}</p>}
                </div>
              )
            })}
          </div>
        </section>

        {/* Closing CTA */}
        <section className="container mx-auto px-6 pb-12 lg:pb-20 max-w-2xl lg:max-w-5xl">
          <div className="bg-blue-50 border border-blue-100 rounded-2xl p-6 lg:p-10 text-center">
            <h2 className="text-2xl lg:text-3xl font-bold text-gray-900">{t('sponsorLanding.cta.heading')}</h2>
            <p className="text-gray-700 mt-2 lg:text-lg">{t('sponsorLanding.cta.body')}</p>
            <Link href="/sponsor/register"
              className="bg-blue-600 text-white font-semibold px-6 py-3 rounded-xl hover:bg-blue-700 transition-colors inline-block mt-5 w-full sm:w-auto">
              {t('sponsorLanding.hero.becomeSponsor')} →
            </Link>
            <p className="text-xs text-gray-500 mt-4">
              {t('sponsorLanding.cta.questions')}{' '}
              <a href="mailto:info@halatuju.xyz" className="text-blue-600 underline">info@halatuju.xyz</a>
            </p>
          </div>
        </section>
      </main>
      <AppFooter />
    </>
  )
}
