'use client'

import { useState } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import AppHeader from '@/components/AppHeader'
import AppFooter from '@/components/AppFooter'
import { useT } from '@/lib/i18n'

// Value-card icons (seedling / people / lock) — inline SVG to match the app.
const CARD_ICONS: Record<string, string> = {
  card1: 'M12 22c4-2 7-5.5 7-10V5l-7-3-7 3v7c0 4.5 3 8 7 10z',
  card2: 'M17 20h5v-2a4 4 0 00-3-3.87M9 20H4v-2a4 4 0 013-3.87m6-1.13a4 4 0 10-4 0M19 8a3 3 0 11-6 0 3 3 0 016 0z',
  card3: 'M12 11V7a4 4 0 10-8 0v4M5 11h14a2 2 0 012 2v7a2 2 0 01-2 2H5a2 2 0 01-2-2v-7a2 2 0 012-2z',
}
const VALUE_CARDS = ['card1', 'card2', 'card3'] as const
const NOTE_BULLETS = ['pilot', 'noGuarantee', 'strict', 'accurate', 'confidential'] as const
const REQ_ITEMS = ['item1', 'item2', 'item3', 'item4', 'item5'] as const
const STEPS = [1, 2, 3, 4, 5, 6, 7, 8] as const
const FAQS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as const

