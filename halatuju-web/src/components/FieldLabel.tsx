import InfoTip from './InfoTip'

/** Field label with an optional required `*` and an optional `i` tooltip.
 *  Shared by /apply and /scholarship/application Story tab so the asterisk
 *  convention stays consistent. */
export default function FieldLabel({
  children,
  required,
  tip,
}: {
  children: React.ReactNode
  required?: boolean
  tip?: string
}) {
  return (
    <span className="mb-1 flex items-center text-sm font-medium text-gray-700">
      {children}
      {required && <span className="ml-0.5 text-red-500" aria-hidden>*</span>}
      {tip && <InfoTip text={tip} />}
    </span>
  )
}
