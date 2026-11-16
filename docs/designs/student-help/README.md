# Student help fixes: design hand-off (2026-11-15)

## Stitch (project 10844973747787673276)
- stitch_3.png = load-error state. Node-id 1d8a45619f4748d69691cdcdbecc5f4b
  Preview: https://stitch.withgoogle.com/preview/10844973747787673276?node-id=1d8a45619f4748d69691cdcdbecc5f4b
  (Stitch rendered it 2560x2048 desktop frame despite deviceType MOBILE; the layout is a mobile column.)
- Mock-ups 1, 2 and 4: three Stitch generates (Action Centre, "I don't have this", sample sheet) timed out, were retried once with shorter prompts, and still did not appear in list_screens after ~7 minutes (no node-id obtainable). They may surface later in the Stitch UI as duplicates; they can be ignored or deleted.
- Fallback: hand-built HTML mock-ups in the site's look (Lexend, #137fec, rounded white cards), 390 px wide:
  - mock_1.png  Action Centre, 3 sections, progress bar, all card states
  - mock_2.png  "I don't have this", states 1-3 (electricity bill)
  - mock_4.png  Sample viewer sheet (uses samples/payslip.svg)
  - HTML sources: mock_1.html, mock_2.html, mock_4.html

## Samples (samples/)
mykad, results_slip, payslip, offer_letter, str, epf_statement, electricity_bill, water_bill: .svg + .png each, plus all_samples.png (contact sheet). All words are plain <text> elements.
