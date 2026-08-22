"""
YouTube Transcript Service
Extracts video transcript text and metadata using youtube-transcript-api and YouTube oEmbed API.
Supports multi-language auto-fallback (English, Telugu, Hindi, Spanish, etc.)
"""

import urllib.request
import json
from youtube_transcript_api import YouTubeTranscriptApi

def get_video_title(video_id):
    """
    Fetches public video title via YouTube oEmbed API without requiring API keys.
    """
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get('title', f"YouTube Video ({video_id})")
    except Exception as e:
        print(f"[Warning] Could not fetch oEmbed title for {video_id}: {e}")
    
    return f"YouTube Video ({video_id})"

def extract_transcript(video_id):
    """
    Extracts and concatenates transcript text from a YouTube video.
    Tries English first, and automatically falls back to any available language track if English isn't found.
    """
    title = get_video_title(video_id)

    try:
        raw_items = []

        # Attempt 1: Fetch via list() to inspect available language tracks
        try:
            if hasattr(YouTubeTranscriptApi, 'list') or hasattr(YouTubeTranscriptApi(), 'list'):
                ytt = YouTubeTranscriptApi() if hasattr(YouTubeTranscriptApi, 'list') else YouTubeTranscriptApi
                transcript_list = ytt.list(video_id) if hasattr(ytt, 'list') else ytt.list_transcripts(video_id)
                
                # Check for English or fallback to first available language track
                try:
                    t = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except Exception:
                    # Pick the first available transcript (e.g. te, hi, es, fr)
                    t = next(iter(transcript_list))
                    
                raw_items = t.fetch()
        except Exception as e1:
            print(f"[Transcript Fallback 1]: {e1}")

        # Attempt 2: Fallback to direct fetch/get_transcript
        if not raw_items:
            try:
                if hasattr(YouTubeTranscriptApi, 'fetch'):
                    raw_items = YouTubeTranscriptApi().fetch(video_id)
                elif hasattr(YouTubeTranscriptApi, 'get_transcript'):
                    raw_items = YouTubeTranscriptApi.get_transcript(video_id)
            except Exception as e2:
                print(f"[Transcript Fallback 2]: {e2}")

        # Extract clean text from fetched items
        fragments = []
        for item in raw_items:
            if isinstance(item, dict):
                fragments.append(item.get('text', ''))
            elif hasattr(item, 'text'):
                fragments.append(item.text)
            else:
                fragments.append(str(item))

        full_text = " ".join(fragments)
        full_text = " ".join(full_text.split())

        if not full_text:
            return {
                "success": False,
                "error": "This video does not have any captions or subtitles enabled."
            }

        return {
            "success": True,
            "title": title,
            "transcript_text": full_text
        }

    except Exception as e:
        print(f"[Transcript Error] {str(e)}")
        return {
            "success": False,
            "error": "No subtitles/transcripts found for this YouTube video."
        }
