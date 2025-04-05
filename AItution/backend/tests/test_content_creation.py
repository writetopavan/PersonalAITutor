#!/usr/bin/env python3
"""
Test module for content creation APIs.
This script tests the following APIs:
1. /api/content/start - Starts content creation for an assessment session
2. /api/content/status - Gets the status of content creation
"""

import requests
import time
import json
import os
import sys
import sqlite3
import argparse
import logging
from datetime import datetime
import unittest
import asyncio
import shutil

# Add parent directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
root_dir = os.path.dirname(parent_dir)
sys.path.insert(0, root_dir)

# Import config and database
from config.config import (
    BASE_DIR, BASE_DATA_DIR, RUNS_DIR, SESSIONS_DIR, DB_PATH,
    LOG_LEVEL, LOG_FORMAT
)
try:
    from database import db
except ImportError:
    logger.error("Could not import database. Make sure you're running from project root.")
    sys.exit(1)

from course_content_agent import CourseContentAgent

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('test_content_creation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TestContentCreation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test database and test data."""
        # Create a test session ID
        cls.session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create test session directory
        cls.session_dir = os.path.join(SESSIONS_DIR, cls.session_id)
        os.makedirs(cls.session_dir, exist_ok=True)
        
        # Create a sample conversation file
        cls.conversation = {
            "conversation": [
                {"source": "user", "content": "I want to learn about Python programming."},
                {"source": "assessment_agent", "content": "Great! I'll ask you some questions about Python."},
                {"source": "user", "content": "I know the basics of Python."},
                {"source": "assessment_agent", "content": "ASSESSMENT COMPLETE\n\n```json\n{\"assessment\": {\"skill_level\": \"beginner\", \"topics\": [\"Python basics\", \"variables\", \"control flow\"]}}\n```"}
            ]
        }
        
        with open(os.path.join(cls.session_dir, 'conversation.json'), 'w') as f:
            json.dump(cls.conversation, f)
        
        # Set up test database record
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_timing (
            session_id TEXT PRIMARY KEY,
            assessment_start TIMESTAMP,
            assessment_finish TIMESTAMP,
            content_creation_start TIMESTAMP,
            content_creation_finish TIMESTAMP,
            assessment_status TEXT CHECK(assessment_status IN ('started', 'in_progress', 'completed')) DEFAULT 'started',
            content_creation_status TEXT CHECK(content_creation_status IN ('not_started', 'started', 'in_progress', 'completed', 'error')) DEFAULT 'not_started',
            content_creation_error TEXT
        )
        ''')
        
        # Insert test data
        cursor.execute(
            "INSERT INTO session_timing (session_id, assessment_start, assessment_finish, assessment_status) VALUES (?, ?, ?, ?)",
            (cls.session_id, datetime.utcnow(), datetime.utcnow(), 'completed')
        )
        
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up test data."""
        # Remove test session record
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM session_timing WHERE session_id = ?", (cls.session_id,))
        conn.commit()
        conn.close()
        
        # Remove test session directory
        if os.path.exists(cls.session_dir):
            shutil.rmtree(cls.session_dir)
            
        # Remove test run directory
        run_dir = os.path.join(RUNS_DIR, cls.session_id)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)

def find_completed_assessments():
    """Find assessment sessions that have been completed but don't have content yet."""
    completed_assessments = []
    
    try:
        # Connect to the database
        conn = sqlite3.connect('C:/Pavan/Dev/AutoGen/autogen_start/assessment_sessions.db')
        cursor = conn.cursor()
        
        # Find completed assessments that don't have content yet
        cursor.execute("""
            SELECT session_id, assessment_start, assessment_finish 
            FROM session_timing 
            WHERE assessment_status = 'completed' 
            AND (content_creation_status = 'not_started' OR content_creation_status IS NULL)
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        for row in rows:
            # Check if conversation file exists
            session_id = row[0]
            conv_file = os.path.join('data', 'sessions', session_id, 'conversation.json')
            if os.path.exists(conv_file):
                completed_assessments.append({
                    'session_id': session_id,
                    'assessment_start': row[1],
                    'assessment_finish': row[2],
                    'conversation_file': conv_file
                })
                logger.info(f"Found completed assessment: {session_id}")
        
    except Exception as e:
        logger.error(f"Error finding completed assessments: {str(e)}")
    
    return completed_assessments

def debug_database_tables():
    """Inspect the database tables and their contents."""
    try:
        # Connect to the database
        conn = sqlite3.connect('C:/Pavan/Dev/AutoGen/autogen_start/assessment_sessions.db')
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        logger.info("Database tables:")
        for table in tables:
            table_name = table[0]
            logger.info(f"\nTable: {table_name}")
            
            # Get schema
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            logger.info("Schema:")
            for col in columns:
                logger.info(f"  {col[1]} ({col[2]})")
            
            # Get sample data
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            rows = cursor.fetchall()
            if rows:
                logger.info("Sample data:")
                for row in rows:
                    logger.info(f"  {row}")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error debugging database: {str(e)}")

def check_content_creation_progress(base_url, session_id):
    """Check the progress of content creation."""
    try:
        # Create a session object and set the Flask session cookie
        s = requests.Session()
        flask_session = {'assessment_session_id': session_id}
        s.cookies.set('session', json.dumps(flask_session))
        
        response = s.get(f"{base_url}/api/content/status")
        
        if response.status_code != 200:
            logger.error(f"Failed to get status: {response.status_code} - {response.text}")
            return None
        
        return response.json()
    except Exception as e:
        logger.error(f"Error checking content creation progress: {str(e)}")
        return None

def test_content_creation(base_url, session_id=None, use_existing_session=False, max_polls=60, poll_interval=10):
    """Test the content creation APIs using an existing assessment."""
    logger.info(f"Testing content creation APIs at {base_url}")
    
    # Create session for requests
    req_session = requests.Session()
    
    # Step 1: If no session_id provided, find a completed assessment
    if not session_id and not use_existing_session:
        logger.info("Looking for completed assessments...")
        completed_assessments = find_completed_assessments()
        
        if not completed_assessments:
            logger.error("No completed assessments found. Please complete an assessment first.")
            return False
        
        # Use the first completed assessment
        assessment = completed_assessments[0]
        session_id = assessment['session_id']
        logger.info(f"Using completed assessment with session ID: {session_id}")
    
    # If use_existing_session is True, start a new assessment to get a session ID
    if use_existing_session and not session_id:
        logger.info("Starting a new assessment session...")
        try:
            response = req_session.post(f"{base_url}/api/assessment/start")
            if response.status_code != 200:
                logger.error(f"Failed to start assessment: {response.status_code} - {response.text}")
                return False
            
            data = response.json()
            session_id = data.get('session_id')
            logger.info(f"Created new assessment session: {session_id}")
        except Exception as e:
            logger.error(f"Error starting assessment: {str(e)}")
            return False
    
    if not session_id:
        logger.error("No session ID available. Cannot proceed.")
        return False
    
    # Step 2: Set up session cookies - this is key for Flask server-side sessions
    flask_session = {'assessment_session_id': session_id}
    req_session.cookies.set('session', json.dumps(flask_session))
    
    # Step 3: Start content creation
    logger.info(f"Starting content creation for session {session_id}...")
    try:
        response = req_session.post(f"{base_url}/api/content/start")
        
        if response.status_code != 200:
            logger.error(f"Failed to start content creation: {response.status_code} - {response.text}")
            return False
        
        logger.info(f"Content creation started: {response.json()}")
    except Exception as e:
        logger.error(f"Error starting content creation: {str(e)}")
        return False
    
    # Step 4: Poll the status endpoint until content creation completes or fails
    logger.info("Polling status endpoint...")
    for i in range(max_polls):
        logger.info(f"Status check {i+1}/{max_polls}...")
        
        try:
            response = req_session.get(f"{base_url}/api/content/status")
            
            if response.status_code != 200:
                logger.error(f"Failed to get status: {response.status_code} - {response.text}")
                time.sleep(poll_interval)
                continue
            
            status_data = response.json()
            progress = status_data.get('progress', {})
            status = progress.get('status')
            
            logger.info(f"Current status: {status}")
            
            # Print progress details if available
            if 'modules' in progress and progress['modules']:
                module_count = len(progress['modules'])
                logger.info(f"Modules found: {module_count}")
                
                # Show detailed progress for all modules
                for module in progress['modules']:
                    logger.info(f"Module '{module['name']}' progress:")
                    logger.info(f"  Summary: {'✓' if module.get('has_summary') else '✗'}")
                    logger.info(f"  Quiz: {'✓' if module.get('has_quiz') else '✗'}")
                    
                    # Show chapter progress
                    for chapter in module.get('chapters', []):
                        logger.info(f"  Chapter '{chapter['title']}':")
                        logger.info(f"    Has plan: {'✓' if chapter.get('has_plan') else '✗'}")
                        logger.info(f"    Pages completed: {chapter.get('pages_completed', 0)}")
                    
                    logger.info("-----")
            
            # Check if complete or error
            if status in ['completed', 'error']:
                logger.info(f"Content creation {status}!")
                
                if status == 'completed':
                    logger.info("Checking if course file was created...")
                    run_dir = os.path.join('data', 'runs', session_id)
                    courses_dir = os.path.join(run_dir, 'courses')
                    
                    if os.path.exists(courses_dir):
                        json_files = [f for f in os.listdir(courses_dir) if f.endswith('.json')]
                        if json_files:
                            logger.info(f"Course file created: {json_files[0]}")
                        else:
                            logger.warning("No course file found!")
                    else:
                        logger.warning(f"Courses directory not found: {courses_dir}")
                
                return status == 'completed'
            
            time.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Error polling status: {str(e)}")
            time.sleep(poll_interval)
    
    logger.warning("Maximum polling attempts reached. Content creation still in progress.")
    return False

def test_direct_functions(session_id=None):
    """Test the database functions directly without API for content creation."""
    logger.info("Testing content creation database functions directly")
    
    try:
        if not session_id:
            # Create a test session ID if not provided
            session_id = f"test_{int(time.time())}"
            
            # Initialize a session in the database
            logger.info(f"Creating test session with ID: {session_id}")
            db.init_session_timing(session_id)
            
            # Set assessment status to completed
            logger.info(f"Setting assessment status to completed for {session_id}")
            db.update_assessment_status(session_id, 'completed')
            db.complete_assessment(session_id)
        
        # Test content creation start
        logger.info(f"Starting content creation for session {session_id}")
        db.start_content_creation(session_id)
        
        # Check status
        status = db.get_content_creation_status(session_id)
        logger.info(f"Initial content creation status: {status}")
        
        # Update status to in_progress
        logger.info("Updating status to in_progress")
        db.update_content_creation_status(session_id, 'in_progress')
        
        # Check updated status
        status = db.get_content_creation_status(session_id)
        logger.info(f"Updated content creation status: {status}")
        
        # Mark as complete
        logger.info("Marking content creation as complete")
        db.complete_content_creation(session_id)
        
        # Check final status
        status = db.get_content_creation_status(session_id)
        logger.info(f"Final content creation status: {status}")
        
        # Verify status is 'completed'
        if status and status['status'] == 'completed':
            logger.info("Direct function test passed - status correctly updated to 'completed'")
            return True
        else:
            logger.error("Direct function test failed - status not correctly updated")
            return False
    except Exception as e:
        logger.error(f"Error in direct test: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test content creation APIs')
    parser.add_argument('--base-url', default='http://localhost:5000', help='Base URL for the API server')
    parser.add_argument('--session-id', help='Optional specific session ID to use')
    parser.add_argument('--debug-db', action='store_true', help='Print database debug information')
    parser.add_argument('--use-existing-session', action='store_true', help='Start a new assessment to get a session')
    parser.add_argument('--max-polls', type=int, default=60, help='Maximum number of status checks')
    parser.add_argument('--poll-interval', type=int, default=10, help='Seconds between status checks')
    parser.add_argument('--direct-test', action='store_true', help='Test database functions directly (no API)')
    
    args = parser.parse_args()
    
    if args.debug_db:
        debug_database_tables()
    
    success = False
    
    if args.direct_test:
        # Test database functions directly
        success = test_direct_functions(args.session_id)
    else:
        # Test the API endpoints
        success = test_content_creation(
            args.base_url, 
            args.session_id,
            args.use_existing_session,
            args.max_polls,
            args.poll_interval
        )
    
    if success:
        logger.info("Content creation test completed successfully!")
        sys.exit(0)
    else:
        logger.error("Content creation test failed or timed out!")
        sys.exit(1) 