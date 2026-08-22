# Database Setup - Neon PostgreSQL

This folder contains the database schema scripts and useful queries for the **YouTube AI Summarizer** project.

## Files
- `schema.sql`: Contains table structure and index definitions.
- `queries.sql`: Contains sample SQL statements for insertion, retrieval, and caching lookup.

## Neon Setup Instructions
1. Log in to your [Neon Console](https://console.neon.tech).
2. Create a new project or select an existing PostgreSQL database.
3. Open the **SQL Editor** tab in Neon.
4. Copy and paste the contents of `schema.sql` into the SQL Editor and click **Run**.
5. Copy your Neon PostgreSQL connection string (found in **Dashboard** -> **Connection Details**) and add it as `DATABASE_URL` in `backend/.env`.

## Database Schema Overview
- **Table:** `summaries`
  - `id` (`SERIAL PRIMARY KEY`): Unique identifier.
  - `youtube_url` (`VARCHAR(500)`): Full YouTube URL submitted by user.
  - `video_id` (`VARCHAR(100)`): Extracted 11-character YouTube video ID.
  - `title` (`VARCHAR(255)`): Video title.
  - `summary` (`TEXT`): Paragraph AI summary from Gemini.
  - `key_points` (`JSONB`): Structured list of key takeaways.
  - `created_at` (`TIMESTAMP WITH TIME ZONE`): Creation timestamp.
