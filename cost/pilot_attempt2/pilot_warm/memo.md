## Recommendation

Prioritize **usability** next quarter, with the focus on the premium-gated shuffle/queue controls and the ad experience. Usability leads the pilot ranking on the aggregates that matter most: the top-ranked issue `usability.shuffle_queue` [C2] carries the highest mean severity among the high-volume issues, and `usability.ads` [C3] is the most-complained-about specific issue.

## Evidence

Scope: this is a declared 100-review cost pilot (cost_100.csv), a subset of the full corpus, not the full review population. All counts below are pilot sample counts.

Issue ranking (baseline, code-computed):
- `other.general_dislike` has the highest priority score [C1], but it is unspecific sentiment and is not actionable on its own.
- `usability.shuffle_queue` shows 7 complaints [C4], severity sum 18 [C5], mean severity 2.571429 [C6]. Reviewers describe being unable to skip or pick songs without Premium, e.g. "You can't even listen to music you want it just shuffles it".
- `usability.ads` shows 8 complaints [C7], severity sum 16 [C8], mean severity 2.000000 [C9]. Reviewers describe frequent interruptions, e.g. "it's always every 1 or 2 song then instant ads".
- Playback issues are less frequent: `playback.general` [C10] and `playback.crash_freeze` [C11] appear with lower complaint volume.
- Billing-linked paywall complaints appear in `billing.premium_paywall` [C12], often tied to the same shuffle/skip restrictions.

Topic aggregate (not claims): usability has 17 records with complaint or cancellation language, the largest severity sum among named topics (38), and 3 cancellation-language records. Playback has 20 severity points with 3 records at severity 4+.

Representative evidence (cited): 88439ec2-7c49-4c57-bedb-c5e098692aff, a78d831a-69f4-428a-9235-cfdd9775c509, ab67a772-c3b7-42ba-9b80-8d21d3857018, 3e8bdc92-4934-457e-85cc-8b9d14bf51c0.

## Alternatives compared

- **Playback**: smaller volume but higher severity on crash and lag issues (playback topic severity sum 20, 3 records at severity 4+). A strong second priority, especially for stability fixes.
- **Access**: `access.login_failure` [C13] has the highest mean severity in the top ranks (4.000000 [C14]) but only 2 complaints, so it is a targeted fix rather than a broad area.
- **Billing-support**: only 3 billing records; the paywall complaints overlap heavily with usability, so the fix is largely a feature-gating decision inside usability.

## Limitations

Reviews are self-selected and historical. Cancellation language reflects stated intent, not confirmed churn. No revenue or plan data is available, so Premium impact cannot be sized. Model labels show measured disagreement. Unresolved and quarantined records are excluded from counts, and usability has 4 records needing review.
