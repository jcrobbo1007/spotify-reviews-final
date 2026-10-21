## Recommendation

Next quarter's product effort should target **usability**, specifically the shuffle/queue controls and the ad experience, because usability holds the highest-ranked issues in this pilot sample.

## Evidence

Scope: this memo covers a declared 100-review cost pilot (cost_100.csv), a subset and not the full corpus. All counts are pilot sample counts.

The top-ranked issue is `other.general_dislike` with complaint_count 15 [C1], severity_sum 31 [C2], and priority_score 31 [C3]. Because it is a catch-all bucket with mean_severity 2.066667 [C4], it does not point to a specific fix.

The strongest actionable usability issue is `usability.shuffle_queue` at rank 2, with complaint_count 7 [C5], severity_sum 18 [C6], mean_severity 2.571429 [C7], and priority_score 18 [C8]. Reviewers describe being unable to skip, queue, or choose songs without Premium, for example: "You can't even listen to music you want it just shuffles it" (review a78d831a-69f4-428a-9235-cfdd9775c509).

`usability.ads` is at rank 3, with complaint_count 8 [C9], severity_sum 16 [C10], mean_severity 2.000000 [C11], and priority_score 16 [C12]. Reviewers report frequent interruptions, for example: "it's always every 1 or 2 song then instant ads" (review 3e8bdc92-4934-457e-85cc-8b9d14bf51c0).

Topic aggregate: usability has 17 records, 3 cancellation-language records, and a severity sum of 38; none are severity 4 or above.

## Alternatives compared

`playback.general` is at rank 4 with complaint_count 3 [C13], severity_sum 9 [C14], mean_severity 3.000000 [C15], and priority_score 9 [C16]. Its severity is higher per complaint, but volume is lower. Topic aggregate: playback has 6 records, 3 severity-4-plus records, and a severity sum of 20.

`access.login_failure` is at rank 5 with complaint_count 2 [C17], severity_sum 8 [C18], mean_severity 4.000000 [C19], and priority_score 8 [C20]. It is the most severe per complaint, but the sample is small. Topic aggregate: access has 3 records and 2 severity-4-plus records.

`billing.premium_paywall` is at rank 6 with complaint_count 2 [C21], severity_sum 6 [C22], mean_severity 3.000000 [C23], and priority_score 6 [C24]. Its complaints overlap with the shuffle/queue Premium gating, so a usability fix may also reduce paywall friction. Topic aggregate: billing has 3 records and 1 cancellation-language record.

Billing-support is not supported as a priority by this sample beyond the overlap above.

## Limitations

Reviews are self-selected and historical. Cancellation language reflects stated intent, not confirmed churn. This analysis has no revenue or plan data. Model labels have measured disagreement. Unresolved or quarantined records are excluded from counts.
