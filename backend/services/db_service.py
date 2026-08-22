"""
Neon PostgreSQL & Database Service
Handles database connections, schema auto-initialization, caching checks, and summary persistence.
Includes automatic fallback to local SQLite DB if remote Neon DB is unreachable.
"""

import json
import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config

def is_postgres():
    return bool(Config.DATABASE_URL and Config.DATABASE_URL.startswith("postgresql"))

def get_connection():
    """
    Attempts PostgreSQL connection if DATABASE_URL is configured.
    If PostgreSQL connection fails (e.g. DNS/network issue), falls back seamlessly to local SQLite DB.
    """
    if is_postgres():
        try:
            db_url = Config.DATABASE_URL.replace("&channel_binding=require", "")
            conn = psycopg2.connect(db_url, connect_timeout=5)
            return conn, "postgres"
        except Exception as e:
            print(f"[DB Warning] Could not connect to Neon PostgreSQL ({e}). Falling back to local SQLite database.")
    
    # SQLite fallback
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    database_dir = os.path.join(project_root, "database")
    os.makedirs(database_dir, exist_ok=True)
    conn = sqlite3.connect(os.path.join(database_dir, "local_dev.db"))
    conn.row_factory = sqlite3.Row
    return conn, "sqlite"

def init_db():
    """
    Auto-initializes database tables.
    """
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        
        if db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id SERIAL PRIMARY KEY,
                    youtube_url VARCHAR(500) NOT NULL,
                    video_id VARCHAR(100) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    summary TEXT NOT NULL,
                    key_points JSONB NOT NULL,
                    summary_length VARCHAR(20) NOT NULL DEFAULT 'medium',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_summaries_video_id ON summaries(video_id);
                ALTER TABLE summaries ADD COLUMN IF NOT EXISTS summary_length VARCHAR(20) NOT NULL DEFAULT 'medium';
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    youtube_url TEXT NOT NULL,
                    video_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    key_points TEXT NOT NULL,
                    summary_length TEXT NOT NULL DEFAULT 'medium',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            try:
                cursor.execute("ALTER TABLE summaries ADD COLUMN summary_length TEXT NOT NULL DEFAULT 'medium'")
            except sqlite3.OperationalError as error:
                if "duplicate column name" not in str(error).lower():
                    raise
        
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[DB] Database initialized successfully using {db_type.upper()}.")
    except Exception as e:
        print(f"[DB Error] Database initialization error: {e}")

def get_summary_by_video_id(video_id, summary_length="medium"):
    """
    Look up existing summary by video_id (caching layer).
    """
    try:
        conn, db_type = get_connection()
        if db_type == "postgres":
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM summaries WHERE video_id = %s AND summary_length = %s ORDER BY created_at DESC LIMIT 1;", (video_id, summary_length))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                row = dict(row)
                if isinstance(row.get('key_points'), str):
                    row['key_points'] = json.loads(row['key_points'])
                return row
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM summaries WHERE video_id = ? AND summary_length = ? ORDER BY created_at DESC LIMIT 1;", (video_id, summary_length))
            row = cursor.fetchone()
            cursor.close()
            conn.close()
            if row:
                row_dict = dict(row)
                row_dict['key_points'] = json.loads(row_dict['key_points'])
                return row_dict
    except Exception as e:
        print(f"[DB Error] Error fetching cached summary: {e}")
    return None

def save_summary(youtube_url, video_id, title, summary, key_points, summary_length="medium"):
    """
    Persists summary record into database.
    """
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        
        key_points_json = json.dumps(key_points)

        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO summaries (youtube_url, video_id, title, summary, key_points, summary_length)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id, created_at;
            """, (youtube_url, video_id, title, summary, key_points_json, summary_length))
            result = cursor.fetchone()
            conn.commit()
            created_at = result[1].isoformat() if result else None
        else:
            cursor.execute("""
                INSERT INTO summaries (youtube_url, video_id, title, summary, key_points, summary_length)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (youtube_url, video_id, title, summary, key_points_json, summary_length))
            conn.commit()
            created_at = None

        cursor.close()
        conn.close()

        return {
            "youtube_url": youtube_url,
            "video_id": video_id,
            "title": title,
            "summary": summary,
            "key_points": key_points,
            "summary_length": summary_length,
            "created_at": created_at
        }
    except Exception as e:
        print(f"[DB Error] Error saving summary to database: {e}")
        return None

def fetch_all_summaries():
    """
    Retrieves all saved video summaries sorted by date (newest first).
    """
    summaries = []
    try:
        conn, db_type = get_connection()
        if db_type == "postgres":
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute("SELECT * FROM summaries ORDER BY created_at DESC LIMIT 50;")
            rows = cursor.fetchall()
            for r in rows:
                item = dict(r)
                if isinstance(item.get('key_points'), str):
                    item['key_points'] = json.loads(item['key_points'])
                if item.get('created_at'):
                    item['created_at'] = item['created_at'].isoformat()
                summaries.append(item)
            cursor.close()
        else:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM summaries ORDER BY created_at DESC LIMIT 50;")
            rows = cursor.fetchall()
            for r in rows:
                item = dict(r)
                item['key_points'] = json.loads(item['key_points'])
                summaries.append(item)
            cursor.close()
            
        conn.close()
    except Exception as e:
        print(f"[DB Error] Error fetching history summaries: {e}")

    return summaries
