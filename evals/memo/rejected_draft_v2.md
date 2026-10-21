## Recommendation

Next quarter's product effort should target **billing-support**. Its issues carry the largest combined severity among the four areas in the declared 173,000-review subset (scope: declared subset, not a full-corpus model run; all counts are subset sample counts).

## Evidence

- `billing.subscription_entitlement` is ranked 3rd with 6029 complaints [C1], severity_sum 16533 [C2], and mean severity 2.742246 [C3].
- `billing.premium_paywall` is ranked 4th with 5303 complaints [C4], severity_sum 15505 [C5], and mean severity 2.923817 [C6].
- `billing.charges_refund` is ranked 12th with 1387 complaints [C7], severity_sum 4015 [C8], and mean severity 2.894737 [C9].
- Topic aggregate: billing-support has 14683 complaint-or-cancellation records, 2950 cancellation records, and 876 severity-4-plus records. Its family severity total is 40813, second in family_rank_order_desc for severity_sum after usability.
- Usability has the largest severity total (43797), driven by `usability.ads` at rank 2 with 9817 complaints [C10], severity_sum 21052 [C11], and mean severity 2.144443 [C12]. Its severity-4-plus count is only 191 (topic aggregate).
- Playback has 2955 severity-4-plus records (topic aggregate) and `playback.crash_freeze` at rank 8 with mean severity 3.472921 [C13]. `playback.general` is rank 6 with mean severity 3.056008 [C14].
- Access has `access.login_failure` at rank 7 with the highest mean severity among ranked issues, 3.934722 [C15] and severity_sum 8499 [C16]. Access totals are the smallest of the four families.

Representative reviews: "Amount debited twice but still Premium account not renewed" (5157428f-8f40-4ce7-8e24-2d2c438b212c); "you used an old and destroyed card to pay for this months fee" (feded429-c541-464a-b77d-a23bcde044a4).

## Alternatives compared

- **usability**: largest family severity total and most complaints, but mostly lower severity; `usability.ads` is rank 2.
- **playback**: strongest severity-4-plus signal in the topic aggregates; `playback.crash_freeze` (rank 8) and `playback.general` (rank 6) are the main issues.
- **access**: highest mean severity for `access.login_failure` (rank 7), but the smallest family totals.

Billing-support ranks second in cancellation-language records (topic aggregate) and second on severity and priority totals, which supports prioritising it over the others for this quarter.

## Limitations

- Reviews are self-selected and historical.
- Cancellation language indicates intent, not confirmed churn.
- There is no revenue or plan data.
- Model labels have measured disagreement.
- Unresolved and quarantined records are excluded from counts.
- The `other.general_dislike` issue is outside the four options and is reported only in topic aggregates.
