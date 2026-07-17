# Lessons Learned

- A bare `N.N.` numbering token (e.g. `2.4.`, `2.5.`) is NEVER a field value — it is an offer body's
  section-clause header, and a label-anchored parser can latch it as the stream/institution (#47:
  a Form-6 offer whose `2.4. Bidang` / `2.5. Pusat Tingkatan Enam` labels landed as the values).
  Defend at BOTH ends: reject at READ (offer_parse defers the whole offer to Gemini) AND sanitise at
  WRITE (`card_display.sanitise_offer_slots` / autofill), mirroring the #125 date/mis-slot guard. The
  shared detector is `card_display.looks_like_clause_number`.
- When investigating data coverage or completeness, always query production Supabase directly — test fixtures are for logic testing and will show misleading zeros. (Ranking Improvements Sprint)
