import os
import logging
from pathlib import Path

# Base paths configuration
BASE_DIR = Path(__file__).parent.parent.absolute()
BASE_DATA_DIR = os.path.join(BASE_DIR, 'data')
RUNS_DIR = os.path.join(BASE_DATA_DIR, 'runs')
SESSIONS_DIR = os.path.join(BASE_DATA_DIR, 'sessions')
DB_PATH = os.path.join(BASE_DIR, 'assessment_sessions.db')

# Ensure directories exist
os.makedirs(RUNS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Logging configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Flask server configuration
FLASK_DEBUG = os.environ.get('FLASK_ENV') == 'development'
FLASK_PORT = 5000

# Load secrets if available
try:
    from config.secrets import *
    SECRETS_LOADED = True
except ImportError:
    SECRETS_LOADED = False
    print("Warning: secrets.py not found. Using default or environment values for secrets.")
    # Define fallback values or use environment variables
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Print configuration for debugging
if __name__ == "__main__":
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"BASE_DATA_DIR: {BASE_DATA_DIR}")
    print(f"RUNS_DIR: {RUNS_DIR}")
    print(f"SESSIONS_DIR: {SESSIONS_DIR}")
    print(f"DB_PATH: {DB_PATH}")
    print(f"SECRETS_LOADED: {SECRETS_LOADED}")