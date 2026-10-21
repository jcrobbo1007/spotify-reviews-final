## Recommendation

Next quarter's product effort should go to **playback**. Playback has the strongest combined signal of severity and crash-like reports in the declared subset. This is a 173,000-review declared subset, not a full-corpus model run; all counts below are sample counts from that subset.

## Evidence

Issue-level ranking (declared subset):

- `playback.general` is at rank 6 with complaint_count 3071 [C1], severity_sum 9385 [C2], and mean_severity 3.056008 [C3].
- `playback.crash_freeze` is at rank 8 with complaint_count 2068 [C4], severity_sum 7182 [C5], and mean_severity 3.472921 [C6].
- `playback.stops_pauses` is at rank 9 with complaint_count 1678 [C7], severity_sum 5289 [C8], and mean_severity 3.151967 [C9].

Topic aggregate (not claims): playback has 12,335 records, 2,955 with severity 4 or higher, and 30,610 total severity, the second-highest severity sum among topics after other and billing.

Representative reviews from the evidence pack:

- `playback.general`: "Won't work anymore. Can't play anything" (dc0c2fb5-9d6a-4b66-89fb-090e2ee8ca59).
- `playback.general`: "my phone is getting restarted while opening Spotify" (09aae8ef-6c97-426d-8c2b-16d1d358b6bf).

## Alternatives compared

- **Billing-support:** `billing.subscription_entitlement` is at rank 3 with complaint_count 6029 [C10] and severity_sum 16533 [C11]; `billing.premium_paywall` is at rank 4 with complaint_count 5303 [C12] and severity_sum 15505 [C13]. Billing has the largest complaint volume among topic-specific issues and the highest cancellation count (2928, topic aggregate), but its mean severity is higher than playback's only for `billing.premium_paywall` (2.923817 [C14]) and lower for `billing.subscription_entitlement` (2.742246 [C15]), and playback's crash-related severity is higher per complaint.
- **Usability:** `usability.ads` is at rank 2 with complaint_count 9817 [C16] and severity_sum 21052 [C17], and `usability.shuffle_queue` is at rank 5 with complaint_count 4317 [C18] and severity_sum 11342 [C19]. Usability has the largest record volume but low severity_4_plus count (191, topic aggregate).
- **Access:** `access.login_failure` is at rank 7 with complaint_count 2160 [C20], severity_sum 8499 [C21], and mean_severity 3.934722 [C22], the highest mean severity in the top rows, but it is a smaller volume issue.

Playback is recommended because it pairs high severity (2,955 severity-4+ records, topic aggregate) with several distinct crash and stop issues that a single engineering effort can address.

## Limitations

- Reviews are self-selected and historical.
- Cancellation language reflects stated intent, not confirmed churn.
- The data contains no revenue or plan data.
- Model labels have measured disagreement.
- Unresolved and quarantined records are excluded from counts.
