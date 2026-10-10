-- 05_feature_adoption.sql
-- Population: users who created a project and signed up by 2025-10-31 (so 12+ weeks of history exist).
-- Adoption = used the feature in the first 30 days.
-- Outcome = active in days 56-83, measured AFTER the adoption window.
-- These are associations, not proof of cause: adopters are also more engaged to begin with.

-- name: feature_adoption_and_retention
WITH pop AS (SELECT user_id FROM dim_user WHERE has_project AND signup_date <= DATE '2025-10-31'),
used AS (
    SELECT DISTINCT e.user_id, e.feature
    FROM stg_events e JOIN dim_user u USING (user_id)
    WHERE e.feature IS NOT NULL AND e.event_ts < u.signup_ts + INTERVAL 30 DAY
),
late AS (
    SELECT DISTINCT e.user_id FROM stg_events e JOIN dim_user u USING (user_id)
    WHERE e.is_usage AND e.event_ts >= u.signup_ts + INTERVAL 56 DAY AND e.event_ts < u.signup_ts + INTERVAL 84 DAY
),
feats AS (SELECT DISTINCT feature FROM used)
SELECT f.feature,
       count(*) AS users,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NOT NULL) / count(*), 1) AS adoption_pct,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NOT NULL AND l.user_id IS NOT NULL)
             / NULLIF(count(*) FILTER (WHERE u.user_id IS NOT NULL), 0), 1) AS retained_adopters_pct,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NULL AND l.user_id IS NOT NULL)
             / NULLIF(count(*) FILTER (WHERE u.user_id IS NULL), 0), 1) AS retained_non_adopters_pct
FROM feats f CROSS JOIN pop p
LEFT JOIN used u ON u.user_id = p.user_id AND u.feature = f.feature
LEFT JOIN late l ON l.user_id = p.user_id
GROUP BY f.feature ORDER BY retained_adopters_pct DESC;

-- name: feature_retention_within_activated
-- Same comparison restricted to activated users: strips out the "engaged users do everything" effect.
WITH pop AS (SELECT user_id FROM dim_user WHERE is_activated AND signup_date <= DATE '2025-10-31'),
used AS (
    SELECT DISTINCT e.user_id, e.feature
    FROM stg_events e JOIN dim_user u USING (user_id)
    WHERE e.feature IS NOT NULL AND e.event_ts < u.signup_ts + INTERVAL 30 DAY
),
late AS (
    SELECT DISTINCT e.user_id FROM stg_events e JOIN dim_user u USING (user_id)
    WHERE e.is_usage AND e.event_ts >= u.signup_ts + INTERVAL 56 DAY AND e.event_ts < u.signup_ts + INTERVAL 84 DAY
),
feats AS (SELECT DISTINCT feature FROM used)
SELECT f.feature, count(*) AS activated_users,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NOT NULL) / count(*), 1) AS adoption_pct,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NOT NULL AND l.user_id IS NOT NULL)
             / NULLIF(count(*) FILTER (WHERE u.user_id IS NOT NULL), 0), 1) AS retained_adopters_pct,
       round(100.0 * count(*) FILTER (WHERE u.user_id IS NULL AND l.user_id IS NOT NULL)
             / NULLIF(count(*) FILTER (WHERE u.user_id IS NULL), 0), 1) AS retained_non_adopters_pct
FROM feats f CROSS JOIN pop p
LEFT JOIN used u ON u.user_id = p.user_id AND u.feature = f.feature
LEFT JOIN late l ON l.user_id = p.user_id
GROUP BY f.feature ORDER BY retained_adopters_pct DESC;
