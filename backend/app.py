"""
YouTube AI Summarizer - Flask Backend Application Core (Full Integration)
"""

import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from config import Config

from services.transcript_service import extract_transcript
from services.ai_service import generate_ai_summary
from services.db_service import (
    init_db, 
    get_summary_by_video_id,
    save_summary, 
    fetch_all_summaries
)

def create_app():
    frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
    app.config.from_object(Config)

    # Enable Cross-Origin Resource Sharing (CORS) for frontend requests
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Auto-initialize database tables on server startup
    with app.app_context():
        init_db()

    # ==========================================
    # Health Check & Status Endpoint
    # ==========================================
    @app.route('/', methods=['GET'])
    def index():
        return send_from_directory(frontend_dir, 'index.html')

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            "status": "healthy",
            "database_configured": bool(Config.DATABASE_URL),
            "gemini_configured": bool(Config.GEMINI_API_KEY)
        }), 200

    # ==========================================
    # Summarization End-to-End Pipeline Route
    # ==========================================
    @app.route('/api/summarize', methods=['POST'])
    def summarize_video():
        """
        Complete AI Summarization Pipeline:
        1. Parse input URL and Video ID
        2. Extract YouTube video transcript & metadata
        3. Call AI service to generate brief summary & key points
        4. Persist result into Neon DB
        5. Return clean JSON response to client
        """
        data = request.get_json() or {}
        youtube_url = data.get('url')
        video_id = data.get('video_id')
        summary_length = data.get('summary_length', 'medium')

        if not youtube_url or not video_id:
            return jsonify({
                "success": False,
                "error": "Missing required parameters: 'url' and 'video_id'."
            }), 400

        if summary_length not in {'short', 'medium', 'detailed'}:
            return jsonify({
                "success": False,
                "error": "Invalid summary_length. Use short, medium, or detailed."
            }), 400

        cached_record = get_summary_by_video_id(video_id, summary_length)
        if cached_record:
            return jsonify({"success": True, "cached": True, "data": cached_record}), 200

        # Step 1: Extract YouTube Transcript
        transcript_result = extract_transcript(video_id)
        if not transcript_result["success"]:
            return jsonify({
                "success": False,
                "error": transcript_result.get("error", "Failed to extract transcript.")
            }), 400

        video_title = transcript_result["title"]
        transcript_text = transcript_result["transcript_text"]

        # Step 2: Generate AI Summary
        ai_result = generate_ai_summary(transcript_text, video_title, summary_length)
        if not ai_result["success"]:
            return jsonify({
                "success": False,
                "error": ai_result.get("error", "Failed to generate AI summary.")
            }), 500

        summary_text = ai_result["summary"]
        key_points = ai_result["key_points"]

        # Step 3: Persist in Neon DB
        saved_record = save_summary(
            youtube_url=youtube_url,
            video_id=video_id,
            title=video_title,
            summary=summary_text,
            key_points=key_points,
            summary_length=summary_length
        )

        response_payload = saved_record if saved_record else {
            "youtube_url": youtube_url,
            "video_id": video_id,
            "title": video_title,
            "summary": summary_text,
            "key_points": key_points,
            "created_at": None
        }

        return jsonify({
            "success": True,
            "data": response_payload
        }), 200

    # ==========================================
    # History Route
    # ==========================================
    @app.route('/api/history', methods=['GET'])
    def get_history():
        """
        Retrieves all saved video summaries from Neon DB.
        """
        records = fetch_all_summaries()
        return jsonify({
            "success": True,
            "count": len(records),
            "data": records
        }), 200

    # ==========================================
    # Global Error Handlers
    # ==========================================
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({"success": False, "error": "Internal server error"}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    print(f"[SERVER] YouTube AI Summarizer Server running on http://127.0.0.1:{Config.PORT}")
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
