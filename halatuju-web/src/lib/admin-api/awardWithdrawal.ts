/** A1.13b: the case detail's `withdrawal_request` (`award_withdrawal_chain.payload_for`). With no request
 *  yet only `id` (null), `status` (null) and `your_step` are sent. `your_step` is the ONE server predicate
 *  (`next_step_for`): 'request' (may ask), 'decide' (may approve or refuse), 'cancel' (the maker), or null
 *  (read only — a super always). Amounts are decimal strings, as the snapshot stored them at the request. */
export interface AwardWithdrawalRequest {
  id: number | null
  status: 'pending' | 'approved' | 'refused' | 'cancelled' | 'expired' | null
  your_step: 'request' | 'decide' | 'cancel' | null
  requested_by_name?: string
  requested_at?: string
  expires_at?: string
  explanation?: string
  /** How many holding sponsorships the withdrawal ends. */
  sponsorship_count?: number
  /** What goes back to the sponsors' balance (their holding sponsorships' sum). */
  amount_freed?: string | null
  /** How many scheduled or due payments stop. */
  tranches_to_withhold?: number
  decided_by_name?: string
  decided_at?: string | null
  decision_note?: string
}
