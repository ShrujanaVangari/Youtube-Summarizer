"""
YouTube Transcript Service
Extracts transcript text and metadata from YouTube videos.

Strategy (in order):
  1. youtube-transcript-api (works in dev / unblocked environments)
  2. Invidious public API (free, no key, bypasses datacenter IP blocks on Render etc.)
"""

import os
import re
import random
import urllib.request
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi


# ---------------------------------------------------------------------------
# Invidious public instances (shuffled per-request for load spreading)
# ---------------------------------------------------------------------------

INVIDIOUS_INSTANCES = [
    "https://invidious.fdn.fr",
    "https://inv.nadeko.net",
    "https://invidious.privacydev.net",
    "https://invidious.nikkosphere.com",
    "https://iv.datura.network",
    "https://invidious.darkness.services",
]


# ---------------------------------------------------------------------------
# Caption text parsers
# ---------------------------------------------------------------------------

def _parse_vtt(text):
    """Extract plain text from WebVTT caption data."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        # Skip headers, timestamps, and blank lines
        if (not line
                or line.startswith("WEBVTT")
                or "-->" in line
                or re.match(r"^\d+$", line)):
            continue
        # Strip inline tags like <c>, <b>, etc.
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            lines.append(line)
    return " ".join(lines)


def _parse_xml_captions(text):
    """Extract plain text from YouTube TTML/XML caption data."""
    # Match <p ...>text</p> or <text ...>text</text>
    fragments = re.findall(r'<(?:p|text)[^>]*>(.*?)</(?:p|text)>', text, re.DOTALL)
    if not fragments:
        # Fallback: strip all XML tags
        fragments = [re.sub(r"<[^>]+>", " ", text)]
    cleaned = [re.sub(r"<[^>]+>", "", f).strip() for f in fragments]
    return " ".join(c for c in cleaned if c)


def _parse_caption_body(content, content_type=""):
    """Auto-detect format and parse caption body into plain text."""
    ct = content_type.lower()
    if "xml" in ct or "ttml" in ct or content.lstrip().startswith("<"):
        text = _parse_xml_captions(content)
    else:
        text = _parse_vtt(content)
    # Normalise whitespace
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Invidious-based transcript fetcher
# ---------------------------------------------------------------------------

def _fetch_via_invidious(video_id):
    """
    Fetch transcript from a public Invidious instance.
    Returns (transcript_text, error_message).
    """
    instances = random.sample(INVIDIOUS_INSTANCES, len(INVIDIOUS_INSTANCES))

    for instance in instances:
        try:
            # Step 1: get the captions list for this video
            list_url = f"{instance}/api/v1/captions/{video_id}"
            r = requests.get(list_url, timeout=10)
            if r.status_code != 200:
                print(f"[Invidious] {instance} captions list → {r.status_code}")
                continue

            data = r.json()
            tracks = data.get("captions", [])
            if not tracks:
                print(f"[Invidious] {instance} has no captions for {video_id}")
                # Don't try other instances — no captions is a video-level fact
                return None, "This video does not have any captions or subtitles enabled."

            # Prefer English; fall back to first track
            preferred_langs = ["en", "en-US", "en-GB"]
            target = None
            for lang in preferred_langs:
                target = next((t for t in tracks if t.get("language_code", "").startswith(lang[:2])), None)
                if target:
                    break
            if not target:
                target = tracks[0]

            print(f"[Invidious] {instance} → using track '{target.get('label', '?')}'")

            # Step 2: fetch the actual caption content
            cap_url = target.get("url", "")
            if cap_url.startswith("/"):
                cap_url = instance + cap_url

            cr = requests.get(cap_url, timeout=15)
            if cr.status_code != 200:
                print(f"[Invidious] {instance} caption fetch → {cr.status_code}")
                continue

            content_type = cr.headers.get("Content-Type", "")
            text = _parse_caption_body(cr.text, content_type)

            if text:
                print(f"[Invidious] Successfully fetched transcript from {instance}")
                return text, None

            print(f"[Invidious] {instance} returned empty caption body")

        except Exception as e:
            print(f"[Invidious] {instance} error: {type(e).__name__}: {e}")
            continue

    return None, "Could not retrieve transcript from any Invidious instance. Please try again later."


# ---------------------------------------------------------------------------
# Primary youtube-transcript-api fetcher
# ---------------------------------------------------------------------------

def _build_session():
    """Build a requests.Session with browser-like headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session


