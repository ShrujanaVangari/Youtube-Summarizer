"""
YouTube Transcript Service
Extracts transcript text and metadata from YouTube videos.

Fetch strategy (in order):
  1. youtube-transcript-api  — works in dev / non-blocked environments
  2. Supadata API             — reliable paid service with free tier (set SUPADATA_API_KEY)
  3. Invidious public API     — open-source YT frontend; free but occasionally unreliable
"""

import os
import re
import random
import urllib.request
import json
import requests
from youtube_transcript_api import YouTubeTranscriptApi


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.protokolla.fi",
    "https://invidious.perennialte.ch",
    "https://invidious.darkness.services",
    "https://yt.dragontar.net",
    "https://invidious.reallyaweso.me",
    "https://invidious.privacyredirect.com",
]


# ---------------------------------------------------------------------------
# Caption content parsers
# ---------------------------------------------------------------------------

def _parse_vtt(text):
    """Extract plain text from WebVTT data."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if (not line
                or line.startswith("WEBVTT")
                or line.startswith("NOTE")
                or "-->" in line
                or re.match(r"^\d+$", line)):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        if line:
            lines.append(line)
    return " ".join(lines)


def _parse_xml_captions(text):
    """Extract plain text from YouTube TTML/XML caption data."""
    fragments = re.findall(r"<(?:p|text)[^>]*>(.*?)</(?:p|text)>", text, re.DOTALL)
    if not fragments:
        fragments = [re.sub(r"<[^>]+>", " ", text)]
    cleaned = [re.sub(r"<[^>]+>", "", f).strip() for f in fragments]
    return " ".join(c for c in cleaned if c)


def _parse_caption_body(content, content_type=""):
    ct = content_type.lower()
    if "xml" in ct or "ttml" in ct or content.lstrip().startswith("<"):
        text = _parse_xml_captions(content)
    else:
        text = _parse_vtt(content)
    return " ".join(text.split())


# ---------------------------------------------------------------------------
# Strategy 1: youtube-transcript-api (works locally / non-blocked servers)
# ---------------------------------------------------------------------------

def _build_session():
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
    """Returns (raw_items | None, last_exception | None)."""
    session = _build_session()
    transcript_api = YouTubeTranscriptApi(http_client=session)
    raw_items = None
    last_error = None

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

    if raw_items is None and hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(video_id)
            print("[YTA] OK via legacy get_transcript()")
        except Exception as e:
            last_error = last_error or e
            print(f"[YTA Legacy Error] {type(e).__name__}: {e}")

    return raw_items, last_error


def _items_to_text(raw_items):
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
# Strategy 2: Supadata API (reliable, free tier 100 req/month)
#   Sign up at https://supadata.ai — add SUPADATA_API_KEY to env vars
# ---------------------------------------------------------------------------

def _fetch_via_supadata(video_id):
    """Returns (transcript_text | None, error_message | None)."""
    api_key = os.getenv("SUPADATA_API_KEY", "").strip()
    if not api_key:
        return None, "SUPADATA_API_KEY not configured"

    try:
        url = "https://api.supadata.ai/v1/youtube/transcript"
        params = {
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "text": "true",
        }
        headers = {"x-api-key": api_key}
        r = requests.get(url, params=params, headers=headers, timeout=20)

        if r.status_code == 200:
            data = r.json()
            # Response: {"content": "full text...", "lang": "en", ...}
            content = data.get("content", "")
            if content:
                print(f"[Supadata] OK — lang: {data.get('lang', '?')}")
                return " ".join(content.split()), None
            return None, "Supadata returned an empty transcript"

        if r.status_code == 404:
            return None, "This video does not have any captions or subtitles enabled."

        print(f"[Supadata] Error {r.status_code}: {r.text[:200]}")
        return None, f"Supadata API error ({r.status_code})"

    except Exception as e:
        print(f"[Supadata] Exception: {type(e).__name__}: {e}")
        return None, f"Supadata request failed: {type(e).__name__}"


# ---------------------------------------------------------------------------
# Strategy 3: Invidious public API (free, no key, less reliable)
# ---------------------------------------------------------------------------

def _fetch_via_invidious(video_id):
    """Returns (transcript_text | None, error_message | None)."""
    instances = random.sample(INVIDIOUS_INSTANCES, len(INVIDIOUS_INSTANCES))

    for instance in instances:
        try:
            # Step 1: get caption list
            list_url = f"{instance}/api/v1/captions/{video_id}"
            r = requests.get(list_url, timeout=10,
                             headers={"Accept": "application/json"})

            if r.status_code != 200:
                print(f"[Invidious] {instance} list → {r.status_code}")
                continue

            # Some instances return HTML — detect and skip
            ct = r.headers.get("Content-Type", "")
            if "html" in ct:
                print(f"[Invidious] {instance} returned HTML (bot check), skipping")
                continue

            data = r.json()
            tracks = data.get("captions", [])
            if not tracks:
                print(f"[Invidious] {instance} — no captions for {video_id}")
                return None, "This video does not have any captions or subtitles enabled."

            # Invidious uses camelCase: languageCode (not language_code)
            preferred = ["en", "en-US", "en-GB"]
            target = None
            for lang in preferred:
                target = next(
                    (t for t in tracks if t.get("languageCode", t.get("language_code", "")).startswith(lang[:2])),
                    None,
                )
                if target:
                    break
            if not target:
                target = tracks[0]

            print(f"[Invidious] {instance} — track: '{target.get('label', '?')}'")

            # Step 2: fetch caption content
            cap_url = target.get("url", "")
            if cap_url.startswith("/"):
                cap_url = instance + cap_url

            cr = requests.get(cap_url, timeout=15)
            if cr.status_code != 200:
                print(f"[Invidious] {instance} caption body → {cr.status_code}")
                continue

            cap_ct = cr.headers.get("Content-Type", "")
            if "html" in cap_ct:
                print(f"[Invidious] {instance} caption body is HTML, skipping")
                continue

            text = _parse_caption_body(cr.text, cap_ct)
            if text:
                print(f"[Invidious] OK from {instance}")
                return text, None

            print(f"[Invidious] {instance} — empty caption body")

        except Exception as e:
            print(f"[Invidious] {instance} error: {type(e).__name__}: {e}")
            continue

    return None, (
        "Could not retrieve transcript from any Invidious instance. "
        "Consider adding a SUPADATA_API_KEY environment variable for reliable transcripts."
    )


# ---------------------------------------------------------------------------
# Video title helper
# ---------------------------------------------------------------------------

def get_video_title(video_id):
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
# Error classifier
# ---------------------------------------------------------------------------

_CONTENT_ERRORS = frozenset({"TranscriptsDisabled", "NoTranscriptFound", "VideoUnavailable"})


def _friendly_error(error):
    if error is None:
        return "This video does not have any captions or subtitles enabled."
    name = type(error).__name__
    if name in ("IpBlocked", "RequestBlocked"):
        return (
            "YouTube is blocking transcript requests from this server's IP. "
            "Add a SUPADATA_API_KEY environment variable to fix this — "
            "free tier available at https://supadata.ai"
        )
    if name == "TranscriptsDisabled":
        return "Captions are disabled for this video."
    if name == "NoTranscriptFound":
        return "No transcript found for this video in any supported language."
    if name == "VideoUnavailable":
        return "This video is unavailable (private, deleted, or region-locked)."
    if name == "TooManyRequests":
        return "Too many requests to YouTube. Please wait a moment and try again."
    return f"Unable to fetch transcript ({name}): {str(error)[:200]}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_transcript(video_id):
    """
    Extract transcript for a YouTube video using a multi-strategy waterfall:
      1. youtube-transcript-api (fast, dev-friendly)
      2. Supadata API           (reliable server-side, needs SUPADATA_API_KEY)
      3. Invidious API          (free, no key, less reliable)
    """
    title = get_video_title(video_id)

    # ── Strategy 1: youtube-transcript-api ───────────────────────────────
    raw_items, yta_error = _fetch_via_yta(video_id)
    if raw_items is not None:
        text = _items_to_text(raw_items)
        if text:
            return {"success": True, "title": title, "transcript_text": text}

    # Content errors (no captions) — no point trying other strategies
    if yta_error is not None and type(yta_error).__name__ in _CONTENT_ERRORS:
        return {"success": False, "error": _friendly_error(yta_error)}

    print(f"[Transcript] YTA failed ({type(yta_error).__name__ if yta_error else 'empty'}), "
          "trying Supadata …")

    # ── Strategy 2: Supadata API ─────────────────────────────────────────
    sup_text, sup_error = _fetch_via_supadata(video_id)
    if sup_text:
        return {"success": True, "title": title, "transcript_text": sup_text}

    # If Supadata says no captions, stop here
    if sup_error and "captions" in sup_error.lower():
        return {"success": False, "error": sup_error}

    print(f"[Transcript] Supadata failed ({sup_error}), trying Invidious …")

    # ── Strategy 3: Invidious API ─────────────────────────────────────────
    inv_text, inv_error = _fetch_via_invidious(video_id)
    if inv_text:
        return {"success": True, "title": title, "transcript_text": inv_text}

    # ── All strategies exhausted ──────────────────────────────────────────
    # Return the most useful error message
    if "captions" in (inv_error or "").lower():
        return {"success": False, "error": inv_error}

    return {"success": False, "error": _friendly_error(yta_error)}
