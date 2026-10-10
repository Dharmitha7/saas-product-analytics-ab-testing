# Decision memo: Guided onboarding checklist

| | |
|---|---|
| **To** | VP Product, Head of Growth |
| **From** | Product Analytics |
| **Experiment** | `exp_onboarding_checklist_v2`, 50/50 randomised at signup |
| **Test window** | Signups from 13 Oct to 23 Nov 2025 (6 weeks), 17,770 users in the analysis |
| **Data status** | Simulated for this case study. The method is what a real readout would use |

## Recommendation: ship, in stages

**Roll the guided checklist out to 50% of new signups for two weeks, then to 100%, and keep a 5% holdout on the old flow for 90 days.** Do not treat it as a one-shot switch. Activation clearly improves, but two things are not yet proven: the effect on revenue, and whether support tickets rise.

## Why

1. **More people activate.** 7-day activation rose from 32.6% to 35.6%, a lift of **+2.96 points** (95% interval +1.57 to +4.35, p < 0.001). Even the low end of the interval clears the +1.0 point we said was needed to justify the feature.
2. **The mechanism is visible.** The share of new users who invite a teammate within 48 hours rose from 12.4% to 16.4% (+32% relative). The checklist is working on the step where the funnel leaks most.
3. **Revenue points the right way, with less certainty.** Paid conversion within 30 days rose from 11.4% to 12.6% (+1.11 points, interval +0.16 to +2.07, p = 0.045 after correcting for three secondary metrics). At 13,400 signups a month, that is roughly **+400 activated users and +$13.6K new MRR per month**, with a wide range ($0.1K to $27.1K).

## Results

| Metric | Control | Treatment | Difference | 95% interval | Read |
|---|---|---|---|---|---|
| **7-day activation (primary)** | 32.64% | 35.60% | **+2.96 pts** | +1.57 to +4.35 | Clear win |
| Invited a teammate within 48h | 12.42% | 16.37% | +3.95 pts | +2.92 to +4.98 | Clear win |
| Paid within 30 days | 11.44% | 12.55% | +1.11 pts | +0.16 to +2.07 | Positive, borderline |
| Active in week 2 (guardrail) | 36.90% | 37.53% | +0.64 pts | -0.79 to +2.06 | No harm detected |
| Support tickets per user, 14 days (guardrail) | 0.0386 | 0.0379 | ratio 0.98 | 0.84 to 1.14 | **Inconclusive** |

Covariate-adjusted estimate for activation: +2.93 points (+1.55 to +4.30), almost identical to the raw result.

## Did the test earn our trust?

- **Randomisation held.** Split was 8,797 vs 8,973 (p = 0.19 for a fair 50/50), and channel, device, company size and week were balanced.
- **Clean population.** 72 users who saw both versions and 139 internal test accounts were removed before analysis.
- **Sample size was planned.** 5,668 users per arm gives 80% power to detect +2.5 points. That was reached on 9 Nov. We ran the full 6 weeks without stopping early, so there was no peeking.
- **The estimate is stable.** The cumulative lift settled at about +3 points from early November onward.

## Is the lift big enough to matter?

Yes. We set +1.0 point as the bar. It is worth about **$3.0K of new MRR per month** (extra activated users x 27-point higher chance of paying x $83 average MRR), which we assumed covers the cost of building and maintaining the checklist. The observed lift is about three times that bar, and the lower end of the interval is still above it. **Product should confirm that the bar matches the real cost.**

## What we do not know

| Gap | Why it matters | How we close it |
|---|---|---|
| **Ticket guardrail is inconclusive** | Tickets are rare (about 0.04 per user), so the test can rule out a large rise but not a 10% rise. The point estimate is fine (0.98). This was a sizing miss on our side. | Monitor weekly during the staged rollout. Pause if the treated group runs more than 15% above the holdout. |
| **Revenue effect is borderline** | The test had about even odds (53%) of detecting a true +1 point paid lift. Passing the correction at p = 0.045 is encouraging, not conclusive. | The 90-day holdout gives more data. |
| **No long-run retention or churn** | Test users have 30 days of paid follow-up and 2 weeks of usage. Activation has historically gone with better retention (46% vs 7% active at week 12), but that is an association. | 5% holdout, read at day 90. |
| **Who benefits is unclear** | Segment lifts range from -1.4 to +5.3 points, but every interval is wide and no interaction test is significant (all adjusted p > 0.5). | Treat as questions for the next test. Do not target the rollout by segment. |
| **Weekly results are noisy** | Weekly lift ranged from -0.1 to +5.2 points. There is no evidence the effect fades (trend p = 0.66), but the test cannot rule out a modest fade. | Track weekly lift against the holdout. |
| **Simulated data** | Real traffic adds bots, multi-device users and tracking gaps. | Repeat the same checks on production data. |

## Rollout plan

| Stage | Exposure | Duration | Go to next stage if |
|---|---|---|---|
| 1 | 50% | 14 days | Activation lift stays at or above +1.0 pt, tickets within 15% of control |
| 2 | 95% (5% holdout) | 90 days | Week-8 retention not below holdout, tickets within limit |
| 3 | Review at day 90 | | Paid conversion and retention read confirms the revenue case. Then retire the holdout |

## Next experiments

1. **Solo accounts** have only a 41% invite rate and 24% activation, because the activation definition needs a teammate. Test an alternative path (for example, complete three tasks) and revisit how we define activation for them.
2. **Mobile signups** invite at 48% against 57% on desktop. The checklist did little for them (+0.9 points, interval -2.2 to +3.9). Test a mobile-specific invite flow.
3. **Resize the ticket guardrail** so the next test can detect a 10% change.

*Analysis: [`notebooks/ab_test_analysis.ipynb`](../notebooks/ab_test_analysis.ipynb). Queries: [`sql/07_experiment.sql`](../sql/07_experiment.sql). Full results: `outputs/exp_results.json`.*
