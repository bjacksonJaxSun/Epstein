-- Migration: Add worker_heartbeat table for live worker visibility
-- Workers send a heartbeat every poll cycle (~2s) so we can see who's alive,
-- what code version they're running, and whether they're idle or busy.

-- ============================================
-- WORKER HEARTBEAT TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS worker_heartbeat (
    worker_id       VARCHAR(100) PRIMARY KEY,   -- machine:pid:thread
    hostname        VARCHAR(100) NOT NULL,
    code_version    VARCHAR(64),                -- SHA256 version_hash from DatabaseUpdater
    job_types       TEXT[],                     -- what job types this worker handles
    status          VARCHAR(20) DEFAULT 'idle', -- 'idle', 'busy', 'shutting_down'
    active_jobs     INT DEFAULT 0,
    started_at      TIMESTAMPTZ NOT NULL,       -- when this worker process started
    last_heartbeat  TIMESTAMPTZ DEFAULT NOW()   -- updated every cycle
);

CREATE INDEX IF NOT EXISTS idx_wh_last_heartbeat
ON worker_heartbeat(last_heartbeat DESC);

CREATE INDEX IF NOT EXISTS idx_wh_hostname
ON worker_heartbeat(hostname);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Upsert a worker heartbeat (called every poll cycle)
CREATE OR REPLACE FUNCTION upsert_worker_heartbeat(
    p_worker_id     VARCHAR(100),
    p_hostname      VARCHAR(100),
    p_code_version  VARCHAR(64),
    p_job_types     TEXT[],
    p_status        VARCHAR(20),
    p_active_jobs   INT,
    p_started_at    TIMESTAMPTZ
) RETURNS VOID AS $$
BEGIN
    INSERT INTO worker_heartbeat (
        worker_id, hostname, code_version, job_types,
        status, active_jobs, started_at, last_heartbeat
    ) VALUES (
        p_worker_id, p_hostname, p_code_version, p_job_types,
        p_status, p_active_jobs, p_started_at, NOW()
    )
    ON CONFLICT (worker_id) DO UPDATE SET
        hostname       = EXCLUDED.hostname,
        code_version   = EXCLUDED.code_version,
        job_types      = EXCLUDED.job_types,
        status         = EXCLUDED.status,
        active_jobs    = EXCLUDED.active_jobs,
        started_at     = EXCLUDED.started_at,
        last_heartbeat = NOW();
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- VIEWS
-- ============================================

-- Live workers: heartbeat within the last 60 seconds
CREATE OR REPLACE VIEW live_workers AS
SELECT
    worker_id,
    hostname,
    code_version,
    job_types,
    status,
    active_jobs,
    started_at,
    last_heartbeat,
    EXTRACT(EPOCH FROM (NOW() - last_heartbeat))::INT AS seconds_since_heartbeat
FROM worker_heartbeat
WHERE last_heartbeat > NOW() - INTERVAL '60 seconds'
ORDER BY last_heartbeat DESC;
