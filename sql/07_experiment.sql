-- 07_experiment.sql
-- exp_onboarding_checklist_v2 (SIMULATED experiment). Control = current onboarding, treatment = guided setup checklist.
-- Randomised 50/50 at signup, signups 2025-10-13 to 2025-11-23. Population = exp_users (see 00_clean.sql).

-- name: exp_srm
-- Sample ratio check inputs: users per arm. The test of this split is in the notebook.
SELECT variant, count(*) AS users FROM exp_users GROUP BY variant ORDER BY variant;

-- name: exp_summary
SELECT variant, count(*) AS users,
       sum(is_activated::INT)                         AS activated,
       round(100.0 * avg(is_activated::INT), 2)       AS activation_pct,
       sum(is_paid_30d::INT)                          AS paid_30d,
       round(100.0 * avg(is_paid_30d::INT), 2)        AS paid_30d_pct,
       round(100.0 * avg(retained_w1::INT), 2)        AS retained_w1_pct,
       round(1.0 * sum(tickets_14d) / count(*), 4)    AS tickets_per_user_14d,
       round(median(hours_to_invite) FILTER (WHERE is_activated), 1) AS median_hours_to_invite_activated
FROM exp_users GROUP BY variant ORDER BY variant;

-- name: exp_by_test_week
SELECT test_week, variant, count(*) AS users,
       round(100.0 * avg(is_activated::INT), 2) AS activation_pct
FROM exp_users GROUP BY test_week, variant ORDER BY test_week, variant;

-- name: exp_by_company_size
SELECT company_size, variant, count(*) AS users,
       round(100.0 * avg(is_activated::INT), 2) AS activation_pct
FROM exp_users GROUP BY company_size, variant
ORDER BY CASE company_size WHEN 'solo' THEN 1 WHEN '2-10' THEN 2 WHEN '11-50' THEN 3 ELSE 4 END, variant;

-- name: exp_by_channel
SELECT acquisition_channel, variant, count(*) AS users,
       round(100.0 * avg(is_activated::INT), 2) AS activation_pct
FROM exp_users GROUP BY acquisition_channel, variant ORDER BY acquisition_channel, variant;

-- name: exp_by_device
SELECT device, variant, count(*) AS users,
       round(100.0 * avg(is_activated::INT), 2) AS activation_pct
FROM exp_users GROUP BY device, variant ORDER BY device, variant;

-- name: exp_daily_enrolment
SELECT signup_date, variant, count(*) AS users FROM exp_users GROUP BY signup_date, variant ORDER BY signup_date, variant;

-- name: exp_users_export
-- User-level extract that the statistics notebook reads.
SELECT user_id, variant, signup_date, test_week, acquisition_channel, device, company_size,
       is_activated::INT AS activated, is_paid_30d::INT AS paid_30d, retained_w1::INT AS retained_w1,
       tickets_14d, hours_to_invite, COALESCE(mrr_usd, 0) AS mrr_usd
FROM exp_users
ORDER BY user_id;

-- name: exp_population_waterfall
-- How the raw assignment table was reduced to the analysis population.
SELECT 1 AS step, 'Assignment rows in raw table' AS description, count(*) AS users FROM raw_experiment_assignments
UNION ALL
SELECT 2, 'Distinct users assigned', count(*) FROM exp_assignment_clean
UNION ALL
SELECT 3, 'Less: users shown both arms', -count(*) FROM exp_assignment_clean WHERE has_conflict
UNION ALL
SELECT 4, 'Less: internal test accounts (conflict-free)', -count(*) FROM exp_assignment_clean a
  JOIN stg_users u USING (user_id) WHERE NOT a.has_conflict AND u.is_internal
UNION ALL
SELECT 5, 'Analysis population', count(*) FROM exp_users
ORDER BY step;
