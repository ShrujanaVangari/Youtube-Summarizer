import os
from dotenv import load_dotenv

# Load environment variables explicitly from backend/.env
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

class Config:
    PORT = int(os.getenv('PORT', 5000))
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = FLASK_ENV == 'development'

    # Third-Party API & Database Configurations
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    DATABASE_URL = os.getenv('DATABASE_URL', '')

    # Optional: proxy URL to bypass YouTube IP blocks on cloud servers (e.g. Render)
    # Format: https://user:password@host:port  or  socks5://user:password@host:port
    TRANSCRIPT_PROXY_URL = os.getenv('TRANSCRIPT_PROXY_URL', '')
