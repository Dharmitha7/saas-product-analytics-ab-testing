"""Create the README charts from outputs/*.csv.  Usage: python python/make_charts.py"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import style

style.apply()
OUT = Path(__file__).resolve().parents[1] / "outputs"
rd = lambda n: pd.read_csv(OUT / f"{n}.csv")

# 1. Funnel ------------------------------------------------------------------------------------------------------
f = rd("funnel_overall")
fig, ax = plt.subplots(figsize=(8.5, 3.8))
y = np.arange(len(f))[::-1]
cols = [style.ACCENT_LIGHT, style.ACCENT_LIGHT, style.ACCENT_LIGHT, style.ACCENT, style.ACCENT_MID]
bars = ax.barh(y, f.pct_of_signups, color=cols, height=0.62)
for yi, r in zip(y, f.itertuples()):
    step = "" if pd.isna(r.pct_of_prior_step) else f"   ({r.pct_of_prior_step:.0f}% of previous step)"
    ax.text(r.pct_of_signups + 1.2, yi, f"{r.users:,}  |  {r.pct_of_signups:.1f}%{step}", va="center", fontsize=9, color=style.INK)
ax.set_yticks(y); ax.set_yticklabels(f.stage); ax.set_xlim(0, 150); ax.set_xticks([]); ax.grid(False)
ax.spines["bottom"].set_visible(False)
ax.set_title("Only half of the people who create a project invite a teammate in week one")
style.save(fig, "funnel.png"); plt.close(fig)

# 2. Cohort heatmaps ---------------------------------------------------------------------------------------------
m = rd("cohort_retention_monthly").pivot(index="signup_month", columns="month_idx", values="retention_pct")
fig, ax = plt.subplots(figsize=(8, 4.6))
ax.imshow(m.values, cmap=style.SEQ, vmin=0, vmax=70, aspect="auto")
for i in range(m.shape[0]):
    for j in range(m.shape[1]):
        v = m.values[i, j]
        if not np.isnan(v):
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=9, color="white" if v > 38 else style.INK)
ax.set_xticks(range(m.shape[1])); ax.set_xticklabels([f"Month {j}" for j in m.columns])
ax.set_yticks(range(m.shape[0])); ax.set_yticklabels([pd.Timestamp(d).strftime("%b %Y") for d in m.index])
ax.grid(False); ax.xaxis.tick_top(); ax.tick_params(length=0)
for sp in ax.spines.values(): sp.set_visible(False)
ax.set_title("Monthly cohorts: share of signups still active, by 30-day block", pad=28)
style.save(fig, "cohort_monthly.png"); plt.close(fig)

w = rd("cohort_retention_weekly").pivot(index="signup_week", columns="week_idx", values="retention_pct")
fig, ax = plt.subplots(figsize=(8, 6))
im = ax.imshow(w.values, cmap=style.SEQ, vmin=0, vmax=70, aspect="auto")
ax.set_xticks(range(w.shape[1])); ax.set_xticklabels([f"W{j}" for j in w.columns])
yt = list(range(0, w.shape[0], 4))
ax.set_yticks(yt); ax.set_yticklabels([pd.Timestamp(w.index[i]).strftime("%b %d") for i in yt])
ax.grid(False); ax.xaxis.tick_top(); ax.tick_params(length=0)
for sp in ax.spines.values(): sp.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02); cb.set_label("% of signups active"); cb.outline.set_visible(False)
ax.set_title("Weekly cohorts: retention is stable across the year", pad=28)
style.save(fig, "cohort_weekly.png"); plt.close(fig)

# 3. Retention by activation ---------------------------------------------------------------------------------------
r = rd("retention_curve_by_activation")
fig, ax = plt.subplots(figsize=(8, 3.8))
for seg, col in [("Activated", style.ACCENT), ("Not activated", style.GREY)]:
    d = r[r.segment == seg]
    ax.plot(d.week_idx, d.retention_pct, color=col, lw=2.4, marker="o", ms=4)
    ax.text(12.15, d.retention_pct.iloc[-1], f"{seg}\n{d.retention_pct.iloc[-1]:.0f}%", color=col, fontsize=9, fontweight="bold", va="center")
ax.set_xlim(0, 14.2); ax.set_xlabel("Weeks since signup"); ax.set_ylabel("% of group active")
ax.set_title("Activated users keep coming back; the rest fade out within weeks")
style.save(fig, "retention_activation.png"); plt.close(fig)

# 4. Friction: invite rate by segment ----------------------------------------------------------------------------
cs, dv = rd("funnel_by_company_size"), rd("funnel_by_device")
rows = [(f"Company size: {a}", b) for a, b in zip(cs.company_size, cs.invite_given_project_pct)] + \
       [(f"Device: {a}", b) for a, b in zip(dv.device, dv.invite_given_project_pct)]
fig, ax = plt.subplots(figsize=(8, 3.9))
yy = np.arange(len(rows))[::-1]
vals = [v for _, v in rows]
proj_users = cs.signups * cs.project_pct / 100
overall = (proj_users * cs.invite_given_project_pct).sum() / proj_users.sum()
colors = [style.ACCENT if v < 50 else style.ACCENT_LIGHT for v in vals]
bars = ax.barh(yy, vals, color=colors, height=0.62)
style.hbar_labels(ax, bars)
ax.axvline(overall, color=style.MUTED, lw=1, ls=(0, (4, 3))); ax.text(overall + 0.5, len(rows) - 0.35, f"all users {overall:.0f}%", fontsize=8, color=style.MUTED)
ax.set_yticks(yy); ax.set_yticklabels([a for a, _ in rows]); ax.set_xlim(0, 85); ax.grid(axis="y", visible=False)
ax.set_xlabel("% of project creators who invite a teammate (any time)")
ax.set_title("Solo accounts and mobile users are where the invite step breaks")
style.save(fig, "friction_invite.png"); plt.close(fig)

# 5. Channel value ------------------------------------------------------------------------------------------------
c = rd("segment_channel").sort_values("new_mrr_per_signup_usd")
fig, ax = plt.subplots(figsize=(8, 3.8))
yy = np.arange(len(c))
bars = ax.barh(yy, c.new_mrr_per_signup_usd, color=[style.ACCENT if ch == "paid_social" else style.ACCENT_LIGHT for ch in c.acquisition_channel], height=0.62)
for b, p in zip(bars, c.paid_pct):
    ax.text(b.get_width() + 0.15, b.get_y() + b.get_height() / 2, f"${b.get_width():.2f}   ({p:.1f}% paid)", va="center", fontsize=9)
ax.set_yticks(yy); ax.set_yticklabels(c.acquisition_channel.str.replace("_", " ")); ax.set_xlim(0, 17); ax.grid(axis="y", visible=False)
ax.set_xlabel("New MRR per signup, USD (signups Jan to Nov 2025)")
ax.set_title("Paid social is the weakest channel: half the revenue per signup of referral")
style.save(fig, "channel_value.png"); plt.close(fig)

# 6. Churn by plan -----------------------------------------------------------------------------------------------
ch = rd("churn_by_plan")
ch["label"] = ch.plan + ", " + ch.billing_period
ch = ch.sort_values("monthly_churn_pct")
fig, ax = plt.subplots(figsize=(8, 3.6))
yy = np.arange(len(ch))
bars = ax.barh(yy, ch.monthly_churn_pct, color=[style.ACCENT if (b == "monthly" and p == "Starter") else style.ACCENT_LIGHT for p, b in zip(ch.plan, ch.billing_period)], height=0.62)
style.hbar_labels(ax, bars, fmt="{:.2f}%", pad=0.08)
ax.set_yticks(yy); ax.set_yticklabels(ch.label); ax.set_xlim(0, 5.8); ax.grid(axis="y", visible=False)
ax.set_xlabel("Average monthly customer churn")
ax.set_title("Starter monthly plans lose about 1 in 21 customers every month")
style.save(fig, "churn_by_plan.png"); plt.close(fig)

# 7. MRR movement -------------------------------------------------------------------------------------------------
mw = rd("mrr_waterfall_monthly")
mw = mw[(mw.month >= "2025-02-01") & (mw.month <= "2025-12-01")]   # Jan 2026 excluded: no new signups after Dec 2025 in this dataset
fig, ax = plt.subplots(figsize=(8.5, 3.8))
x = np.arange(len(mw))
ax.bar(x, mw.new_mrr / 1000, color=style.ACCENT, width=0.66, label="New MRR")
ax.bar(x, -mw.churned_mrr / 1000, color=style.GREY, width=0.66, label="Churned MRR")
ax.axhline(0, color=style.INK, lw=0.8)
ax.set_xticks(x); ax.set_xticklabels([pd.Timestamp(m_).strftime("%b\n%y") for m_ in mw.month], fontsize=8)
ax.set_ylabel("Thousand USD per month"); ax.legend(loc="upper left", ncol=2)
ax.set_title("Churned MRR has grown from 1% to 13% of new MRR booked as the base scales")
style.save(fig, "mrr_movement.png"); plt.close(fig)

# 8. Feature adoption --------------------------------------------------------------------------------------------
a, b = rd("feature_adoption_and_retention"), rd("feature_retention_within_activated")
a["gap_all"] = a.retained_adopters_pct - a.retained_non_adopters_pct
b["gap_act"] = b.retained_adopters_pct - b.retained_non_adopters_pct
g = a[["feature", "adoption_pct", "gap_all"]].merge(b[["feature", "gap_act"]], on="feature").sort_values("gap_all")
fig, ax = plt.subplots(figsize=(8, 3.8))
yy = np.arange(len(g)); hgt = 0.34
b1 = ax.barh(yy + hgt / 2, g.gap_all, height=hgt, color=style.GREY, label="All users who created a project")
b2 = ax.barh(yy - hgt / 2, g.gap_act, height=hgt, color=style.ACCENT, label="Activated users only")
for bars in (b1, b2): style.hbar_labels(ax, bars, fmt="+{:.0f} pts", pad=0.4)
ax.set_yticks(yy); ax.set_yticklabels([f"{n} ({p:.0f}% adopt)" for n, p in zip(g.feature, g.adoption_pct)])
ax.set_xlim(0, 30); ax.grid(axis="y", visible=False); ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=2)
ax.set_xlabel("Retention gap in month 3: adopters minus non-adopters")
ax.set_title("Integrations and automations look sticky, but half the gap is just engaged users")
style.save(fig, "feature_adoption.png"); plt.close(fig)
print("charts written to", style.IMG)
