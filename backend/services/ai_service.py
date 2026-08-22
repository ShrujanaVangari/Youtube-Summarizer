"""
Google Gemini AI & Smart NLP Summarization Engine
Powered by Google Gemini 3.5 Flash & 3.7 Flash models.
"""

import json
import urllib.request
import re
from config import Config

def smart_nlp_summary(transcript_text, video_title, summary_length="medium"):
    """
    Fallback local NLP summarizer.
    """
    raw_sentences = re.split(r'(?<=[.!?]) +', transcript_text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 30]

    if not sentences:
        sentences = [s.strip() for s in transcript_text.split('.') if len(s.strip()) > 20]

    total = len(sentences)
    sentence_count = {"short": 1, "medium": 3, "detailed": 6}.get(summary_length, 3)
    overview_text = " ".join(sentences[:sentence_count]) if total >= sentence_count else " ".join(sentences)
    if not overview_text.endswith('.'):
        overview_text += '.'

    return {
        "success": True,
        "summary": f"Executive Summary ({video_title}): {overview_text}",
        "key_points": [
            f"Key Concept: Core discussions in '{video_title}'.",
            f"Main Focus: {sentences[0] if sentences else 'Detailed explanations in video.'}",
            f"Takeaway: {sentences[1] if len(sentences) > 1 else 'Final conclusions.'}"
        ],
        "engine": "Smart Local NLP Engine"
    }

def generate_ai_summary(transcript_text, video_title, summary_length="medium"):
    """
    Calls Google Gemini AI (gemini-3.5-flash, gemini-flash-lite-latest, gemini-3.7-flash) to generate high-accuracy summaries.
    """
    api_key = Config.GEMINI_API_KEY.strip()

    if not api_key:
        print("[AI Service] No GEMINI_API_KEY found in .env. Using Smart Local NLP Engine.")
        return smart_nlp_summary(transcript_text, video_title, summary_length)

    length_instructions = {
        "short": "Write a concise 1-to-2 sentence summary and 3 key points.",
        "medium": "Write a clear 3-to-4 sentence summary and 4-to-6 key points.",
        "detailed": "Write a thorough 6-to-8 sentence summary and 6-to-8 key points."
    }
    prompt = f"""
You are an expert research assistant and content analyst. Analyze the following transcript for the YouTube video titled "{video_title}".

Provide an ACCURATE, HIGH-QUALITY summary in JSON format with EXACTLY two fields:
1. "summary": An informative executive summary paragraph explaining WHAT the video covers, WHY it matters, and the MAIN LESSONS.
2. "key_points": A list of specific, actionable bullet points detailing the key concepts, tools, or conclusions from the video.

SUMMARY LENGTH: {length_instructions.get(summary_length, length_instructions['medium'])}

CRITICAL INSTRUCTIONS:
- Do NOT copy verbatim transcript fluff ("welcome", "subscribe", "like the video").
- Write in clear, professional, easy-to-understand language.
- Return ONLY valid raw JSON without markdown codeblocks.

Transcript:
{transcript_text[:14000]}
"""

    model_names = ["gemini-3.5-flash", "gemini-flash-lite-latest", "gemini-3.7-flash"]
    last_error = ""

    for model in model_names:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "response_mime_type": "application/json"
                }
            }

            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})

            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
                candidates = result.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts:
                        raw_text = parts[0].get('text', '').strip()
                        if raw_text.startswith("```json"):
                            raw_text = raw_text[7:]
                        if raw_text.startswith("```"):
                            raw_text = raw_text[3:]
                        if raw_text.endswith("```"):
                            raw_text = raw_text[:-3]

                        parsed = json.loads(raw_text.strip())
                        print(f"[AI Service SUCCESS] Generated summary using Google Gemini ({model}).")
                        return {
                            "success": True,
                            "summary": parsed.get("summary", "Summary generated."),
                            "key_points": parsed.get("key_points", []),
                            "engine": f"Google Gemini AI ({model})"
                        }
        except urllib.error.HTTPError as http_err:
            err_msg = http_err.read().decode('utf-8')
            print(f"[Gemini API {model} HTTP Error {http_err.code}]: {err_msg}")
            last_error = f"HTTP {http_err.code}"
            continue
        except Exception as e:
            print(f"[Gemini API {model} Error]: {e}")
            last_error = str(e)
            continue

    print(f"[Gemini API Failed]: {last_error}. Using fallback summarizer.")
    return smart_nlp_summary(transcript_text, video_title, summary_length)
