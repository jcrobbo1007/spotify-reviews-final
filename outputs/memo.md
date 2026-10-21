## Recommendation
Put next quarter's product effort into billing-support, starting with `billing.subscription_entitlement` and `billing.premium_paywall`. Scope: Declared 173,000-review subset — not a full-corpus model run; counts are subset counts (sample counts, not population totals). `other.general_dislike` is at rank 1 but has no topic, so it sits outside the listed areas and is not scored here.

## Evidence
The highest-ranked billing-support issue is `billing.subscription_entitlement` at rank 3, with complaint_count 6034 [C1], severity_sum 16547 [C2], mean_severity 2.742294 [C3], and priority_score 16547 [C4]. One reviewer wrote "Amount debited twice but still Premium account not renewed" (5157428f-8f40-4ce7-8e24-2d2c438b212c).

`billing.premium_paywall` sits at rank 4 with complaint_count 5307 [C5] and priority_score 15516 [C6]. One reviewer wrote "To get charged for making a playlist is just ridiculous!" (f4b75fa1-e7aa-4264-947b-67d08b357b70).

Topic aggregates (not claims):
- billing-support is 2nd of 4 families on complaint-or-cancellation records (14692) [F2]
- billing-support is 1st of 4 families on cancellation-language records (2954) [F5]
- billing-support is 2nd of 4 families on severity sum (40838) [F10]

Cancellation language is the intent signal that sets billing-support apart in this sample, and the two billing issues above sit at ranks 3 and 4.

## Alternatives compared
Usability: usability is 1st of 4 families on complaint-or-cancellation records (18859) [F1]. This is driven by `usability.ads` at rank 2 with complaint_count 9821 [C9] and priority_score 21060 [C10]. usability is 4th of 4 families on severity-4-plus records (192) [F16], so its complaint volume is a weak proxy for severity.

Playback: playback is 1st of 4 families on severity-4-plus records (2955) [F13]. Its issues sit at rank 6 (`playback.general`), rank 8 (`playback.crash_freeze`, complaint_count 2068 [C7]), and rank 9 (`playback.stops_pauses`). This is the case for the alternative: a playback quarter would be justified if severity were weighted above intent.

Access: access is 4th of 4 families on complaint-or-cancellation records (3007) [F4]. Its main issue, `access.login_failure`, is at rank 7 with complaint_count 2161 [C8], and access is 2nd of 4 families on severity-4-plus records (2608) [F14].

## Limitations
The reviews are self-selected and historical. Cancellation language is intent, not confirmed churn. There is no revenue or plan data, so billing impact is unmeasured. Model labels have measured disagreement. Unresolved and quarantined records are excluded from counts.
