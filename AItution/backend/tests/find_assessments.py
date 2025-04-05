#!/usr/bin/env python3
"""
Script to find all completed assessments ready for content creation.
"""

import sys
import os
import json
import sqlite3
import logging
from datetime import datetime

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Import config
from config.config import (
    BASE_DIR, BASE_DATA_DIR, RUNS_DIR, SESSIONS_DIR, DB_PATH,
    LOG_LEVEL, LOG_FORMAT
)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('find_assessments.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def find_completed_assessments():
    """Find assessment sessions that have been completed but don't have content yet."""
    logger.info("Looking for completed assessments without content")
    
    if not os.path.exists(DB_PATH):
        logger.error(f"Database file '{DB_PATH}' not found")
        return []
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Find sessions with completed assessments but no content creation
        cursor.execute("""
            SELECT session_id, assessment_start, assessment_finish
            FROM session_timing
            WHERE assessment_status = 'completed'
            AND (content_creation_status = 'not_started' OR content_creation_status = 'error')
            ORDER BY assessment_finish DESC
        """)
        
        rows = cursor.fetchall()
        results = []
        
        for row in rows:
            session_id, assessment_start, assessment_finish = row
            
            # Check if conversation file exists
            session_dir = os.path.join(SESSIONS_DIR, session_id)
            conv_file = os.path.join(session_dir, 'conversation.json')
            
            if os.path.exists(conv_file):
                with open(conv_file, 'r') as f:
                    try:
                        conversation = json.load(f)
                        
                        # Extract assessment data if available
                        assessment_data = None
                        for msg in reversed(conversation.get('conversation', [])):
                            if msg.get('source') == 'assessment_agent' and 'ASSESSMENT COMPLETE' in msg.get('content', ''):
                                # Try to extract JSON
                                import re
                                json_match = re.search(r'```json\s*(.*?)\s*```', msg.get('content', ''), re.DOTALL)
                                if json_match:
                                    try:
                                        assessment_json = json.loads(json_match.group(1))
                                        assessment_data = assessment_json.get('assessment', {})
                                        break
                                    except:
                                        pass
                        
                        results.append({
                            'session_id': session_id,
                            'assessment_start': assessment_start,
                            'assessment_finish': assessment_finish,
                            'assessment_data': assessment_data
                        })
                    except:
                        logger.error(f"Error reading conversation file for session {session_id}")
            else:
                logger.warning(f"Conversation file not found for session {session_id}")
        
        conn.close()
        logger.info(f"Found {len(results)} completed assessments without content")
        return results
        
    except Exception as e:
        logger.error(f"Error finding completed assessments: {str(e)}")
        return []

if __name__ == "__main__":
    results = find_completed_assessments()
    
    if not results:
        print("No completed assessments without content found.")
        sys.exit(0)
    
    print(f"Found {len(results)} completed assessments without content:")
    for i, result in enumerate(results, 1):
        if result.get('assessment_data'):
            skill_level = result.get('assessment_data', {}).get('skill_level', 'unknown')
            topics = ', '.join(result.get('assessment_data', {}).get('topics', []))
            print(f"{i}. Session: {result['session_id']} - Skill level: {skill_level} - Topics: {topics}")
        else:
            print(f"{i}. Session: {result['session_id']} - No assessment data available")
    
    sys.exit(0) 