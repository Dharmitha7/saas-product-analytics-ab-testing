-- 02_funnel.sql
-- Signup -> verified -> first project -> teammate invited (activated) -> paid.
-- Activation = first project AND a teammate invited within 7 days of signup.

-- name: funnel_overall
WITH s AS (
    SELECT count(*) AS signups,
           count(*) FILTER (WHERE is_verified)   AS verified,
           count(*) FILTER (WHERE has_project)   AS project,
           count(*) FILTER (WHERE is_activated)  AS activated,
           count(*) FILTER (WHERE is_paid)       AS paid
    FROM dim_user
)
SELECT stage, users,
       round(100.0 * users / first_value(users) OVER (ORDER BY ord), 1) AS pct_of_signups,
       round(100.0 * users / lag(users) OVER (ORDER BY ord), 1)         AS pct_of_prior_step
FROM (
    SELECT 1 AS ord, 'Signed up' AS stage, signups AS users FROM s UNION ALL
    SELECT 2, 'Verified email', verified FROM s UNION ALL
    SELECT 3, 'Created first project', project FROM s UNION ALL
    SELECT 4, 'Activated (invited teammate in 7 days)', activated FROM s UNION ALL
    SELECT 5, 'Started paid plan', paid FROM s
) ORDER BY ord;

-- name: funnel_by_channel
SELECT acquisition_channel,
       count(*) AS signups,
       round(100.0 * avg(is_verified::INT), 1)   AS verified_pct,
       round(100.0 * avg(has_project::INT), 1)   AS project_pct,
       round(100.0 * avg(is_activated::INT), 1)  AS activated_pct,
       round(100.0 * avg(is_paid::INT), 1)       AS paid_pct,
       round(100.0 * sum(is_paid::INT) / NULLIF(sum(is_activated::INT), 0), 1) AS paid_per_activated_pct
FROM dim_user GROUP BY acquisition_channel ORDER BY paid_pct DESC;

-- name: funnel_by_company_size
SELECT company_size, count(*) AS signups,
       round(100.0 * avg(has_project::INT), 1)  AS project_pct,
       round(100.0 * avg(is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(is_paid::INT), 1)      AS paid_pct,
       round(100.0 * avg(has_invite::INT) FILTER (WHERE has_project), 1) AS invite_given_project_pct
FROM dim_user GROUP BY company_size
ORDER BY CASE company_size WHEN 'solo' THEN 1 WHEN '2-10' THEN 2 WHEN '11-50' THEN 3 ELSE 4 END;

-- name: funnel_by_device
SELECT device, count(*) AS signups,
       round(100.0 * avg(has_project::INT), 1)  AS project_pct,
       round(100.0 * avg(is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(is_paid::INT), 1)      AS paid_pct,
       round(100.0 * avg(has_invite::INT) FILTER (WHERE has_project), 1) AS invite_given_project_pct
FROM dim_user GROUP BY device ORDER BY signups DESC;

-- name: funnel_monthly_trend
SELECT signup_month, count(*) AS signups,
       round(100.0 * avg(is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(is_paid::INT), 1)      AS paid_pct
FROM dim_user GROUP BY signup_month ORDER BY signup_month;

-- name: activation_to_paid_gap
-- Why activation matters: conversion to paid for activated vs not activated users.
SELECT CASE WHEN is_activated THEN 'Activated' ELSE 'Not activated' END AS segment,
       count(*) AS users,
       round(100.0 * avg(is_paid::INT), 1) AS paid_pct,
       round(avg(mrr_usd) FILTER (WHERE is_paid), 0) AS avg_mrr_usd
FROM dim_user GROUP BY 1 ORDER BY 1;

-- name: time_between_steps
SELECT
  round(median(date_diff('minute', signup_ts, project_ts)) / 60.0, 1)      AS median_hours_signup_to_project,
  round(median(date_diff('minute', project_ts, invite_ts)) / 60.0, 1)      AS median_hours_project_to_invite,
  round(median(date_diff('minute', signup_ts, sub_start_ts)) / 1440.0, 1)  AS median_days_signup_to_paid
FROM dim_user;
