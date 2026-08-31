import { fundedFraction } from '@/lib/poolCard'

/**
 * The sponsor funding bar: an empty rail when unfunded, partial fill when partially
 * funded, full when fully funded. Driven by funded_amount / award_amount from the
 * allowlist card. Today every pooled student reads 0 (funding is full-or-nothing and a
 * funded student leaves the pool), so it renders as the empty rail; when partial funding
 * (TD-075) ships the same props drive partial/full with no change here. Caption-free by
 * owner decision — the RM amount already shows alongside.
 */
export function FundingBar({
  funded,
  award,
  className = '',
}: {
  funded: string | number | null | undefined
  award: string | number | null | undefined
  className?: string
}) {
  const pct = Math.round(fundedFraction(funded, award) * 100)
  return (
    <div
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Funding progress"
      className={`h-1.5 w-full overflow-hidden rounded-full bg-ground-100 ${className}`}
    >
      {/* BRAND, not the info tone — corrected by hand after the codemod (F2a). A progress fill
          carries no semantic state: it is not "information", it is this product's own measure of
          how far something has got. `ActionCentre`'s identical bar was already `bg-primary-500`,
          so leaving this one a tone would mean a tenant sets their colour and one bar follows
          while the other stays blue. */}
      <div
        className="h-full rounded-full bg-primary-600 transition-[width] duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}
