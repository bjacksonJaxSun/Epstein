-- Migration: Add download_queue table for multi-machine PDF download coordination
-- This table uses PostgreSQL's FOR UPDATE SKIP LOCKED for atomic batch claiming

-- ============================================
-- DOWNLOAD QUEUE TABLE
-- ============================================

CREATE TABLE IF NOT EXISTS download_queue (
    queue_id BIGSERIAL PRIMARY KEY,
    efta_number VARCHAR(20) NOT NULL,
    dataset_number INT NOT NULL,

    -- Source information
    source_type VARCHAR(20) NOT NULL,  -- 'geeken_zip', 'azure_blob', 'doj_direct'
    source_path TEXT NOT NULL,          -- Zip entry path, blob name, or filename
    doj_url TEXT,                        -- Direct DOJ URL (for fallback)

    -- Target
    r2_key TEXT,                         -- DataSet_{N}/{efta}.pdf

    -- Status tracking
    status VARCHAR(20) DEFAULT 'pending',  -- pending, claimed, completed, failed, skipped
    claimed_by VARCHAR(100),               -- machine:pid:thread
    claimed_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Error tracking
    error_message TEXT,
    retry_count INT DEFAULT 0,
    last_error_at TIMESTAMPTZ,

    -- Metadata
    file_size_bytes BIGINT,
    actual_source_used VARCHAR(20),      -- Which source actually succeeded
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT uq_download_queue_efta UNIQUE (efta_number)
);

-- ============================================
-- INDEXES
-- ============================================

-- Primary work queue index: find pending items for a dataset
CREATE INDEX IF NOT EXISTS idx_dq_pending_dataset
ON download_queue(dataset_number, efta_number)
WHERE status = 'pending';

-- Failed items eligible for retry
CREATE INDEX IF NOT EXISTS idx_dq_failed_retry
ON download_queue(dataset_number, retry_count)
WHERE status = 'failed';

-- Stale claim detection (for crashed workers)
CREATE INDEX IF NOT EXISTS idx_dq_claimed_timeout
ON download_queue(claimed_at)
WHERE status = 'claimed';

-- Status summary queries
CREATE INDEX IF NOT EXISTS idx_dq_status
ON download_queue(status);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Atomically claim a batch of downloads
-- Uses FOR UPDATE SKIP LOCKED to prevent race conditions
CREATE OR REPLACE FUNCTION claim_download_batch(
    p_dataset INT,
    p_batch_size INT,
    p_worker_id VARCHAR(100)
) RETURNS TABLE(
    queue_id BIGINT,
    efta_number VARCHAR(20),
    source_type VARCHAR(20),
    source_path TEXT,
    doj_url TEXT,
    r2_key TEXT
) AS $$
BEGIN
    RETURN QUERY
    WITH claimed AS (
        SELECT dq.queue_id
        FROM download_queue dq
        WHERE dq.status = 'pending'
          AND dq.dataset_number = p_dataset
        ORDER BY dq.efta_number
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    )
    UPDATE download_queue dq
    SET status = 'claimed',
        claimed_by = p_worker_id,
        claimed_at = NOW(),
        updated_at = NOW()
    FROM claimed c
    WHERE dq.queue_id = c.queue_id
    RETURNING dq.queue_id, dq.efta_number, dq.source_type, dq.source_path, dq.doj_url, dq.r2_key;
END;
$$ LANGUAGE plpgsql;


-- Mark a download as completed
CREATE OR REPLACE FUNCTION complete_download(
    p_queue_id BIGINT,
    p_r2_key TEXT,
    p_file_size BIGINT,
    p_source_used VARCHAR(20) DEFAULT NULL
) RETURNS VOID AS $$
BEGIN
    UPDATE download_queue
    SET status = 'completed',
        completed_at = NOW(),
        r2_key = p_r2_key,
        file_size_bytes = p_file_size,
        actual_source_used = COALESCE(p_source_used, source_type),
        error_message = NULL,
        updated_at = NOW()
    WHERE queue_id = p_queue_id;

    -- Also update the documents table if the EFTA exists there
    UPDATE documents
    SET r2_key = p_r2_key,
        file_size_bytes = COALESCE(file_size_bytes, p_file_size),
        updated_at = NOW()
    WHERE efta_number = (SELECT efta_number FROM download_queue WHERE queue_id = p_queue_id);
END;
$$ LANGUAGE plpgsql;


