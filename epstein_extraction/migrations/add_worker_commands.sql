-- Migration: Add remote command support to worker_heartbeat
-- Workers check for pending commands on every heartbeat cycle.
-- Commands: 'shutdown', 'restart', 'kill_children'

-- Add pending_command column
ALTER TABLE worker_heartbeat
ADD COLUMN IF NOT EXISTS pending_command VARCHAR(50) DEFAULT NULL;

-- Update upsert to return pending_command and clear it atomically
CREATE OR REPLACE FUNCTION upsert_worker_heartbeat(
    p_worker_id     VARCHAR(100),
    p_hostname      VARCHAR(100),
    p_code_version  VARCHAR(64),
    p_job_types     TEXT[],
    p_status        VARCHAR(20),
    p_active_jobs   INT,
    p_started_at    TIMESTAMPTZ
) RETURNS VARCHAR(50) AS $$
DECLARE
    v_command VARCHAR(50);
BEGIN
    -- Read the current pending command BEFORE clearing it.
    -- FOR UPDATE locks the row so the value cannot change between read and clear.
    -- NOTE: RETURNING after SET pending_command = NULL would return NULL (post-update
    -- value), so we must SELECT first to capture the pre-update value.
    SELECT pending_command INTO v_command
    FROM worker_heartbeat
    WHERE worker_id = p_worker_id
    FOR UPDATE;

    -- Upsert the heartbeat, explicitly clearing pending_command
    INSERT INTO worker_heartbeat (
        worker_id, hostname, code_version, job_types,
        status, active_jobs, started_at, last_heartbeat
    ) VALUES (
        p_worker_id, p_hostname, p_code_version, p_job_types,
        p_status, p_active_jobs, p_started_at, NOW()
    )
    ON CONFLICT (worker_id) DO UPDATE SET
        hostname        = EXCLUDED.hostname,
        code_version    = EXCLUDED.code_version,
        job_types       = EXCLUDED.job_types,
        status          = EXCLUDED.status,
        active_jobs     = EXCLUDED.active_jobs,
        started_at      = EXCLUDED.started_at,
        last_heartbeat  = NOW(),
        pending_command = NULL;

    RETURN v_command;
END;
$$ LANGUAGE plpgsql;


-- Send a command to a specific worker
CREATE OR REPLACE FUNCTION send_worker_command(
    p_worker_id VARCHAR(100),
    p_command   VARCHAR(50)
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE worker_heartbeat
    SET pending_command = p_command
    WHERE worker_id = p_worker_id;
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;


-- Send a command to ALL workers on a specific host
CREATE OR REPLACE FUNCTION send_host_command(
    p_hostname VARCHAR(100),
    p_command  VARCHAR(50)
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE worker_heartbeat
    SET pending_command = p_command
    WHERE hostname = p_hostname
      AND last_heartbeat > NOW() - INTERVAL '60 seconds';
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- Send a command to ALL live workers
CREATE OR REPLACE FUNCTION send_all_workers_command(
    p_command VARCHAR(50)
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE worker_heartbeat
    SET pending_command = p_command
    WHERE last_heartbeat > NOW() - INTERVAL '60 seconds';
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
