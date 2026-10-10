-- 06_segmentation.sql
-- Where the value is: acquisition channel, subscription plan and engagement level.
-- Signups through 2025-11-30 only, so every user has at least 12 weeks of history.

-- name: segment_channel
WITH w4 AS (SELECT user_id FROM user_week_activity WHERE week_idx = 4)
SELECT d.acquisition_channel, count(*) AS signups,
       round(100.0 * avg(d.is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(d.is_paid::INT), 1)      AS paid_pct,
       round(100.0 * count(w4.user_id) / count(*), 1) AS w4_retention_pct,
       round(sum(COALESCE(d.mrr_usd, 0)) / count(*), 2) AS new_mrr_per_signup_usd,
       round(avg(d.mrr_usd) FILTER (WHERE d.is_paid), 0) AS avg_mrr_usd
FROM dim_user d LEFT JOIN w4 USING (user_id)
WHERE d.signup_date < DATE '2025-12-01'
GROUP BY d.acquisition_channel ORDER BY new_mrr_per_signup_usd DESC;

-- name: segment_plan
SELECT plan, billing_period, count(*) AS customers,
       round(avg(mrr_usd), 0) AS avg_mrr_usd,
       round(100.0 * avg(is_activated::INT), 1) AS activated_in_week1_pct,
       round(sum(mrr_usd), 0) AS total_mrr_started
FROM dim_user WHERE is_paid GROUP BY plan, billing_period
ORDER BY CASE plan WHEN 'Starter' THEN 1 WHEN 'Team' THEN 2 ELSE 3 END, billing_period;

-- name: segment_engagement
-- Engagement tier is set by week-0 usage; retention is measured later (week 4) so the comparison is not circular.
WITH w4 AS (SELECT user_id FROM user_week_activity WHERE week_idx = 4)
SELECT d.engagement_tier, count(*) AS signups,
       round(100.0 * avg(d.is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(d.is_paid::INT), 1)      AS paid_pct,
       round(100.0 * count(w4.user_id) / count(*), 1) AS w4_retention_pct
FROM dim_user d LEFT JOIN w4 USING (user_id)
WHERE d.signup_date < DATE '2025-12-01'
GROUP BY d.engagement_tier ORDER BY CASE d.engagement_tier WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END;

-- name: march_paid_social_burst
-- A three-week paid-social push in March changed the mix of new users.
WITH w4 AS (SELECT user_id FROM user_week_activity WHERE week_idx = 4)
SELECT d.signup_month, count(*) AS signups,
       round(100.0 * avg((d.acquisition_channel = 'paid_social')::INT), 1) AS paid_social_share_pct,
       round(100.0 * avg(d.is_activated::INT), 1) AS activated_pct,
       round(100.0 * avg(d.is_paid::INT), 1)      AS paid_pct,
       round(100.0 * count(w4.user_id) / count(*), 1) AS w4_retention_pct
FROM dim_user d LEFT JOIN w4 USING (user_id)
WHERE d.signup_date < DATE '2025-12-01'
GROUP BY d.signup_month ORDER BY d.signup_month;
