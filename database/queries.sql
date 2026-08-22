-- Sample Useful Queries for YouTube AI Summarizer

-- 1. Insert a new summary into database
INSERT INTO summaries (youtube_url, video_id, title, summary, key_points)
VALUES (
    'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    'dQw4w9WgXcQ',
    'Sample Video Title',
    'This is a sample generated AI summary for testing purposes.',
    '["Key point 1: High engagement", "Key point 2: Summary overview", "Key point 3: Key takeaway"]'::jsonb
)
RETURNING id, created_at;

-- 2. Retrieve all saved summaries (newest first)
SELECT id, youtube_url, video_id, title, summary, key_points, created_at
FROM summaries
ORDER BY created_at DESC;

-- 3. Find summary by video ID (caching check)
SELECT id, youtube_url, video_id, title, summary, key_points, created_at
FROM summaries
WHERE video_id = 'dQw4w9WgXcQ'
LIMIT 1;

-- 4. Delete summary by ID
DELETE FROM summaries WHERE id = 1;
