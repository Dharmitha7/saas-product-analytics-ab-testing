-- 04_churn.sql
-- Paid-customer churn and MRR movement. A billing month is approximated as 30.44 days.
-- A subscription is active from start_ts until end_ts (NULL = still active at the 2026-02-28 cutoff).

-- name: mrr_waterfall_monthly
WITH months AS (SELECT CAST(unnest(generate_series(DATE '2025-01-01', DATE '2026-02-01', INTERVAL 1 MONTH)) AS DATE) AS m)
SELECT m AS month,
       count(*) FILTER (WHERE s.start_ts < m AND (s.end_ts IS NULL OR s.end_ts >= m))                AS customers_start,
       count(*) FILTER (WHERE s.start_ts >= m AND s.start_ts < m + INTERVAL 1 MONTH)                 AS new_customers,
       count(*) FILTER (WHERE s.end_ts >= m AND s.end_ts < m + INTERVAL 1 MONTH)                     AS churned_customers,
       round(COALESCE(sum(s.mrr_usd) FILTER (WHERE s.start_ts < m AND (s.end_ts IS NULL OR s.end_ts >= m)), 0), 0) AS mrr_start,
       round(COALESCE(sum(s.mrr_usd) FILTER (WHERE s.start_ts >= m AND s.start_ts < m + INTERVAL 1 MONTH), 0), 0)  AS new_mrr,
       round(COALESCE(sum(s.mrr_usd) FILTER (WHERE s.end_ts >= m AND s.end_ts < m + INTERVAL 1 MONTH), 0), 0)      AS churned_mrr
FROM months CROSS JOIN stg_subs s
GROUP BY m ORDER BY m;

-- name: churn_by_plan
-- Average monthly logo churn = churn events / customer-months at risk, Jan 2025 to Feb 2026.
WITH months AS (SELECT CAST(unnest(generate_series(DATE '2025-01-01', DATE '2026-02-01', INTERVAL 1 MONTH)) AS DATE) AS m)
SELECT s.plan, s.billing_period,
       count(DISTINCT s.subscription_id) AS customers_ever,
       count(*) FILTER (WHERE s.start_ts < m AND (s.end_ts IS NULL OR s.end_ts >= m)) AS customer_months,
       count(*) FILTER (WHERE s.end_ts >= m AND s.end_ts < m + INTERVAL 1 MONTH)      AS churn_events,
       round(100.0 * count(*) FILTER (WHERE s.end_ts >= m AND s.end_ts < m + INTERVAL 1 MONTH)
             / NULLIF(count(*) FILTER (WHERE s.start_ts < m AND (s.end_ts IS NULL OR s.end_ts >= m)), 0), 2) AS monthly_churn_pct,
       round(avg(s.mrr_usd), 0) AS avg_mrr_usd
FROM months CROSS JOIN stg_subs s
GROUP BY s.plan, s.billing_period
ORDER BY CASE s.plan WHEN 'Starter' THEN 1 WHEN 'Team' THEN 2 ELSE 3 END, s.billing_period;

-- name: churn_by_activation
-- 6-month customer retention (monthly-billed customers who started before 2025-08-31), by first-week activation.
SELECT CASE WHEN d.is_activated THEN 'Activated in week 1' ELSE 'Not activated' END AS segment,
       count(*) AS customers,
       round(100.0 * avg((s.end_ts IS NULL OR s.end_ts > s.start_ts + INTERVAL 183 DAY)::INT), 1) AS retained_6m_pct
FROM stg_subs s JOIN dim_user d USING (user_id)
WHERE s.start_ts < TIMESTAMP '2025-08-31' AND s.billing_period = 'monthly'
GROUP BY 1 ORDER BY 1;

-- name: churn_by_channel
SELECT d.acquisition_channel, count(*) AS customers,
       round(100.0 * avg((s.end_ts IS NULL OR s.end_ts > s.start_ts + INTERVAL 183 DAY)::INT), 1) AS retained_6m_pct
FROM stg_subs s JOIN dim_user d USING (user_id)
WHERE s.start_ts < TIMESTAMP '2025-08-31' AND s.billing_period = 'monthly'
GROUP BY 1 ORDER BY retained_6m_pct DESC;
