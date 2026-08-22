-- PostgreSQL Schema for YouTube AI Summarizer
-- Compatible with Neon PostgreSQL

-- Drop table if it exists (for clean resets during development)
DROP TABLE IF EXISTS summaries;

-- Create summaries table
CREATE TABLE summaries (
    id SERIAL PRIMARY KEY,
    youtube_url VARCHAR(500) NOT NULL,
    video_id VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    key_points JSONB NOT NULL,
    summary_length VARCHAR(20) NOT NULL DEFAULT 'medium',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index on video_id for faster lookup of existing summaries
CREATE INDEX idx_summaries_video_id ON summaries(video_id);
