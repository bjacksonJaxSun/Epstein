-- Migration: Add worker_code table for database-based code distribution
-- Workers that can't use git pull receive code updates via PostgreSQL instead.
-- Server (BobbyHomeEP) publishes managed files on startup; clients pull when behind.

-- ============================================
-- WORKER CODE TABLE
-- Stores deployable file sets with version hashing
-- ============================================

CREATE TABLE IF NOT EXISTS worker_code (
    version_id    SERIAL PRIMARY KEY,
    version_hash  VARCHAR(64) UNIQUE NOT NULL,  -- SHA256 of all files combined
    files         JSONB NOT NULL,                -- { "relative/path.py": "file contents", ... }
    published_by  VARCHAR(100),                  -- hostname of machine that published
    published_at  TIMESTAMPTZ DEFAULT NOW(),
    notes         TEXT                           -- optional release notes
);

CREATE INDEX IF NOT EXISTS idx_wc_published_at ON worker_code(published_at DESC);

-- ============================================
-- FUNCTIONS
-- ============================================

-- Publish a new code version (no-op if hash already exists)
CREATE OR REPLACE FUNCTION publish_worker_code(
    p_version_hash VARCHAR(64),
    p_files JSONB,
    p_published_by VARCHAR(100) DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
) RETURNS BOOLEAN AS $$
DECLARE
    v_count INT;
BEGIN
    INSERT INTO worker_code (version_hash, files, published_by, notes)
    VALUES (p_version_hash, p_files, p_published_by, p_notes)
    ON CONFLICT (version_hash) DO NOTHING;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$$ LANGUAGE plpgsql;


-- Get the latest version hash
CREATE OR REPLACE FUNCTION get_latest_worker_version()
RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN (
        SELECT version_hash
        FROM worker_code
        ORDER BY version_id DESC
        LIMIT 1
    );
END;
$$ LANGUAGE plpgsql;


-- Get the files JSONB for a specific version
CREATE OR REPLACE FUNCTION get_worker_code(
    p_version_hash VARCHAR(64)
) RETURNS JSONB AS $$
BEGIN
    RETURN (
        SELECT files
        FROM worker_code
        WHERE version_hash = p_version_hash
    );
END;
$$ LANGUAGE plpgsql;


-- ============================================
-- VIEWS
-- ============================================

-- Helper function for file count (used by view)
CREATE OR REPLACE FUNCTION jsonb_object_keys_count(j JSONB)
RETURNS INT AS $$
BEGIN
    RETURN (SELECT COUNT(*) FROM jsonb_object_keys(j));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Recent code versions
CREATE OR REPLACE VIEW worker_code_history AS
SELECT
    version_id,
    version_hash,
    published_by,
    published_at,
    notes,
    jsonb_object_keys_count(files) as file_count
FROM worker_code
ORDER BY version_id DESC
LIMIT 20;
