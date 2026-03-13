-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================================
-- Table: channels
-- ============================================================
CREATE TABLE channels (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_id      bigint      UNIQUE NOT NULL,
    username         text,
    title            text        NOT NULL,
    category         text,
    is_active        boolean     DEFAULT true,
    last_scraped_at  timestamptz,
    created_at       timestamptz DEFAULT now()
);

-- ============================================================
-- Table: posts
-- ============================================================
CREATE TABLE posts (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id       uuid        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    telegram_msg_id  integer     NOT NULL,
    text             text,
    date             timestamptz NOT NULL,
    views            integer,
    forwards         integer,
    reactions_json   jsonb,
    has_media        boolean     DEFAULT false,
    media_type       text,
    link             text,
    embedding        vector(1024),
    created_at       timestamptz DEFAULT now(),
    UNIQUE (channel_id, telegram_msg_id)
);

-- ============================================================
-- Table: comments
-- ============================================================
CREATE TABLE comments (
    id                   uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id              uuid        NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    telegram_msg_id      integer     NOT NULL,
    sender_name          text,
    sender_id            bigint,
    text                 text,
    date                 timestamptz NOT NULL,
    is_reply             boolean     DEFAULT false,
    reply_to_comment_id  uuid        REFERENCES comments(id),
    embedding            vector(1024),
    created_at           timestamptz DEFAULT now()
);

-- ============================================================
-- Table: channel_summaries
-- ============================================================
CREATE TABLE channel_summaries (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id        uuid        NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    period_type       text        NOT NULL CHECK (period_type IN ('week','month','quarter','half_year','year','custom')),
    period_start      timestamptz NOT NULL,
    period_end        timestamptz NOT NULL,
    summary           text,
    facts_json        jsonb,
    post_count        integer,
    status            text        DEFAULT 'pending' CHECK (status IN ('pending','processing','done','error')),
    parent_summary_id uuid        REFERENCES channel_summaries(id),
    model_used        text,
    tokens_used       integer,
    created_at        timestamptz DEFAULT now()
);

-- ============================================================
-- Table: digests
-- ============================================================
CREATE TABLE digests (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start timestamptz NOT NULL,
    period_end   timestamptz NOT NULL,
    digest_type  text        NOT NULL CHECK (digest_type IN ('headlines','brief','deep','qa','actions')),
    summary      text,
    facts_json   jsonb,
    model_used   text,
    tokens_used  integer,
    created_at   timestamptz DEFAULT now()
);

-- ============================================================
-- Table: digest_posts
-- ============================================================
CREATE TABLE digest_posts (
    digest_id uuid NOT NULL REFERENCES digests(id) ON DELETE CASCADE,
    post_id   uuid NOT NULL REFERENCES posts(id)   ON DELETE CASCADE,
    PRIMARY KEY (digest_id, post_id)
);

-- ============================================================
-- Table: search_history
-- ============================================================
CREATE TABLE search_history (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    query          text        NOT NULL,
    results_json   jsonb,
    ai_synthesis   text,
    created_at     timestamptz DEFAULT now()
);

-- ============================================================
-- Indexes
-- ============================================================

-- Full-text search (Russian config) on posts.text and comments.text
CREATE INDEX idx_posts_text_fts
    ON posts USING GIN (to_tsvector('russian', coalesce(text, '')));

CREATE INDEX idx_comments_text_fts
    ON comments USING GIN (to_tsvector('russian', coalesce(text, '')));

-- HNSW vector indexes for cosine similarity search
CREATE INDEX idx_posts_embedding_hnsw
    ON posts USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_comments_embedding_hnsw
    ON comments USING hnsw (embedding vector_cosine_ops);

-- B-tree indexes
CREATE INDEX idx_posts_channel_date
    ON posts (channel_id, date DESC);

CREATE INDEX idx_posts_date
    ON posts (date DESC);

CREATE INDEX idx_comments_post_id
    ON comments (post_id);

CREATE INDEX idx_channel_summaries_lookup
    ON channel_summaries (channel_id, period_type, period_start);

CREATE INDEX idx_digests_period_start
    ON digests (period_start DESC);