const CheckIcon = () => (
  <svg className="w-5 h-5 text-primary-500 shrink-0 mt-0.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

export default function ScholarshipLandingPage() {
  const { t } = useT()
  const [openFaq, setOpenFaq] = useState<number | null>(null)

  return (
    <>
      <AppHeader />
      <main className="bg-gray-50">
        {/* Hero — single column on mobile, text + image side by side on desktop */}
        <section className="container mx-auto px-6 pt-6 pb-10 lg:pt-14 lg:pb-16 max-w-2xl lg:max-w-6xl">
          <div className="lg:grid lg:grid-cols-2 lg:gap-12 lg:items-center">
            <div className="relative w-full h-60 lg:h-[26rem] rounded-2xl overflow-hidden mb-6 lg:mb-0 lg:order-2">
              <Image
                src="/scholarship/hero.jpg" alt="" fill priority
                className="object-cover object-center" sizes="(max-width:1024px) 100vw, 600px"
              />
            </div>
            <div className="lg:order-1">
              <h1 className="text-3xl lg:text-5xl font-bold text-gray-900 leading-tight">{t('scholarship.landing.hero.heading')}</h1>
              <p className="text-gray-600 mt-3 lg:mt-4 lg:text-lg">{t('scholarship.landing.hero.sub')}</p>
              <div className="mt-5 lg:mt-7 flex flex-col sm:flex-row sm:items-center gap-3">
                <Link href="/scholarship/apply" className="btn-primary text-center w-full sm:w-auto">{t('scholarship.landing.hero.apply')} →</Link>
                <a href="#requirements" className="text-primary-600 text-sm text-center sm:text-left font-medium">{t('scholarship.landing.hero.seeQualify')} ↓</a>
              </div>
            </div>
          </div>
        </section>

        {/* Overview + value cards */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-5xl">
          <div className="lg:max-w-3xl">
            <p className="text-gray-700 lg:text-lg">{t('scholarship.landing.overview.p1')}</p>
            <p className="text-gray-700 mt-3 lg:text-lg">{t('scholarship.landing.overview.p2')}</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 md:gap-5 mt-6 lg:mt-8">
            {VALUE_CARDS.map((c) => (
              <div key={c} className="bg-white rounded-2xl p-5 shadow-sm">
                <div className="w-10 h-10 rounded-full bg-primary-50 flex items-center justify-center mb-2">
                  <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d={CARD_ICONS[c]} />
                  </svg>
                </div>
                <h3 className="font-semibold text-gray-900">{t(`scholarship.landing.${c}.title`)}</h3>
                <p className="text-sm text-gray-500 mt-1">{t(`scholarship.landing.${c}.desc`)}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Can you apply? + Please note — side by side on desktop, headings top-aligned */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-5xl">
          <div className="lg:grid lg:grid-cols-2 lg:gap-6 lg:items-start">
            {/* Can you apply? (left) */}
            <div id="requirements" className="scroll-mt-24 mb-6 lg:mb-0">
              <h2 className="text-2xl font-bold text-gray-900 mb-4">{t('scholarship.landing.req.title')}</h2>
              <div className="bg-white rounded-2xl shadow-sm divide-y divide-gray-100">
                {REQ_ITEMS.map((it) => (
                  <div key={it} className="flex items-start gap-3 p-4">
                    <CheckIcon />
                    <span className="text-sm text-gray-700">{t(`scholarship.landing.req.${it}`)}</span>
                  </div>
                ))}
              </div>
              <p className="text-sm text-gray-500 italic mt-3">{t('scholarship.landing.req.closeNote')}</p>
            </div>

            {/* Please note (right) — heading above the card so its top aligns with "Can you apply?" */}
            <div>
              <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                {t('scholarship.landing.note.title')}
              </h2>
              <div className="bg-primary-50 border-l-4 border-primary-500 rounded-2xl p-5">
                <ul className="space-y-2.5 text-sm text-gray-700">
                  {NOTE_BULLETS.map((b) => (
                    <li key={b}>
                      <span className="font-semibold text-gray-900">{t(`scholarship.landing.note.${b}Label`)}:</span>{' '}
                      {t(`scholarship.landing.note.${b}Text`)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </section>

        {/* How it works — vertical list on mobile, 4-up step cards on desktop */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-6xl">
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <h2 className="text-2xl font-bold text-gray-900">{t('scholarship.landing.how.title')}</h2>
            <span className="inline-block text-xs bg-primary-50 text-primary-700 rounded-full px-3 py-1">
              {t('scholarship.landing.how.rolling')}
            </span>
          </div>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((n) => (
              <li key={n} className="bg-white rounded-2xl p-5 shadow-sm">
                <span className="w-8 h-8 rounded-full bg-primary-500 text-white text-sm font-semibold flex items-center justify-center mb-3">
                  {n}
                </span>
                <h3 className="font-semibold text-gray-900">{t(`scholarship.landing.how.step${n}Title`)}</h3>
                <p className="text-sm text-gray-500 mt-1">{t(`scholarship.landing.how.step${n}Desc`)}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* FAQ — single column on mobile, two columns on desktop */}
        <section className="container mx-auto px-6 pb-10 lg:pb-14 max-w-2xl lg:max-w-5xl">
          <h2 className="text-2xl font-bold text-gray-900 mb-4 lg:mb-6">{t('scholarship.landing.faq.title')}</h2>
          <div className="grid gap-2 lg:grid-cols-2 lg:gap-x-5 lg:items-start">
            {FAQS.map((i) => {
              const open = openFaq === i
              return (
                <div key={i} className="bg-white rounded-xl shadow-sm self-start">
                  <button
                    type="button" aria-expanded={open}
                    onClick={() => setOpenFaq(open ? null : i)}
                    className="w-full flex items-center justify-between gap-3 p-4 text-left"
                  >
                    <span className="font-medium text-gray-900 text-sm">{t(`scholarship.landing.faq.q${i}`)}</span>
                    <svg className={`w-5 h-5 text-gray-400 shrink-0 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {open && <p className="px-4 pb-4 text-sm text-gray-600 leading-relaxed">{t(`scholarship.landing.faq.a${i}`)}</p>}
                </div>
              )
            })}
          </div>
        </section>

        {/* Closing CTA — stacked on mobile, image + text side by side on desktop */}
        <section className="container mx-auto px-6 pb-12 lg:pb-20 max-w-2xl lg:max-w-5xl">
          <div className="bg-white rounded-2xl shadow-sm overflow-hidden lg:grid lg:grid-cols-2 lg:items-stretch">
            <div className="relative w-full h-48 lg:h-auto lg:min-h-[18rem]">
              <Image src="/scholarship/community.jpg" alt="" fill className="object-cover" sizes="(max-width:1024px) 100vw, 600px" />
            </div>
            <div className="p-6 lg:p-10 text-center lg:text-left lg:flex lg:flex-col lg:justify-center">
              <h2 className="text-2xl lg:text-3xl font-bold text-gray-900">{t('scholarship.landing.cta.heading')}</h2>
              <p className="text-gray-600 mt-2 text-sm lg:text-base">{t('scholarship.landing.cta.body')}</p>
              <Link href="/scholarship/apply" className="btn-primary w-full sm:w-auto mt-4 inline-block text-center self-center lg:self-start">
                {t('scholarship.landing.hero.apply')} →
              </Link>
              <p className="text-xs text-gray-400 mt-3">
                {t('scholarship.landing.cta.questions')}{' '}
                <a href="mailto:info@halatuju.xyz" className="text-primary-600 underline">info@halatuju.xyz</a>
              </p>
            </div>
          </div>
        </section>
      </main>
      <AppFooter />
    </>
  )
}
