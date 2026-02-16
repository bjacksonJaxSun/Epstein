-- Migration: Add User Authentication Tables
-- Run this script on the PostgreSQL database to create auth tables

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    last_login_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username);
CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email);

-- Roles table
CREATE TABLE IF NOT EXISTS roles (
    role_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(500),
    tier_level INTEGER NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ix_roles_name ON roles (name);

-- Seed default roles
INSERT INTO roles (role_id, name, description, tier_level)
VALUES
    (1, 'freemium', 'Access to sample/limited data only', 0),
    (2, 'basic', 'Access to images, people, documents, etc.', 1),
    (3, 'premium', 'Access to AI chat and deeper analysis features', 2),
    (4, 'admin', 'System administrator with full access', 3)
ON CONFLICT (role_id) DO NOTHING;

-- User-Role junction table
CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(role_id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id)
);

-- Refresh tokens table
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ,
    replaced_by_token_id BIGINT REFERENCES refresh_tokens(token_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_refresh_tokens_token_hash ON refresh_tokens (token_hash);

-- Reset sequence for roles to avoid conflicts
SELECT setval('roles_role_id_seq', (SELECT MAX(role_id) FROM roles));
