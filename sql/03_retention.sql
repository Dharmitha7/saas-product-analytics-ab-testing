-- 03_retention.sql
-- Active = at least one usage event in the period. Base = all (non-internal) signups in the cohort.
-- Only fully observed periods are reported (no partial last week or month).

-- name: cohort_retention_weekly
WITH cohort AS (
    SELECT signup_week, count(*) AS cohort_size FROM dim_user
    WHERE signup_week >= DATE '2025-01-06' AND signup_week < DATE '2025-12-29'
    GROUP BY signup_week
), act AS (
    SELECT u.signup_week, a.week_idx, count(*) AS active_users
    FROM user_week_activity a JOIN dim_user u USING (user_id)
    GROUP BY u.signup_week, a.week_idx
)
SELECT c.signup_week, a.week_idx, c.cohort_size, a.active_users,
       round(100.0 * a.active_users / c.cohort_size, 2) AS retention_pct
FROM cohort c JOIN act a USING (signup_week)
WHERE a.week_idx <= 12 AND c.signup_week + 7 * (a.week_idx + 1) <= DATE '2026-02-28'
ORDER BY c.signup_week, a.week_idx;

-- name: cohort_retention_monthly
-- Month index = 30-day block after signup (block 0 = days 0-29).
WITH ev AS (
    SELECT DISTINCT e.user_id, CAST(floor(date_diff('second', u.signup_ts, e.event_ts) / 2592000.0) AS INTEGER) AS m
    FROM stg_events e JOIN dim_user u USING (user_id) WHERE e.is_usage
), cohort AS (
    SELECT signup_month, count(*) AS cohort_size FROM dim_user
    WHERE signup_month < DATE '2025-12-01' GROUP BY signup_month
), act AS (
    SELECT u.signup_month, ev.m, count(*) AS active_users
    FROM ev JOIN dim_user u USING (user_id) GROUP BY u.signup_month, ev.m
)
SELECT c.signup_month, a.m AS month_idx, c.cohort_size, a.active_users,
       round(100.0 * a.active_users / c.cohort_size, 2) AS retention_pct
FROM cohort c JOIN act a USING (signup_month)
WHERE a.m <= 6
  AND CAST(c.signup_month + INTERVAL 1 MONTH AS DATE) + 30 * (a.m + 1) <= DATE '2026-02-28'
ORDER BY c.signup_month, a.m;

-- name: retention_curve_by_activation
-- Weekly retention for activated vs not activated users, signups Jan-Aug 2025 (12+ weeks observed).
WITH base AS (SELECT user_id, is_activated FROM dim_user WHERE signup_date < DATE '2025-09-01'),
tot AS (SELECT is_activated, count(*) AS n FROM base GROUP BY 1),
act AS (SELECT b.is_activated, a.week_idx, count(*) AS active_users
        FROM user_week_activity a JOIN base b USING (user_id) WHERE a.week_idx <= 12 GROUP BY 1, 2)
SELECT CASE WHEN a.is_activated THEN 'Activated' ELSE 'Not activated' END AS segment, a.week_idx,
       round(100.0 * a.active_users / t.n, 2) AS retention_pct
FROM act a JOIN tot t USING (is_activated) ORDER BY 1, 2;

-- name: retention_by_channel
-- W1, W4, W8 retention by acquisition channel, signups Jan-Aug 2025.
WITH base AS (SELECT user_id, acquisition_channel FROM dim_user WHERE signup_date < DATE '2025-09-01'),
tot AS (SELECT acquisition_channel, count(*) AS n FROM base GROUP BY 1)
SELECT t.acquisition_channel, t.n AS signups,
       round(100.0 * count(DISTINCT a.user_id) FILTER (WHERE a.week_idx = 1) / t.n, 1) AS w1_pct,
       round(100.0 * count(DISTINCT a.user_id) FILTER (WHERE a.week_idx = 4) / t.n, 1) AS w4_pct,
       round(100.0 * count(DISTINCT a.user_id) FILTER (WHERE a.week_idx = 8) / t.n, 1) AS w8_pct
FROM tot t JOIN base b USING (acquisition_channel)
LEFT JOIN user_week_activity a ON a.user_id = b.user_id
GROUP BY t.acquisition_channel, t.n ORDER BY w4_pct DESC;
