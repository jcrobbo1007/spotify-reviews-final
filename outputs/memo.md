## Recommendation
Recommend billing-support for next quarter. billing-support is 1st of 4 families on cancellation-language records (2950) [F5]. The highest-ranked billing-support issue is `billing.subscription_entitlement` at rank 3 [F25], with complaint_count 6029 [C1] and priority_score 16533 [C4]. All counts are sample counts from the declared subset.

## Evidence
Scope: Declared 173,000-review subset — not a full-corpus model run; counts are subset counts.

- `billing.subscription_entitlement` (rank 3): complaint_count 6029 [C1], severity_sum 16533 [C2], mean_severity 2.742246 [C3], priority_score 16533 [C4]. Quote: “Amount debited twice but still Premium account not renewed” (5157428f-8f40-4ce7-8e24-2d2c438b212c).
- `billing.premium_paywall` (rank 4): complaint_count 5303 [C5], priority_score 15505 [C6]. Quote: “To get charged for making a playlist is just ridiculous!” (f4b75fa1-e7aa-4264-947b-67d08b357b70).

## Alternatives compared
- Usability: usability is 1st of 4 families on complaint-or-cancellation records (18850) [F1]. usability is 1st of 4 families on severity sum (43797) [F9]. usability is 4th of 4 families on severity-4-plus records (191) [F16]. The highest-ranked usability issue is `usability.ads` at rank 2 [F23], with complaint_count 9817 [C7] and priority_score 21052 [C8]. On cancellation language, usability is 2nd of 4 families on cancellation-language records (1351) [F6].
- Playback: playback is 1st of 4 families on severity-4-plus records (2955) [F13]. The highest-ranked playback issue is `playback.general` at rank 6 [F24], with complaint_count 3071 [C9]. playback is 3rd of 4 families on cancellation-language records (608) [F7].
- Access: access is 4th of 4 families on complaint-or-cancellation records (3004) [F4]. access is 2nd of 4 families on severity-4-plus records (2605) [F14]. `access.login_failure` has the highest mean severity among the top 12 ranked issues (3.934722) [F21]; it sits at rank 7 with mean_severity 3.934722 [C10].

The rank 1 item, `other.general_dislike`, sits outside the four families and is not used for the recommendation.

## Limitations
The reviews are self-selected and historical. Cancellation language is intent, not confirmed churn. No revenue or plan data is available, so financial impact is not measured. Model labels have measured disagreement. Unresolved or quarantined records are excluded from counts.
