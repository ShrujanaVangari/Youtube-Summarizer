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
