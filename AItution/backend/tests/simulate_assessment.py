#!/usr/bin/env python3
"""
Script to create a mock assessment for testing content creation.
"""

import sys
import os
import json
import sqlite3
import argparse
import logging
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulate_assessment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from database import db
except ImportError:
    logger.error("Could not import database module")
    sys.exit(1)

def create_mock_assessment():
    """Create a mock assessment with a conversation file."""
    session_id = str(uuid.uuid4())
    logger.info(f"Creating mock assessment with ID: {session_id}")
    
    # Initialize database entry
    db.init_session_timing(session_id)
    
    # Create the session directory
    session_dir = os.path.join('data', 'sessions', session_id)
    logger.info(f"Creating directory: {session_dir}")
    os.makedirs(session_dir, exist_ok=True)
    
    # Create a minimal mock conversation
    conversation = {
        "conversation": [
            {"source": "assessment_agent", "content": "What's your programming experience?"},
            {"source": "user", "content": "I have 5 years of Python experience."},
            {"source": "assessment_agent", "content": "ASSESSMENT COMPLETE\n\n```json\n{\"assessment\": {\"skill_level\": \"Intermediate\"}}\n```"}
        ]
    }
    
    conv_file = os.path.join(session_dir, 'conversation.json')
    logger.info(f"Creating conversation file: {conv_file}")
    
    try:
        with open(conv_file, 'w') as f:
            json.dump(conversation, f, indent=2)
        logger.info(f"Conversation file created successfully")
    except Exception as e:
        logger.error(f"Error creating conversation file: {str(e)}")
        return None
    
    # Mark as completed in database
    logger.info(f"Marking assessment as completed")
    db.complete_assessment(session_id)
    
    logger.info(f"Mock assessment created with ID: {session_id}")
    print(f"Mock assessment created with ID: {session_id}")
    print(f"Conversation file: {conv_file}")
    print(f"Run content creation test: python -m tests.test_content_creation --session-id {session_id}")
    
    return session_id

if __name__ == "__main__":
    create_mock_assessment() 