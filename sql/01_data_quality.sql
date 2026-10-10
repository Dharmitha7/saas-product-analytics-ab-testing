-- 01_data_quality.sql
-- What was wrong with the raw data, and how each issue was handled.

-- name: dq_summary
SELECT 'Raw users' AS check_name, count(*) AS rows_affected, count(*) AS rows_total,
       'Starting population' AS treatment FROM raw_users
UNION ALL
SELECT 'Internal test accounts (tasklane.com)', count(*), (SELECT count(*) FROM raw_users),
       'Excluded from all analysis' FROM raw_users WHERE email_domain = 'tasklane.com'
UNION ALL
SELECT 'Users with no acquisition channel', count(*), (SELECT count(*) FROM raw_users),
       'Kept; labelled unknown' FROM raw_users WHERE acquisition_channel IS NULL
UNION ALL
SELECT 'Users with no country', count(*), (SELECT count(*) FROM raw_users),
       'Kept; labelled unknown' FROM raw_users WHERE country IS NULL
UNION ALL
SELECT 'Exact duplicate events',
       (SELECT count(*) FROM raw_events) - (SELECT count(*) FROM (SELECT DISTINCT user_id, event_name, event_ts, feature FROM raw_events)),
       (SELECT count(*) FROM raw_events), 'Removed (kept first occurrence)'
UNION ALL
SELECT 'Events stamped before signup (clock skew)', count(*), (SELECT count(*) FROM raw_events),
       'Timestamp clamped to signup time'
FROM raw_events e JOIN raw_users u USING (user_id) WHERE e.event_ts < u.signup_ts
UNION ALL
SELECT 'Users assigned to both experiment arms', count(*),
       (SELECT count(DISTINCT user_id) FROM raw_experiment_assignments),
       'Excluded from experiment readout'
FROM exp_assignment_clean WHERE has_conflict;

-- name: dq_event_volume_by_name
SELECT event_name, count(*) AS events, count(DISTINCT user_id) AS users
FROM stg_events GROUP BY event_name ORDER BY events DESC;
