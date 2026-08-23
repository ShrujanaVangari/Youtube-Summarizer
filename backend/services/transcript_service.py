"""
YouTube Transcript Service
Extracts video transcript text and metadata using youtube-transcript-api and YouTube oEmbed API.
Supports multi-language auto-fallback (English, Telugu, Hindi, Spanish, etc.)
"""

import urllib.request
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi


def _caption_error(error):
    error_name = type(error).__name__
    blocked_errors = {'IpBlocked', 'RequestBlocked', 'YouTubeRequestFailed'}

    if error_name in blocked_errors:
        return (
            "YouTube is blocking caption requests from this server. "
            "Please try again later or configure a transcript proxy."
        )

    return "Unable to fetch captions from YouTube right now. Please check the URL and try again."

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
        raw_items = None

        # youtube-transcript-api 1.x requires an instance and returns transcript
        # snippets with a text attribute. Select a non-English track when needed.
        http_client = requests.Session()
        http_client.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 Chrome/131.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        })
        transcript_api = YouTubeTranscriptApi(http_client=http_client)

        if hasattr(transcript_api, 'list'):
            try:
                transcript_list = transcript_api.list(video_id)
                try:
                    transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except Exception:
                    transcript = next(iter(transcript_list), None)

                if transcript is not None:
                    raw_items = transcript.fetch()
            except Exception as list_error:
                print(f"[Transcript List Error] {type(list_error).__name__}: {list_error}")

        if raw_items is None and hasattr(transcript_api, 'fetch'):
            try:
                raw_items = transcript_api.fetch(
                    video_id,
                    languages=['en', 'en-US', 'en-GB']
                )
            except Exception as fetch_error:
                print(f"[Transcript Fetch Error] {type(fetch_error).__name__}: {fetch_error}")

        if raw_items is None and hasattr(YouTubeTranscriptApi, 'get_transcript'):
            # Compatibility with youtube-transcript-api versions before 1.0.
            raw_items = YouTubeTranscriptApi.get_transcript(video_id)

        if raw_items is None:
            return {
                "success": False,
                "error": "This video does not have any captions or subtitles enabled."
            }

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
        print(f"[Transcript Error] {type(e).__name__}: {e}")
        return {
            "success": False,
            "error": _caption_error(e)
        }
