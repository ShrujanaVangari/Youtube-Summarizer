"""
YouTube Transcript Service
Extracts video transcript text and metadata using youtube-transcript-api and YouTube oEmbed API.
Supports multi-language auto-fallback (English, Telugu, Hindi, Spanish, etc.)
Supports TRANSCRIPT_PROXY_URLS env var (comma-separated direct proxy IPs) to bypass YouTube IP blocks.
"""

import os
import random
import urllib.request
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi


def _get_proxy_list():
    """Returns the list of configured proxy URLs (from TRANSCRIPT_PROXY_URLS env var)."""
    raw = os.getenv('TRANSCRIPT_PROXY_URLS', os.getenv('TRANSCRIPT_PROXY_URL', ''))
    return [p.strip() for p in raw.split(',') if p.strip()]


def _caption_error(error, proxy_configured=False):
    """Map youtube-transcript-api exceptions to human-readable messages."""
    error_name = type(error).__name__

    # --- IP / request blocked ---
    if error_name in ('IpBlocked', 'RequestBlocked'):
        if proxy_configured:
            return (
                "YouTube is blocking caption requests even through the configured proxy. "
                "Please try a different proxy or try again later."
            )
        return (
            "YouTube is blocking caption requests from this server. "
            "Set the TRANSCRIPT_PROXY_URLS environment variable to route requests through a proxy."
        )

    # --- YouTube request failed (network / parse error) ---
    if error_name == 'YouTubeRequestFailed':
        return f"YouTube returned an unexpected response: {error}. Please try again later."

    # --- Captions explicitly disabled on this video ---
    if error_name == 'TranscriptsDisabled':
        return "Captions are disabled for this video. The creator has turned off subtitles."

    # --- No transcript in any of the requested languages ---
    if error_name == 'NoTranscriptFound':
        return (
            "No transcript was found for this video in any supported language. "
            "The video may not have captions available."
        )

    # --- Video is unavailable / private / deleted ---
    if error_name == 'VideoUnavailable':
        return "This video is unavailable (it may be private, deleted, or region-locked)."

    # --- Too many requests ---
    if error_name == 'TooManyRequests':
        return "Too many requests to YouTube. Please wait a moment and try again."

    # --- Proxy / network errors from requests library ---
    if error_name in ('ProxyError', 'ConnectionError', 'SSLError', 'Timeout', 'ReadTimeout'):
        return (
            f"Could not connect to YouTube through the proxy ({error_name}). "
            "Please check your TRANSCRIPT_PROXY_URLS configuration."
        )

    # --- Catch-all: surface the real exception so it's diagnosable ---
    return (
        f"Unable to fetch transcript ({error_name}): {str(error)[:200]}. "
        "Please check the server logs for details."
    )


# ---------------------------------------------------------------------------
# Video title helper
# ---------------------------------------------------------------------------

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


def _build_session(proxy_url=None):
    """Build a requests.Session with browser headers and optional proxy."""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 Chrome/131.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9'
    })
    if proxy_url:
        session.proxies.update({'http': proxy_url, 'https': proxy_url})
        display = proxy_url.split('@')[-1].rstrip('/')
        print(f"[Transcript] Using proxy: {display}")
    return session


def _fetch_raw_items(video_id, session):
    """
    Tries all available fetch strategies for a given session.
    Returns (raw_items, last_error).
    """
    transcript_api = YouTubeTranscriptApi(http_client=session)
    raw_items = None
    last_error = None

    # Strategy 1: list() API (>= 0.6)
    if hasattr(transcript_api, 'list'):
        try:
            transcript_list = transcript_api.list(video_id)
            try:
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except Exception:
                transcript = next(iter(transcript_list), None)
            if transcript is not None:
                raw_items = transcript.fetch()
                print(f"[Transcript] OK via list() — lang: {getattr(transcript, 'language_code', '?')}")
        except Exception as e:
            last_error = e
            print(f"[Transcript List Error] {type(e).__name__}: {e}")

    # Strategy 2: fetch() with language list
    if raw_items is None and hasattr(transcript_api, 'fetch'):
        try:
            raw_items = transcript_api.fetch(
                video_id,
                languages=['en', 'en-US', 'en-GB', 'hi', 'te', 'ta', 'kn', 'ml', 'bn', 'es', 'fr', 'de', 'pt', 'ja']
            )
            print("[Transcript] OK via fetch() fallback")
        except Exception as e:
            last_error = e
            print(f"[Transcript Fetch Error] {type(e).__name__}: {e}")

    # Strategy 3: legacy get_transcript()
    if raw_items is None and hasattr(YouTubeTranscriptApi, 'get_transcript'):
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(video_id)
            print("[Transcript] OK via legacy get_transcript()")
        except Exception as e:
            last_error = last_error or e
            print(f"[Transcript Legacy Error] {type(e).__name__}: {e}")

    return raw_items, last_error


def extract_transcript(video_id):
    """
    Extracts and concatenates transcript text from a YouTube video.
    Randomly picks a proxy from TRANSCRIPT_PROXY_URLS and retries with
    a different one on proxy errors.
    """
    title = get_video_title(video_id)
    proxy_list = _get_proxy_list()

    # Build a shuffled attempt order: [random proxy, ...remaining proxies..., no proxy]
    proxies_to_try = random.sample(proxy_list, len(proxy_list)) if proxy_list else []
    proxies_to_try.append(None)  # final fallback: direct connection

    last_error = None

    for proxy_url in proxies_to_try:
        try:
            session = _build_session(proxy_url)
            raw_items, fetch_error = _fetch_raw_items(video_id, session)

            if raw_items is None:
                if fetch_error is not None:
                    raise fetch_error
                return {
                    "success": False,
                    "error": "This video does not have any captions or subtitles enabled."
                }

            # Extract clean text
            fragments = []
            for item in raw_items:
                if isinstance(item, dict):
                    fragments.append(item.get('text', ''))
                elif hasattr(item, 'text'):
                    fragments.append(item.text)
                else:
                    fragments.append(str(item))

            full_text = " ".join(" ".join(fragments).split())

            if not full_text:
                return {
                    "success": False,
                    "error": "This video does not have any captions or subtitles enabled."
                }

            return {"success": True, "title": title, "transcript_text": full_text}

        except Exception as e:
            last_error = e
            err_name = type(e).__name__
            print(f"[Transcript Error] proxy={proxy_url.split('@')[-1] if proxy_url else 'direct'} "
                  f"{err_name}: {e}")
            # Only retry on proxy-related errors; content errors are final
            if err_name not in ('ProxyError', 'ConnectionError', 'SSLError', 'Timeout', 'ReadTimeout'):
                break

    print(f"[Transcript] All attempts exhausted. Last error: {type(last_error).__name__}")
    return {
        "success": False,
        "error": _caption_error(last_error, proxy_configured=bool(proxy_list))
    }
