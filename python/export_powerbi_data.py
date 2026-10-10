"""Export the star-schema CSVs that the Power BI project loads.  Usage: python python/export_powerbi_data.py"""
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "powerbi" / "data"
OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(ROOT / "data" / "tasklane.duckdb"), read_only=True)

# One row per (non-internal) user. Retention flags are NULL when the week is not yet fully observed at the data cutoff.
fact_user = con.execute("""
WITH wk AS (
    SELECT user_id, max((week_idx = 1)::INT) AS a1, max((week_idx = 4)::INT) AS a4, max((week_idx = 8)::INT) AS a8
    FROM user_week_activity GROUP BY user_id
)
SELECT
    d.user_id, d.signup_date, d.signup_month,
    d.acquisition_channel AS channel, d.device, d.company_size, d.engagement_tier,
    d.is_verified::INT AS is_verified, d.has_project::INT AS has_project, d.is_activated::INT AS is_activated,
    CASE WHEN d.is_activated THEN 'Activated' ELSE 'Not activated' END AS activation_status,
    d.is_paid::INT AS is_paid,
    COALESCE(d.plan, 'No plan') AS plan, COALESCE(d.billing_period, 'none') AS billing_period,
    d.mrr_usd,
    CAST(d.sub_start_ts AS DATE) AS sub_start_date, CAST(d.sub_end_ts AS DATE) AS sub_end_date,
    (d.sub_end_ts IS NOT NULL)::INT AS is_churned,
    CASE WHEN d.is_paid THEN
        (SELECT count(*) FROM (SELECT unnest(generate_series(DATE '2025-01-01', DATE '2026-02-01', INTERVAL 1 MONTH)) AS m)
         WHERE d.sub_start_ts < m AND (d.sub_end_ts IS NULL OR d.sub_end_ts >= m))
    ELSE 0 END AS customer_months,
    CASE WHEN d.signup_ts + INTERVAL 14 DAY <= TIMESTAMP '2026-02-28' THEN COALESCE(wk.a1, 0) END AS w1_active,
    CASE WHEN d.signup_ts + INTERVAL 35 DAY <= TIMESTAMP '2026-02-28' THEN COALESCE(wk.a4, 0) END AS w4_active,
    CASE WHEN d.signup_ts + INTERVAL 63 DAY <= TIMESTAMP '2026-02-28' THEN COALESCE(wk.a8, 0) END AS w8_active,
    COALESCE(x.variant, 'not in test') AS experiment_variant,
    (x.user_id IS NOT NULL)::INT AS in_experiment,
    COALESCE(x.is_paid_30d, FALSE)::INT AS is_paid_30d,
    COALESCE(x.test_week + 1, 0) AS test_week
FROM dim_user d
LEFT JOIN wk USING (user_id)
LEFT JOIN exp_users x USING (user_id)
""").df()
fact_user.to_csv(OUT / "fact_user.csv", index=False)

dates = pd.date_range("2025-01-01", "2026-02-28")
dim_date = pd.DataFrame({"date": dates, "week_start": (dates - pd.to_timedelta(dates.dayofweek, unit="D")),
                         "month_start": dates.to_period("M").to_timestamp(),
                         "month_label": dates.strftime("%Y-%m"), "year": dates.year})
for c in ["date", "week_start", "month_start"]:
    dim_date[c] = dim_date[c].dt.strftime("%Y-%m-%d")
dim_date.to_csv(OUT / "dim_date.csv", index=False)

pd.read_csv(ROOT / "outputs" / "cohort_retention_weekly.csv").to_csv(OUT / "cohort_retention_weekly.csv", index=False)
pd.read_csv(ROOT / "outputs" / "mrr_waterfall_monthly.csv").to_csv(OUT / "mrr_monthly.csv", index=False)
pd.DataFrame({"stage": ["Signed up", "Verified email", "Created first project", "Activated", "Paid"],
              "stage_order": [1, 2, 3, 4, 5]}).to_csv(OUT / "dim_funnel_stage.csv", index=False)

print(fact_user.shape, "users;", int(fact_user.is_activated.sum()), "activated;", int(fact_user.is_paid.sum()), "paid;",
      int(fact_user.in_experiment.sum()), "in experiment")
