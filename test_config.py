#!/usr/bin/env python3
"""
Test script to verify configuration is working properly.
"""

import sys
import os

# Add the project root to the path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    print("Importing configuration...")
    from config.config import (
        BASE_DIR, BASE_DATA_DIR, RUNS_DIR, SESSIONS_DIR, DB_PATH,
        LOG_LEVEL, LOG_FORMAT, FLASK_DEBUG, FLASK_PORT, SECRETS_LOADED
    )
    
    print("\nConfiguration paths:")
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"BASE_DATA_DIR: {BASE_DATA_DIR}")
    print(f"RUNS_DIR: {RUNS_DIR}")
    print(f"SESSIONS_DIR: {SESSIONS_DIR}")
    print(f"DB_PATH: {DB_PATH}")
    
    print("\nFlask settings:")
    print(f"FLASK_DEBUG: {FLASK_DEBUG}")
    print(f"FLASK_PORT: {FLASK_PORT}")
    
    print("\nLogging settings:")
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print(f"LOG_FORMAT: {LOG_FORMAT}")
    
    print("\nSecrets:")
    print(f"SECRETS_LOADED: {SECRETS_LOADED}")
    
    # Check if directories exist
    print("\nVerifying directories...")
    print(f"BASE_DIR exists: {os.path.exists(BASE_DIR)}")
    print(f"BASE_DATA_DIR exists: {os.path.exists(BASE_DATA_DIR)}")
    print(f"RUNS_DIR exists: {os.path.exists(RUNS_DIR)}")
    print(f"SESSIONS_DIR exists: {os.path.exists(SESSIONS_DIR)}")
    
    print("\nConfiguration test successful! All imports worked correctly.")
    sys.exit(0)
except ImportError as e:
    print(f"\nConfiguration test failed: {e}")
    print("\nCurrent sys.path:")
    for path in sys.path:
        print(f"  - {path}")
    sys.exit(1)
except Exception as e:
    print(f"\nUnexpected error: {e}")
    sys.exit(1) 