-- Mark a download as failed
CREATE OR REPLACE FUNCTION fail_download(
    p_queue_id BIGINT,
    p_error_message TEXT,
    p_max_retries INT DEFAULT 3
) RETURNS VOID AS $$
DECLARE
    v_retry_count INT;
BEGIN
    SELECT retry_count INTO v_retry_count
    FROM download_queue WHERE queue_id = p_queue_id;

    IF v_retry_count >= p_max_retries THEN
        -- Exceeded max retries, mark as skipped (permanent failure)
        UPDATE download_queue
        SET status = 'skipped',
            error_message = p_error_message,
            last_error_at = NOW(),
            claimed_by = NULL,
            claimed_at = NULL,
            updated_at = NOW()
        WHERE queue_id = p_queue_id;
    ELSE
        -- Mark as failed, eligible for retry
        UPDATE download_queue
        SET status = 'failed',
            error_message = p_error_message,
            retry_count = retry_count + 1,
            last_error_at = NOW(),
            claimed_by = NULL,
            claimed_at = NULL,
            updated_at = NOW()
        WHERE queue_id = p_queue_id;
    END IF;
END;
$$ LANGUAGE plpgsql;


-- Reset failed downloads to pending (for retry)
CREATE OR REPLACE FUNCTION reset_failed_for_retry(
    p_dataset INT,
    p_max_retry_count INT DEFAULT 3
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE download_queue
    SET status = 'pending',
        error_message = NULL,
        claimed_by = NULL,
        claimed_at = NULL,
        updated_at = NOW()
    WHERE status = 'failed'
      AND dataset_number = p_dataset
      AND retry_count < p_max_retry_count;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- Reset stale claims (crashed workers) back to pending
CREATE OR REPLACE FUNCTION reclaim_stale_downloads(
    p_timeout_minutes INT DEFAULT 30
) RETURNS INT AS $$
DECLARE
    v_count INT;
BEGIN
    UPDATE download_queue
    SET status = 'pending',
        claimed_by = NULL,
        claimed_at = NULL,
        updated_at = NOW()
    WHERE status = 'claimed'
      AND claimed_at < NOW() - (p_timeout_minutes || ' minutes')::INTERVAL;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- VIEWS
-- ============================================

-- Progress summary by dataset
CREATE OR REPLACE VIEW download_progress AS
SELECT
    dataset_number,
    COUNT(*) FILTER (WHERE status = 'pending') as pending,
    COUNT(*) FILTER (WHERE status = 'claimed') as in_progress,
    COUNT(*) FILTER (WHERE status = 'completed') as completed,
    COUNT(*) FILTER (WHERE status = 'failed') as failed,
    COUNT(*) FILTER (WHERE status = 'skipped') as skipped,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'completed') / NULLIF(COUNT(*), 0), 1) as pct_complete,
    COALESCE(SUM(file_size_bytes) FILTER (WHERE status = 'completed'), 0) / (1024*1024*1024.0) as gb_transferred
FROM download_queue
GROUP BY dataset_number
ORDER BY dataset_number;


-- Active workers view
CREATE OR REPLACE VIEW active_download_workers AS
SELECT
    claimed_by as worker_id,
    dataset_number,
    COUNT(*) as items_claimed,
    MIN(claimed_at) as oldest_claim,
    MAX(claimed_at) as newest_claim,
    EXTRACT(EPOCH FROM (NOW() - MIN(claimed_at)))/60 as minutes_since_oldest
FROM download_queue
WHERE status = 'claimed'
GROUP BY claimed_by, dataset_number
ORDER BY dataset_number, oldest_claim;


-- Recent errors view
CREATE OR REPLACE VIEW recent_download_errors AS
SELECT
    efta_number,
    dataset_number,
    error_message,
    retry_count,
    last_error_at,
    status
FROM download_queue
WHERE status IN ('failed', 'skipped')
  AND last_error_at IS NOT NULL
ORDER BY last_error_at DESC
LIMIT 100;


-- Source effectiveness (which sources are working)
CREATE OR REPLACE VIEW download_source_stats AS
SELECT
    dataset_number,
    actual_source_used as source,
    COUNT(*) as completed_count,
    SUM(file_size_bytes) / (1024*1024*1024.0) as gb_transferred
FROM download_queue
WHERE status = 'completed' AND actual_source_used IS NOT NULL
GROUP BY dataset_number, actual_source_used
ORDER BY dataset_number, completed_count DESC;
