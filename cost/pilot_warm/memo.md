## Recommendation

Next quarter's product effort should go to **billing-support**, specifically the premium gating that restricts core playback controls. This is a recommendation for the 100-review cost pilot (cost_100.csv) only; counts are pilot counts, and this pilot is a declared subset, not the full corpus.

## Evidence

The baseline ranking places `billing.premium_paywall` at rank 3 with complaint_count 5 [C1], severity_sum 15 [C2], mean_severity 3.000000 [C3], and priority_score 15 [C4]. It has the highest mean severity among the top three issues.

The usability issues rank higher on volume: `other.general_dislike` is rank 1 (complaint_count 16 [C5], severity_sum 33 [C6]), and `usability.ads` is rank 2 (complaint_count 8 [C7], severity_sum 18 [C8]). Several usability complaints, such as `usability.shuffle_queue` at rank 4 (complaint_count 3 [C9], severity_sum 9 [C10]), are also tied to premium restrictions in quotes, which supports treating the paywall as a driver of the usability pain.

Topic aggregate: billing records total 6, all complaint_or_cancellation, with severity_sum 18 and no severity-4-plus records. Topic aggregate: playback records total 5 with severity_sum 17 and 2 severity-4-plus records.

Representative quotes: "now you can't even pick a certain song without Spotify premium" (review d146397f-4a94-4980-be00-ae9212eca3a7); "its not fair ..to restrict all the features jst so people would purchase premium" (review 88439ec2-7c49-4c57-bedb-c5e098692aff).

## Alternatives compared

- **usability**: the largest volume (topic aggregate: 16 records, severity_sum 39). Much of this overlaps with the paywall theme, and `usability.ads` [C7] is a separate ads concern. Ranked by issue, its strongest item is `usability.ads` at rank 2.
- **playback**: `playback.crash_freeze` and `playback.lag_loading` each appear at rank 11 and rank 12 with complaint_count 1 [C11]. Topic aggregate: 5 records, severity_sum 17, 2 severity-4-plus records. Severe but low volume.
- **access**: `access.login_failure` and `access.general` appear at ranks 7 and 8 with complaint_count 1 each. Topic aggregate: 2 records, severity_sum 8. Too small in this pilot to prioritize.

## Limitations

- Reviews are self-selected and historical.
- Cancellation language is intent, not confirmed churn.
- No revenue or plan data is available.
- Model labels have measured disagreement.
- Unresolved and quarantined records are excluded from counts.
- Counts are sample counts from a 100-review pilot.
