"""Generate the simulated Tasklane dataset (SaaS project-management product).

ALL DATA IS SIMULATED. Nothing here is real customer data. The generator is seeded, so the dataset is reproducible.

Tables written to data/*.parquet:
    users, events, subscriptions, experiment_assignments, support_tickets

What is deliberately built in (so the analysis has something real to find, and some mess to clean):
  * Funnel: signup -> email verified -> first project -> teammate invited -> paid subscription.
  * Channel quality differs; a March paid-social burst brings in a weaker cohort.
  * Weekly usage decays; integrations and automations are associated with better retention.
  * Plan-level churn (monthly and annual billing).
  * A randomised onboarding experiment (exp_onboarding_checklist_v2), 50/50, 6 weeks of signups.
      - lifts the "invite a teammate" step, with no effect for solo accounts
      - effect fades over the test window (novelty)
      - paid conversion is helped only through activation, so that lift is small
  * Data quality problems: duplicate events, events stamped before signup, null channel/country,
    internal test accounts, and users with conflicting experiment assignments.
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20251013
rng = np.random.default_rng(SEED)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

SIGNUP_START, SIGNUP_END = pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")
CUTOFF = pd.Timestamp("2026-02-28 23:59:59")
EXP_START, EXP_END = pd.Timestamp("2025-10-13"), pd.Timestamp("2025-11-23")  # 6 full weeks, Mon to Sun
EXP_ID = "exp_onboarding_checklist_v2"
DAY = 86400.0


def sig(x):
    return 1.0 / (1.0 + np.exp(-x))


# ------------------------------------------------------------------ users
days = pd.date_range(SIGNUP_START, SIGNUP_END)
t = np.arange(len(days)) / (len(days) - 1)
dow = np.array([1.0, 1.05, 1.05, 1.0, 0.95, 0.55, 0.50])[days.dayofweek]
season = np.where(days.month == 8, 0.88, 1.0) * np.where(days.month.isin([11, 12]), 1.05, 1.0)
lam = (270 + 250 * t) * dow * season
n_day = rng.poisson(lam)
N = int(n_day.sum())
signup_date = np.repeat(days.values, n_day)
hour_w = np.array([1, 1, 1, 1, 1, 2, 3, 5, 8, 10, 10, 9, 8, 9, 10, 9, 8, 6, 4, 3, 2, 2, 1, 1], float)
hour = rng.choice(24, size=N, p=hour_w / hour_w.sum())
signup_ts = signup_date + (hour * 3600 + rng.uniform(0, 3600, N)).astype("timedelta64[s]")
signup_sec = (signup_ts - np.datetime64("2025-01-01T00:00:00")).astype("timedelta64[s]").astype(float)

CHANNELS = ["organic_search", "paid_search", "paid_social", "referral", "email_content", "direct"]
QC = dict(organic_search=0.10, paid_search=-0.20, paid_social=-0.60, referral=0.60, email_content=0.0, direct=0.20)
base_p = np.array([0.28, 0.20, 0.15, 0.10, 0.12, 0.15])
spike_p = np.array([0.20, 0.15, 0.40, 0.08, 0.09, 0.08])  # March paid-social burst
is_spike = (signup_date >= np.datetime64("2025-03-10")) & (signup_date <= np.datetime64("2025-03-30"))
ch_idx = np.where(is_spike, rng.choice(6, N, p=spike_p), rng.choice(6, N, p=base_p))
channel = np.array(CHANNELS)[ch_idx]
qc = np.array([QC[c] for c in CHANNELS])[ch_idx]

device = rng.choice(["desktop", "mobile", "tablet"], N, p=[0.72, 0.20, 0.08])
size_band = rng.choice(["solo", "2-10", "11-50", "51+"], N, p=[0.35, 0.40, 0.18, 0.07])
country = rng.choice(["US", "GB", "DE", "CA", "IN", "AU", "OTHER"], N, p=[0.55, 0.10, 0.08, 0.07, 0.06, 0.04, 0.10])
internal = rng.random(N) < 0.008
email_domain = np.where(internal, "tasklane.com",
                        rng.choice(["gmail.com", "outlook.com", "yahoo.com", "company-domain"], N, p=[0.2, 0.07, 0.03, 0.70]))
e = rng.normal(0, 1, N)  # latent engagement propensity (not observed by analysts)

solo = (size_band == "solo").astype(float)
mid = (size_band == "2-10").astype(float)
big = np.isin(size_band, ["11-50", "51+"]).astype(float)
mobile = (device == "mobile").astype(float)

# experiment assignment
in_exp = (signup_date >= EXP_START.to_datetime64()) & (signup_date <= EXP_END.to_datetime64())
variant = np.where(rng.random(N) < 0.5, "treatment", "control")
trt = (in_exp & (variant == "treatment")).astype(float)
wk_idx = np.clip(((signup_date - EXP_START.to_datetime64()).astype("timedelta64[D]").astype(int)) // 7, 0, 5)
mult = 1.30 - 0.07 * wk_idx  # novelty: the effect fades by about 25% across the six weeks

# ------------------------------------------------------------------ funnel steps
p_ver = sig(1.7 + 0.25 * qc + 0.1 * e)
verified = (rng.random(N) < p_ver) | internal
ver_lag = np.maximum(60, rng.exponential(20 * 60, N))

p_proj = sig(1.25 + 0.55 * e + 0.45 * qc + trt * 0.04 * mult)
has_proj = verified & (rng.random(N) < p_proj)
proj_lag = np.maximum(120, rng.exponential(1.2 * DAY, N)) * np.where(trt == 1, 0.85, 1.0)

eff = (0.075 + 0.055 * mid) * (1 - solo) * mult
p_inv = sig(0.45 + 0.65 * e + 0.40 * qc - 0.45 * mobile - 0.85 * solo + 0.35 * big + trt * eff)
has_inv = has_proj & (rng.random(N) < p_inv)
inv_lag = proj_lag + np.maximum(300, rng.exponential(2.2 * DAY, N)) * np.where(trt == 1, 0.8, 1.0)
activated = has_inv & (proj_lag <= 7 * DAY) & (inv_lag <= 7 * DAY)

# ------------------------------------------------------------------ subscriptions
p_buy = sig(-3.55 + 2.2 * activated + 0.35 * e + 0.45 * qc + 0.35 * mid + 0.5 * big)
buys = verified & ~internal & (rng.random(N) < p_buy)
trial_end = rng.random(N) < 0.45
buy_lag_days = np.where(trial_end, 14 + rng.exponential(0.8, N), 2 + rng.gamma(2.0, 3.0, N))
buy_lag_days = np.maximum(buy_lag_days, np.where(has_inv, inv_lag / DAY + 0.1, 1.0))
buy_lag_days = np.maximum(buy_lag_days, 1.0)

plan_probs = {"solo": [0.75, 0.22, 0.03], "2-10": [0.35, 0.55, 0.10], "11-50": [0.10, 0.55, 0.35], "51+": [0.02, 0.28, 0.70]}
PLANS = np.array(["Starter", "Team", "Business"])
plan_idx = np.zeros(N, int)
for sb, pr in plan_probs.items():
    m = size_band == sb
    plan_idx[m] = rng.choice(3, m.sum(), p=pr)
plan = PLANS[plan_idx]
annual = rng.random(N) < np.array([0.15, 0.22, 0.35])[plan_idx]
list_mrr = np.array([29.0, 79.0, 199.0])[plan_idx]
mrr = np.round(np.where(annual, list_mrr * 0.85, list_mrr), 2)

hz = np.array([0.070, 0.040, 0.022])[plan_idx] * np.exp(-0.30 * e) * np.where(activated, 0.6, 1.25)
churn_month = np.full(N, 0)  # 0 = never churns within horizon
alive = buys.copy()
for m in range(1, 16):
    h = np.where(m == 1, hz * 1.6, hz)
    h = np.where(annual, 0.0, h)
    if m == 12:
        h = np.where(annual, np.clip(0.20 * np.exp(-0.30 * e) * np.where(activated, 0.6, 1.25), 0, 0.9), h)
    drop = alive & (rng.random(N) < h)
    churn_month[drop] = m
    alive &= ~drop
sub_start_sec = signup_sec + buy_lag_days * DAY
sub_start = np.datetime64("2025-01-01T00:00:00") + sub_start_sec.astype("timedelta64[s]") if False else None
sub_start_ts = pd.to_datetime(sub_start_sec, unit="s", origin="2025-01-01")
sub_end_ts = sub_start_ts + pd.to_timedelta(churn_month * 30.4375, unit="D")
churned = buys & (churn_month > 0) & (sub_end_ts <= CUTOFF)
started = buys & (sub_start_ts <= CUTOFF)
churned &= started
churn_sec = np.where(churned, (sub_end_ts - pd.Timestamp("2025-01-01")).total_seconds(), np.inf)

# ------------------------------------------------------------------ events
ev_u, ev_t, ev_n, ev_f = [], [], [], []


def add(u, sec, name, feat=None):
    ev_u.append(u)
    ev_t.append(sec)
    ev_n.append(np.full(len(u), name, dtype=object))
    ev_f.append(np.full(len(u), feat, dtype=object) if feat else np.full(len(u), None, dtype=object))


uid = np.arange(N)
add(uid, signup_sec, "signup")
m = verified
add(uid[m], signup_sec[m] + ver_lag[m], "email_verified")
m = has_proj
add(uid[m], signup_sec[m] + proj_lag[m], "project_created")
m = has_inv
add(uid[m], signup_sec[m] + inv_lag[m], "teammate_invited")
m = started
add(uid[m], sub_start_sec[m], "subscription_started")

# weekly activity (weeks counted from signup)
K = int(np.ceil((CUTOFF - SIGNUP_START).days / 7)) + 1
k0 = np.floor(proj_lag / (7 * DAY)).astype(int)
a1 = sig(-0.45 + 0.8 * e + 1.1 * activated + 0.3 * qc + 0.35 * started + 0.5 * internal)

FEATS = {"integration_connected": -1.6, "automation_created": -2.3, "timeline_viewed": -1.2,
         "report_viewed": -1.4, "mobile_app_opened": -1.0}
has_feat = {f: has_proj & (rng.random(N) < sig(b + 0.5 * e + 0.7 * activated)) for f, b in FEATS.items()}
r = 0.90 + 0.03 * e + 0.03 * activated + 0.03 * has_feat["integration_connected"] + 0.03 * has_feat["automation_created"]
r = np.clip(r, 0.6, 0.985)

kk = np.arange(K)[None, :]
p_act = np.clip(a1[:, None] * r[:, None] ** np.maximum(kk - 1, 0), 0, 0.97)
active = rng.random((N, K)) < p_act
active[:, 0] = True
week_start = signup_sec[:, None] + kk * 7 * DAY
active &= (kk >= k0[:, None]) & has_proj[:, None]
active &= week_start < (CUTOFF - pd.Timestamp("2025-01-01")).total_seconds()
active &= week_start < churn_sec[:, None]
ui, wi = np.nonzero(active)
lam_ev = np.exp(0.75 + 0.35 * e[ui] + 0.3 * activated[ui] + 0.6 * internal[ui])
n_ev = 1 + rng.poisson(lam_ev)
ui_rep = np.repeat(ui, n_ev)
wi_rep = np.repeat(wi, n_ev)
t0 = signup_sec[ui_rep] + wi_rep * 7 * DAY
if True:
    t0 = np.where(wi_rep == k0[ui_rep], np.maximum(t0, signup_sec[ui_rep] + proj_lag[ui_rep]), t0)
span = np.where(wi_rep == k0[ui_rep], np.maximum(7 * DAY - (t0 - (signup_sec[ui_rep] + wi_rep * 7 * DAY)), 3600), 7 * DAY)
sec = t0 + rng.uniform(0, 1, len(ui_rep)) * span
is_task = rng.random(len(ui_rep)) < 0.65
add(ui_rep[is_task], sec[is_task], "task_created")
add(ui_rep[~is_task], sec[~is_task], "comment_added")

# feature events inside active weeks
for f in FEATS:
    mask = has_feat[f][ui] & (rng.random(len(ui)) < 0.35)
    uu, ww = ui[mask], wi[mask]
    s = signup_sec[uu] + ww * 7 * DAY + rng.uniform(0, 7 * DAY, len(uu))
    add(uu, s, f, f.split("_")[0])

users_idx = np.concatenate(ev_u)
sec_all = np.concatenate(ev_t)
names = np.concatenate(ev_n)
feats = np.concatenate(ev_f)
ev = pd.DataFrame({"user_idx": users_idx, "sec": sec_all, "event_name": names, "feature": feats})
ev = ev[ev.sec <= (CUTOFF - pd.Timestamp("2025-01-01")).total_seconds()]
ev["event_ts"] = pd.to_datetime(ev.sec.round(0), unit="s", origin="2025-01-01")
ev = ev.drop(columns="sec")

# data quality defects: duplicates and events stamped before signup (clock skew)
dup = ev.sample(frac=0.006, random_state=SEED)
ev = pd.concat([ev, dup], ignore_index=True)
skew = ev.sample(frac=0.003, random_state=SEED + 1).index
ev.loc[skew, "event_ts"] = ev.loc[skew, "event_ts"] - pd.to_timedelta(rng.integers(60, 1800, len(skew)), unit="s")
ev = ev.sort_values(["event_ts", "user_idx"]).reset_index(drop=True)
ev["event_id"] = np.arange(1, len(ev) + 1)
ev["user_id"] = ev.user_idx.map(lambda i: f"u_{i + 1:06d}")

# ------------------------------------------------------------------ tables
ch_out = pd.Series(channel).where(rng.random(N) > 0.025, None)
country_out = pd.Series(country).where(rng.random(N) > 0.01, None)
users = pd.DataFrame({
    "user_id": [f"u_{i + 1:06d}" for i in range(N)], "signup_ts": signup_ts,
    "acquisition_channel": ch_out, "country": country_out, "device": device, "company_size": size_band,
    "email_domain": email_domain})

# ordered by user_idx for positional access below
users_ev = ev[["event_id", "user_id", "event_ts", "event_name", "feature"]]

sub_mask = started
subs = pd.DataFrame({
    "user_id": users.user_id[sub_mask].values, "plan": plan[sub_mask], "billing_period": np.where(annual[sub_mask], "annual", "monthly"),
    "mrr_usd": mrr[sub_mask], "start_ts": sub_start_ts[sub_mask],
    "end_ts": pd.Series(sub_end_ts[sub_mask]).where(churned[sub_mask], pd.NaT).values})
subs["status"] = np.where(subs.end_ts.isna(), "active", "churned")
subs.insert(0, "subscription_id", [f"s_{i + 1:06d}" for i in range(len(subs))])

asg = pd.DataFrame({"user_id": users.user_id[in_exp].values, "experiment_id": EXP_ID, "variant": variant[in_exp],
                    "assigned_ts": signup_ts[in_exp] + np.timedelta64(2, "s")})
# conflicting re-assignments (cookie loss): ~0.4% of users appear in both arms
conf = asg.sample(frac=0.004, random_state=SEED + 2).copy()
conf["variant"] = np.where(conf.variant == "control", "treatment", "control")
conf["assigned_ts"] = conf.assigned_ts + pd.Timedelta(hours=6)
asg = pd.concat([asg, conf], ignore_index=True).sort_values(["assigned_ts"]).reset_index(drop=True)

# support tickets in the first 30 days: struggling users (project but not activated) ask more; flat across arms
rate = 0.05 + 0.10 * (has_proj & ~activated) + 0.02 * (size_band == "11-50")
n_t = rng.poisson(rate)
t_u = np.repeat(uid, n_t)
t_ts = signup_sec[t_u] + rng.uniform(0.2, 30, len(t_u)) * DAY
tix = pd.DataFrame({"user_id": users.user_id.values[t_u],
                    "created_ts": pd.to_datetime(t_ts.round(0), unit="s", origin="2025-01-01"),
                    "category": rng.choice(["how_to", "bug", "billing", "access"], len(t_u), p=[0.5, 0.25, 0.15, 0.10])})
tix = tix[tix.created_ts <= CUTOFF].sort_values("created_ts").reset_index(drop=True)
tix.insert(0, "ticket_id", [f"t_{i + 1:06d}" for i in range(len(tix))])

users.to_parquet(OUT / "users.parquet", index=False)
users_ev.to_parquet(OUT / "events.parquet", index=False)
subs.to_parquet(OUT / "subscriptions.parquet", index=False)
asg.to_parquet(OUT / "experiment_assignments.parquet", index=False)
tix.to_parquet(OUT / "support_tickets.parquet", index=False)

print(f"users {len(users):,}  events {len(users_ev):,}  subs {len(subs):,}  assignments {len(asg):,}  tickets {len(tix):,}")
x = in_exp & ~internal
for v in ["control", "treatment"]:
    mm = x & (variant == v)
    print(f"{v:9s} n={mm.sum():,}  activation={activated[mm].mean():.3%}  paid={started[mm].mean():.3%}")
print(f"overall activation {activated[~internal].mean():.3%}, paid {started[~internal].mean():.3%}")