def _fetch_via_yta(video_id):
    """
    Fetch transcript using youtube-transcript-api.
    Returns (raw_items_or_None, last_exception_or_None).
    """
    session = _build_session()
    transcript_api = YouTubeTranscriptApi(http_client=session)
    raw_items = None
    last_error = None

    # Strategy A: list() → find_transcript()
    if hasattr(transcript_api, "list"):
        try:
            tlist = transcript_api.list(video_id)
            try:
                transcript = tlist.find_transcript(["en", "en-US", "en-GB"])
            except Exception:
                transcript = next(iter(tlist), None)
            if transcript is not None:
                raw_items = transcript.fetch()
                print(f"[YTA] OK via list() — lang: {getattr(transcript, 'language_code', '?')}")
        except Exception as e:
            last_error = e
            print(f"[YTA List Error] {type(e).__name__}: {e}")

    # Strategy B: fetch() with language list
    if raw_items is None and hasattr(transcript_api, "fetch"):
        try:
            raw_items = transcript_api.fetch(
                video_id,
                languages=["en", "en-US", "en-GB", "hi", "te", "ta", "kn", "ml", "bn", "es", "fr", "de", "pt", "ja"],
            )
            print("[YTA] OK via fetch()")
        except Exception as e:
            last_error = e
            print(f"[YTA Fetch Error] {type(e).__name__}: {e}")

    # Strategy C: legacy get_transcript()
    if raw_items is None and hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(video_id)
            print("[YTA] OK via legacy get_transcript()")
        except Exception as e:
            last_error = last_error or e
            print(f"[YTA Legacy Error] {type(e).__name__}: {e}")

    return raw_items, last_error


def _items_to_text(raw_items):
    """Convert a list of transcript snippet objects/dicts to a clean string."""
    fragments = []
    for item in raw_items:
        if isinstance(item, dict):
            fragments.append(item.get("text", ""))
        elif hasattr(item, "text"):
            fragments.append(item.text)
        else:
            fragments.append(str(item))
    return " ".join(" ".join(fragments).split())


# ---------------------------------------------------------------------------
# Video title helper
# ---------------------------------------------------------------------------

def get_video_title(video_id):
    """Fetch public video title via YouTube oEmbed (no API key required)."""
    try:
        url = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                return data.get("title", f"YouTube Video ({video_id})")
    except Exception as e:
        print(f"[Warning] oEmbed title fetch failed for {video_id}: {e}")
    return f"YouTube Video ({video_id})"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# Error classes that indicate YouTube is blocking the request (not a content issue)
_BLOCK_ERRORS = frozenset({"IpBlocked", "RequestBlocked", "YouTubeRequestFailed"})


def extract_transcript(video_id):
    """
    Extract transcript for a YouTube video.

    1. Tries youtube-transcript-api (fast, works in dev).
    2. On any block/network error falls back to Invidious public API.
    """
    title = get_video_title(video_id)

    # ── Primary: youtube-transcript-api ──────────────────────────────────
    raw_items, yta_error = _fetch_via_yta(video_id)

    if raw_items is not None:
        text = _items_to_text(raw_items)
        if text:
            return {"success": True, "title": title, "transcript_text": text}

    # If the video simply has no captions, don't bother with Invidious
    if yta_error is not None:
        err_name = type(yta_error).__name__
        if err_name in ("TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable"):
            return {
                "success": False,
                "error": _friendly_error(yta_error),
            }

    # ── Fallback: Invidious API ───────────────────────────────────────────
    print(f"[Transcript] youtube-transcript-api failed ({type(yta_error).__name__ if yta_error else 'empty'}), "
          f"trying Invidious …")

    inv_text, inv_error = _fetch_via_invidious(video_id)
    if inv_text:
        return {"success": True, "title": title, "transcript_text": inv_text}

    # ── Both failed ───────────────────────────────────────────────────────
    error_msg = inv_error or _friendly_error(yta_error) if yta_error else (
        inv_error or "This video does not have any captions or subtitles enabled."
    )
    return {"success": False, "error": error_msg}


def _friendly_error(error):
    """Convert an exception into a user-facing message."""
    name = type(error).__name__

    if name in ("IpBlocked", "RequestBlocked"):
        return (
            "YouTube is blocking transcript requests from this server. "
            "The Invidious fallback also failed — please try again in a few minutes."
        )
    if name == "YouTubeRequestFailed":
        return f"YouTube returned an unexpected response. Please try again later."
    if name == "TranscriptsDisabled":
        return "Captions are disabled for this video. The creator has turned off subtitles."
    if name == "NoTranscriptFound":
        return "No transcript found for this video in any supported language."
    if name == "VideoUnavailable":
        return "This video is unavailable (private, deleted, or region-locked)."
    if name == "TooManyRequests":
        return "Too many requests to YouTube. Please wait a moment and try again."

    return f"Unable to fetch transcript ({name}): {str(error)[:200]}"
