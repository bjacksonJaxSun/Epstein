-- Migration: Add job_pool table for multi-machine CPU-type pooling operations
-- This table uses PostgreSQL's FOR UPDATE SKIP LOCKED for atomic batch claiming
-- Based on the proven download_queue pattern

-- ============================================
-- JOB POOL TABLE
-- Multi-machine job queue with atomic claiming
-- ============================================

CREATE TABLE IF NOT EXISTS job_pool (
    job_id BIGSERIAL PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,        -- 'general', 'ocr', 'entity', 'vision'

    -- Job definition
    payload JSONB NOT NULL,                -- Job-specific data (action, command, args, etc.)
    priority INT DEFAULT 0,                -- Higher = more urgent
    timeout_seconds INT DEFAULT 300,

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- pending, claimed, running, completed, failed, skipped
    claimed_by VARCHAR(100),               -- machine:pid:thread
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Results
    result JSONB,                          -- Output from job execution
    output_text TEXT,                      -- stdout/stderr capture
    exit_code INT,

    -- Error tracking
    error_message TEXT,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    last_error_at TIMESTAMPTZ,

    -- Metadata
    source_machine VARCHAR(100),           -- Who submitted the job
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================
-- INDEXES
-- ============================================

-- Primary work queue: find pending jobs by priority
CREATE INDEX IF NOT EXISTS idx_jp_pending
ON job_pool(priority DESC, created_at)
WHERE status = 'pending';

-- Filter by job type
CREATE INDEX IF NOT EXISTS idx_jp_pending_type
ON job_pool(job_type, priority DESC, created_at)
WHERE status = 'pending';

-- Failed items eligible for retry
CREATE INDEX IF NOT EXISTS idx_jp_failed_retry
ON job_pool(job_type, retry_count)
WHERE status = 'failed';

-- Stale claim detection
CREATE INDEX IF NOT EXISTS idx_jp_claimed_timeout
ON job_pool(claimed_at)
WHERE status IN ('claimed', 'running');

-- Status summary queries
CREATE INDEX IF NOT EXISTS idx_jp_status
ON job_pool(status);

-- Job type summary
CREATE INDEX IF NOT EXISTS idx_jp_job_type
ON job_pool(job_type);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Atomically claim a batch of jobs
-- Uses FOR UPDATE SKIP LOCKED to prevent race conditions
CREATE OR REPLACE FUNCTION claim_job_batch(
    p_worker_id VARCHAR(100),
    p_job_types VARCHAR(50)[],
    p_batch_size INT DEFAULT 5
) RETURNS TABLE(
    job_id BIGINT,
    job_type VARCHAR(50),
    payload JSONB,
    timeout_seconds INT
) AS $$
BEGIN
    RETURN QUERY
    WITH claimed AS (
        SELECT jp.job_id
        FROM job_pool jp
        WHERE jp.status = 'pending'
          AND (p_job_types IS NULL OR jp.job_type = ANY(p_job_types))
        ORDER BY jp.priority DESC, jp.created_at
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    )
    UPDATE job_pool jp
    SET status = 'claimed',
        claimed_by = p_worker_id,
        claimed_at = NOW(),
        retry_count = retry_count + 1,
        updated_at = NOW()
    FROM claimed c
    WHERE jp.job_id = c.job_id
    RETURNING jp.job_id, jp.job_type, jp.payload, jp.timeout_seconds;
END;
$$ LANGUAGE plpgsql;


-- Mark job as started (running)
CREATE OR REPLACE FUNCTION start_job(
    p_job_id BIGINT
) RETURNS VOID AS $$
BEGIN
    UPDATE job_pool
    SET status = 'running',
        started_at = NOW(),
        updated_at = NOW()
    WHERE job_id = p_job_id;
END;
$$ LANGUAGE plpgsql;


-- Mark job as completed
CREATE OR REPLACE FUNCTION complete_job(
    p_job_id BIGINT,
    p_result JSONB DEFAULT NULL,
    p_output_text TEXT DEFAULT NULL,
    p_exit_code INT DEFAULT 0
) RETURNS VOID AS $$
BEGIN
    UPDATE job_pool
    SET status = 'completed',
        completed_at = NOW(),
        result = p_result,
        output_text = p_output_text,
        exit_code = p_exit_code,
        error_message = NULL,
        updated_at = NOW()
    WHERE job_id = p_job_id;
END;
$$ LANGUAGE plpgsql;


-- Mark job as failed
CREATE OR REPLACE FUNCTION fail_job(
    p_job_id BIGINT,
    p_error_message TEXT,
    p_output_text TEXT DEFAULT NULL,
    p_exit_code INT DEFAULT -1
) RETURNS VOID AS $$
DECLARE
    v_retry_count INT;
    v_max_retries INT;
BEGIN
    SELECT retry_count, max_retries INTO v_retry_count, v_max_retries
    FROM job_pool WHERE job_id = p_job_id;

    IF v_retry_count >= v_max_retries THEN
        -- Exceeded max retries, mark as skipped (permanent failure)
        UPDATE job_pool
        SET status = 'skipped',
            error_message = p_error_message,
            output_text = p_output_text,
            exit_code = p_exit_code,
            last_error_at = NOW(),
            claimed_by = NULL,
            claimed_at = NULL,
            updated_at = NOW()
        WHERE job_id = p_job_id;
    ELSE
        -- Mark as failed, eligible for retry
        UPDATE job_pool
        SET status = 'failed',
            error_message = p_error_message,
            output_text = p_output_text,
            exit_code = p_exit_code,
            last_error_at = NOW(),
            claimed_by = NULL,
            claimed_at = NULL,
            updated_at = NOW()
        WHERE job_id = p_job_id;
    END IF;
END;
$$ LANGUAGE plpgsql;


-- Reset failed jobs to pending for retry
CREATE OR REPLACE FUNCTION reset_failed_jobs(
    p_job_type VARCHAR(50) DEFAULT NULL
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE job_pool
    SET status = 'pending',
        error_message = NULL,
        claimed_by = NULL,
        claimed_at = NULL,
        updated_at = NOW()
    WHERE status = 'failed'
      AND retry_count < max_retries
      AND (p_job_type IS NULL OR job_type = p_job_type);

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- Reclaim stale jobs (crashed workers)
CREATE OR REPLACE FUNCTION reclaim_stale_jobs(
    p_timeout_minutes INT DEFAULT 30
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE job_pool
    SET status = 'pending',
        claimed_by = NULL,
        claimed_at = NULL,
        started_at = NULL,
        updated_at = NOW()
    WHERE status IN ('claimed', 'running')
      AND claimed_at < NOW() - (p_timeout_minutes || ' minutes')::INTERVAL
      AND retry_count < max_retries;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- Submit a new job
CREATE OR REPLACE FUNCTION submit_job(
    p_job_type VARCHAR(50),
    p_payload JSONB,
    p_priority INT DEFAULT 0,
    p_timeout_seconds INT DEFAULT 300,
    p_source_machine VARCHAR(100) DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_job_id BIGINT;
BEGIN
    INSERT INTO job_pool (job_type, payload, priority, timeout_seconds, source_machine)
    VALUES (p_job_type, p_payload, p_priority, p_timeout_seconds, p_source_machine)
    RETURNING job_id INTO v_job_id;

    RETURN v_job_id;
END;
$$ LANGUAGE plpgsql;


-- Get job by ID
CREATE OR REPLACE FUNCTION get_job(
    p_job_id BIGINT
) RETURNS TABLE(
    job_id BIGINT,
    job_type VARCHAR(50),
    payload JSONB,
    priority INT,
    timeout_seconds INT,
    status VARCHAR(20),
    claimed_by VARCHAR(100),
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSONB,
    output_text TEXT,
    exit_code INT,
    error_message TEXT,
    retry_count INT,
    max_retries INT,
    source_machine VARCHAR(100),
    created_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT jp.job_id, jp.job_type, jp.payload, jp.priority, jp.timeout_seconds,
           jp.status, jp.claimed_by, jp.claimed_at, jp.started_at, jp.completed_at,
           jp.result, jp.output_text, jp.exit_code, jp.error_message,
           jp.retry_count, jp.max_retries, jp.source_machine, jp.created_at
    FROM job_pool jp
    WHERE jp.job_id = p_job_id;
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- VIEWS
-- ============================================

-- Progress summary by job type
CREATE OR REPLACE VIEW job_pool_progress AS
SELECT
    job_type,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    COUNT(*) FILTER (WHERE status = 'claimed') as claimed,
    COUNT(*) FILTER (WHERE status = 'running') as running,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE status = 'skipped') as skipped,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'completed') / NULLIF(COUNT(*), 0), 1) as pct_complete
FROM job_pool
GROUP BY job_type
ORDER BY job_type;


-- Active workers view
CREATE OR REPLACE VIEW active_pool_workers AS
SELECT
    claimed_by as worker_id,
    job_type,
    COUNT(*) as jobs_claimed,
    MIN(claimed_at) as oldest_claim,
    MAX(claimed_at) as newest_claim,
    EXTRACT(EPOCH FROM (NOW() - MIN(claimed_at)))/60 as minutes_since_oldest
FROM job_pool
WHERE status IN ('claimed', 'running')
GROUP BY claimed_by, job_type
ORDER BY job_type, oldest_claim;


-- Recent errors view
CREATE OR REPLACE VIEW recent_pool_errors AS
SELECT
    job_id,
    job_type,
    payload->>'action' as action,
    error_message,
    retry_count,
    last_error_at,
    status
FROM job_pool
WHERE status IN ('failed', 'skipped')
  AND last_error_at IS NOT NULL
ORDER BY last_error_at DESC
LIMIT 100;


-- Job results (most recent completed)
CREATE OR REPLACE VIEW recent_job_results AS
SELECT
    job_id,
    job_type,
    payload->>'action' as action,
    status,
    exit_code,
    result,
    LEFT(output_text, 500) as output_preview,
    EXTRACT(EPOCH FROM (completed_at - started_at)) as duration_seconds,
    completed_at
FROM job_pool
WHERE status = 'completed'
ORDER BY completed_at DESC
LIMIT 100;


-- Grant permissions if needed
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO epstein_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO epstein_user;
