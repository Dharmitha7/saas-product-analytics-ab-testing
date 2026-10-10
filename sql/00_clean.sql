-- 00_clean.sql
-- Builds the analysis-ready layer from the raw tables (raw_users, raw_events, raw_subscriptions,
-- raw_experiment_assignments, raw_support_tickets). Every later query reads only from these tables.
-- Data cutoff: 2026-02-28. Engine: DuckDB (ANSI SQL plus a few DuckDB date helpers).

-- 1. Users: standardise nulls, flag internal test accounts, add signup week and month.
CREATE OR REPLACE TABLE stg_users AS
SELECT
    user_id,
    signup_ts,
    CAST(signup_ts AS DATE)                        AS signup_date,
    CAST(date_trunc('week', signup_ts) AS DATE)    AS signup_week,
    CAST(date_trunc('month', signup_ts) AS DATE)   AS signup_month,
    COALESCE(acquisition_channel, 'unknown')       AS acquisition_channel,
    COALESCE(country, 'unknown')                   AS country,
    device,
    company_size,
    (email_domain = 'tasklane.com')                AS is_internal
FROM raw_users;

-- 2. Events: drop internal accounts, remove exact duplicates, clamp events stamped before signup.
--    usage events = anything a person does inside the product (excludes signup, verification, billing).
CREATE OR REPLACE TABLE stg_events AS
WITH dedup AS (
    SELECT e.*,
           row_number() OVER (PARTITION BY user_id, event_name, event_ts, feature ORDER BY event_id) AS rn
    FROM raw_events e
)
SELECT
    d.event_id,
    d.user_id,
    GREATEST(d.event_ts, u.signup_ts)                                   AS event_ts,
    (d.event_ts < u.signup_ts)                                          AS was_clock_skewed,
    d.event_name,
    d.feature,
    d.event_name NOT IN ('signup', 'email_verified', 'subscription_started') AS is_usage,
    CAST(floor(date_diff('second', u.signup_ts, GREATEST(d.event_ts, u.signup_ts)) / 604800.0) AS INTEGER) AS week_idx
FROM dedup d
JOIN stg_users u USING (user_id)
WHERE d.rn = 1
  AND NOT u.is_internal;

-- 3. One row per user per week in which the user did something in the product.
CREATE OR REPLACE TABLE user_week_activity AS
SELECT DISTINCT user_id, week_idx
FROM stg_events
WHERE is_usage;

-- 4. Subscriptions (internal accounts excluded).
CREATE OR REPLACE TABLE stg_subs AS
SELECT s.*
FROM raw_subscriptions s
JOIN stg_users u USING (user_id)
WHERE NOT u.is_internal;

-- 5. Experiment assignment: one row per user. Users shown both arms (cookie loss) are flagged and excluded later.
CREATE OR REPLACE TABLE exp_assignment_clean AS
SELECT
    user_id,
    experiment_id,
    min(variant)                  AS variant,
    min(assigned_ts)              AS assigned_ts,
    count(DISTINCT variant) > 1   AS has_conflict
FROM raw_experiment_assignments
GROUP BY user_id, experiment_id;

-- 6. Milestones per user (first time each funnel step happened).
CREATE OR REPLACE TABLE user_milestones AS
SELECT
    user_id,
    min(event_ts) FILTER (WHERE event_name = 'email_verified')     AS verified_ts,
    min(event_ts) FILTER (WHERE event_name = 'project_created')    AS project_ts,
    min(event_ts) FILTER (WHERE event_name = 'teammate_invited')   AS invite_ts,
    count(*) FILTER (WHERE is_usage AND week_idx = 0)              AS wk0_usage_events
FROM stg_events
GROUP BY user_id;

-- 7. The user dimension used by every analysis. One row per user.
--    Activated = created a first project AND invited a teammate within 7 days of signup.
--    Engagement tier = number of usage events in the first 7 days (low 0-2, medium 3-9, high 10+).
CREATE OR REPLACE TABLE dim_user AS
SELECT
    u.user_id, u.signup_ts, u.signup_date, u.signup_week, u.signup_month,
    u.acquisition_channel, u.country, u.device, u.company_size,
    m.verified_ts, m.project_ts, m.invite_ts,
    (m.verified_ts IS NOT NULL)                                              AS is_verified,
    (m.project_ts  IS NOT NULL)                                              AS has_project,
    (m.invite_ts   IS NOT NULL)                                              AS has_invite,
    (m.project_ts IS NOT NULL AND m.invite_ts IS NOT NULL
        AND m.project_ts <= u.signup_ts + INTERVAL 7 DAY
        AND m.invite_ts  <= u.signup_ts + INTERVAL 7 DAY)                    AS is_activated,
    COALESCE(m.wk0_usage_events, 0)                                          AS wk0_usage_events,
    CASE WHEN COALESCE(m.wk0_usage_events, 0) >= 10 THEN 'high'
         WHEN COALESCE(m.wk0_usage_events, 0) >= 3  THEN 'medium'
         ELSE 'low' END                                                      AS engagement_tier,
    s.subscription_id, s.plan, s.billing_period, s.mrr_usd,
    s.start_ts AS sub_start_ts, s.end_ts AS sub_end_ts,
    (s.user_id IS NOT NULL)                                                  AS is_paid,
    (s.start_ts <= u.signup_ts + INTERVAL 30 DAY)                            AS is_paid_30d
FROM stg_users u
LEFT JOIN user_milestones m USING (user_id)
LEFT JOIN stg_subs s USING (user_id)
WHERE NOT u.is_internal;

-- 8. Experiment population: assigned inside the test window, internal accounts and conflicted users removed.
CREATE OR REPLACE TABLE exp_users AS
SELECT
    d.user_id, a.variant, d.signup_date, d.signup_ts,
    CAST(floor(date_diff('day', DATE '2025-10-13', d.signup_date) / 7.0) AS INTEGER) AS test_week,
    d.acquisition_channel, d.device, d.company_size,
    d.is_activated,
    COALESCE(d.is_paid_30d, FALSE)                                           AS is_paid_30d,
    d.mrr_usd,
    date_diff('minute', d.signup_ts, d.invite_ts) / 60.0                     AS hours_to_invite,
    EXISTS (SELECT 1 FROM user_week_activity w WHERE w.user_id = d.user_id AND w.week_idx = 1) AS retained_w1,
    (SELECT count(*) FROM raw_support_tickets t
      WHERE t.user_id = d.user_id AND t.created_ts <= d.signup_ts + INTERVAL 14 DAY)           AS tickets_14d
FROM dim_user d
JOIN exp_assignment_clean a USING (user_id)
WHERE NOT a.has_conflict
  AND a.experiment_id = 'exp_onboarding_checklist_v2';
