from flask import Flask, jsonify, send_from_directory, request, session
from flask_cors import CORS
import os
import json
import glob
import sys
import logging
import re
from datetime import datetime
import secrets
from flask_session import Session  # Import Flask-Session extension
import uuid
import asyncio
from database import db
from threading import Thread
from queue import Queue
import time
import sqlite3
from assessment_agent import external_termination, start_assessment, team, set_user_response, get_next_question, get_answer_for_question

# Add project root to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import config
from config.config import (
    BASE_DIR, BASE_DATA_DIR, RUNS_DIR, SESSIONS_DIR, DB_PATH,
    LOG_LEVEL, LOG_FORMAT, FLASK_DEBUG, FLASK_PORT, FLASK_SECRET_KEY
)

# Ensure directories exist
os.makedirs(RUNS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"BASE_DATA_DIR set to: {BASE_DATA_DIR}")
logger.info(f"RUNS_DIR set to: {RUNS_DIR}")
logger.info(f"SESSIONS_DIR set to: {SESSIONS_DIR}")
logger.info(f"DB_PATH set to: {DB_PATH}")

# Now import local modules
from assessment_agent import external_termination, start_assessment, team, set_user_response, get_next_question, get_answer_for_question
from course_content_agent import CourseContentAgent

app = Flask(__name__)
# Set a secret key for session encryption
app.secret_key = FLASK_SECRET_KEY

# Configure server-side sessions using filesystem
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_USE_SIGNER"] = True
Session(app)

CORS(app, supports_credentials=True)  # Enable credentials for sessions

# Store conversation state for assessments
conversation_states = {}

def get_chapter_content_from_intermediate(run_id: str, module_name: str, chapter_title: str) -> dict:
    """Get chapter content from the intermediate folder."""
    logger.info(f"Fetching chapter content for run_id: {run_id}, module: {module_name}, chapter: {chapter_title}")
    base_dir = os.path.join(
        RUNS_DIR, 
        run_id, 
        'intermediate'
    )
    
    # Get the chapter plan first
    chapter_plan_file = os.path.join(base_dir, f'chapter_plan_{module_name}_{chapter_title}.json')
    pages = []
    
    # Get all page files for this chapter
    page_pattern = os.path.join(base_dir, f'page_{module_name}_{chapter_title}_*.json')
    page_files = glob.glob(page_pattern)
    
    if page_files:
        for page_file in page_files:
            try:
                with open(page_file, 'r', encoding='utf-8') as f:
                    page_data = json.load(f)
                    pages.append(page_data)
                    logger.debug(f"Successfully loaded page from {page_file}")
            except Exception as e:
                logger.error(f"Error reading page file {page_file}: {str(e)}")
    
    logger.info(f"Found {len(pages)} pages for chapter {chapter_title}")
    return {
        "title": chapter_title,
        "pages": pages
    }

def get_module_quiz_from_intermediate(run_id: str, module_name: str) -> list:
    """Get quiz data from the intermediate folder."""
    logger.info(f"Fetching quiz data for run_id: {run_id}, module: {module_name}")
    quiz_file = os.path.join(
        RUNS_DIR, 
        run_id, 
        'intermediate',
        f'quiz_{module_name}.json'
    )
    
    if os.path.exists(quiz_file):
        try:
            with open(quiz_file, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)
                logger.info(f"Successfully loaded quiz data for module {module_name}")
                return quiz_data
        except Exception as e:
            logger.error(f"Error reading quiz file {quiz_file}: {str(e)}")
    logger.warning(f"No quiz file found for module {module_name}")
    return []

def get_module_summary_from_intermediate(run_id: str, module_name: str) -> str:
    """Get module summary from the intermediate folder."""
    logger.info(f"Fetching module summary for run_id: {run_id}, module: {module_name}")
    summary_file = os.path.join(
        RUNS_DIR, 
        run_id, 
        'intermediate',
        f'summary_{module_name}.json'
    )
    
    if os.path.exists(summary_file):
        try:
            with open(summary_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                logger.info(f"Successfully loaded summary for module {module_name}")
                return data.get('summary', '')
        except Exception as e:
            logger.error(f"Error reading summary file {summary_file}: {str(e)}")
    logger.warning(f"No summary file found for module {module_name}")
    return ''

@app.route('/data/runs')
def list_runs():
    logger.info("Listing all available runs")
    runs_dir = RUNS_DIR
    runs = []
    
    try:
        # List all run directories
        for run_id in os.listdir(runs_dir):
            courses_dir = os.path.join(runs_dir, run_id, 'courses')
            if os.path.exists(courses_dir):
                # Get the first JSON file in the courses directory
                json_files = [f for f in os.listdir(courses_dir) if f.endswith('.json')]
                if json_files:
                    course_file = os.path.join(courses_dir, json_files[0])
                    try:
                        with open(course_file, 'r', encoding='utf-8') as f:
                            course_data = json.load(f)
                            # Add run_id to the course data
                            course_data['run_id'] = run_id
                            runs.append(course_data)
                            logger.debug(f"Loaded course data for run_id: {run_id}")
                    except Exception as e:
                        logger.error(f"Error reading {course_file}: {str(e)}")
    except Exception as e:
        logger.error(f"Error listing runs directory: {str(e)}")
    
    logger.info(f"Found {len(runs)} runs")
    return jsonify(runs)

@app.route('/data/runs/<run_id>/course.json')
def get_course(run_id):
    logger.info(f"Fetching course data for run_id: {run_id}")
    courses_dir = os.path.join(RUNS_DIR, run_id, 'courses')
    if os.path.exists(courses_dir):
        json_files = [f for f in os.listdir(courses_dir) if f.endswith('.json')]
        if json_files:
            course_file = os.path.join(courses_dir, json_files[0])
            try:
                with open(course_file, 'r', encoding='utf-8') as f:
                    course_data = json.load(f)
                    # Add run_id to the course data
                    course_data['run_id'] = run_id
                    
                    # Update each module with content from intermediate files
                    for module in course_data['modules']:
                        logger.debug(f"Processing module: {module['name']}")
                        # Add quiz data
                        module['quiz'] = get_module_quiz_from_intermediate(run_id, module['name'])
                        
                        # Add module summary
                        module['summary'] = get_module_summary_from_intermediate(run_id, module['name'])
                        
                        # Update chapters with content
                        for chapter in module['chapters']:
                            chapter_content = get_chapter_content_from_intermediate(
                                run_id, 
                                module['name'], 
                                chapter['title']
                            )
                            if chapter_content and 'pages' in chapter_content:
                                chapter['pages'] = chapter_content['pages']
                            else:
                                # Initialize with empty pages if no content found
                                chapter['pages'] = []
                    
                    logger.info(f"Successfully loaded course data for run_id: {run_id}")
                    return jsonify(course_data)
            except Exception as e:
                logger.error(f"Error reading course file: {str(e)}")
                return jsonify({'error': f'Error reading course file: {str(e)}'}), 500
    logger.warning(f"Course not found for run_id: {run_id}")
    return jsonify({'error': 'Course not found'}), 404

@app.route('/api/assessment/start', methods=['POST'])
def start_assessment_endpoint():
    """Start a new assessment session."""
    logger.info("Starting new assessment session")
    
    session_id = str(uuid.uuid4())
    session['assessment_session_id'] = session_id
    
    try:
        # Initialize session timing
        db.init_session_timing(session_id)

        # Create a function that will run the assessment asynchronously
        def run_background_assessment(app_context):
            with app_context:
                async def async_assessment():
                    try:
                        external_termination.set()
                        await team.reset()
                        await start_assessment(session_id)
                        logger.info(f"Background assessment completed for session {session_id}")
                    except Exception as e:
                        logger.error(f"Background assessment error: {str(e)}", exc_info=True)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(async_assessment())
                finally:
                    loop.close()
        
        # Start the background task with app context
        ctx = app.app_context()
        background_thread = Thread(target=run_background_assessment, args=(ctx,))
        background_thread.daemon = True
        background_thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': "Assessment started in background. Use the question endpoint to retrieve questions when ready."
        })
        
    except Exception as e:
        logger.error(f"Error starting assessment: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error starting assessment: {str(e)}'}), 500

@app.route('/api/assessment/question', methods=['GET'])
def get_question_endpoint():
    """Get the next question for the current assessment session."""
    # Get the session ID from the user's session
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        logger.warning("No active assessment session found in request")
        return jsonify({'error': 'No active assessment session'}), 400
    
    logger.info(f"Getting next question for session {session_id}")
    
    try:
        # First check if the conversation JSON file exists, which indicates assessment completion
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        conv_file = os.path.join(session_dir, f'conversation.json')
        
        if os.path.exists(conv_file):
            logger.debug(f"Found conversation file for session {session_id}")
            # We don't need to process the file content here - just indicate completion
            return jsonify({
                'success': True,
                'assessment_complete': True,
                'message': 'Assessment complete. Use the result endpoint to get assessment details.'
            })
        
        # If the conversation file doesn't exist, check for questions
        logger.debug("Checking for next question in database")
        question = get_next_question(session_id)
        logger.info(f"Question: {question}")
        
        if question:
            logger.info(f"Found next question: {question[:50]}...")
            # Try to parse JSON format if present in the question
            try:
                json_match = re.search(r'```json\s*(.*?)\s*```', question, re.DOTALL)
                
                if json_match:
                    question_json = json.loads(json_match.group(1))
                    logger.debug("Successfully parsed question JSON")
                    return jsonify({
                        'success': True,
                        'assessment_complete': False,
                        'question': question,
                        'formatted_question': question_json
                    })
            except Exception as json_err:
                logger.warning(f"Error parsing question JSON: {str(json_err)}")
            
            # Return the raw question if JSON parsing fails
            return jsonify({
                'success': True,
                'assessment_complete': False,
                'question': question
            })
        else:
            # No questions and no conversation file - assessment still in progress
            logger.info("No questions found, checking assessment progress")
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Count questions and answers for this session
            cursor.execute(
                "SELECT COUNT(*) FROM assessment_data WHERE session_id = ?",
                (session_id,)
            )
            total_records = cursor.fetchone()[0]
            
            cursor.execute(
                "SELECT COUNT(*) FROM assessment_data WHERE session_id = ? AND answer IS NOT NULL",
                (session_id,)
            )
            answered_records = cursor.fetchone()[0]
            
            conn.close()
            
            logger.info(f"Assessment progress: {answered_records}/{total_records} questions answered")
            
            # Tell client to keep polling - we're processing
            return jsonify({
                'success': True,
                'assessment_complete': False,
                'processing': True,
                'progress': {
                    'total': total_records,
                    'answered': answered_records
                },
                'message': 'Assessment in progress. Please continue polling for results.'
            })
    except Exception as e:
        logger.error(f"Error getting question: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error getting question: {str(e)}'}), 500

@app.route('/api/assessment/answer', methods=['POST'])
def submit_answer_endpoint():
    """Submit an answer to the current question."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        logger.warning("No active assessment session found in request")
        return jsonify({'error': 'No active assessment session'}), 400
    
    try:
        # Update status to in_progress when first answer is submitted
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE session_timing SET assessment_status = 'in_progress' WHERE session_id = ? AND assessment_status = 'started'",
            (session_id,)
        )
        conn.commit()
        conn.close()

        # Get the answer from the request
        data = request.json
        answer = data.get('answer', '')
        
        if not answer:
            logger.warning("Empty answer submitted")
            return jsonify({'error': 'Answer is required'}), 400
        
        logger.info(f"Submitting answer for session {session_id}")
        logger.debug(f"Answer content: {answer[:50]}...")
        
        # Store the user's response
        set_user_response(session_id, answer)
        logger.info("User response stored successfully")
        
        # Get the next question (if available)
        next_question = get_next_question(session_id)
        if next_question:
            logger.info("Found next question after storing response")
        else:
            logger.info("No more questions available after storing response")
        
        return jsonify({
            'success': True,
            'message': 'Answer submitted successfully',
            'has_next_question': next_question is not None,
            'next_question': next_question if next_question else None
        })
    except Exception as e:
        logger.error(f"Error submitting answer: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error submitting answer: {str(e)}'}), 500

@app.route('/api/assessment/result', methods=['GET'])
def get_assessment_result():
    """Get the final assessment result."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        return jsonify({'error': 'No active assessment session'}), 400
    
    try:
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        conv_file = os.path.join(session_dir, f'conversation.json')
        
        if os.path.exists(conv_file):
            # Mark assessment as completed if not already done
            db.complete_assessment(session_id)

            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv_data = json.load(f)
                    conversation = conv_data.get('conversation', [])
                    
                    if conversation:
                        # Try to extract the assessment JSON from the conversation
                        assessment_data = None
                        raw_assessment = None
                        
                        for msg in reversed(conversation):
                            if msg.get('source') == 'assessment_agent':
                                content = msg.get('content', '')
                                if "ASSESSMENT COMPLETE" in content:
                                    raw_assessment = content
                                    # Try to extract JSON
                                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                                    if json_match:
                                        try:
                                            assessment_json = json.loads(json_match.group(1))
                                            assessment_data = assessment_json
                                            break
                                        except Exception as json_err:
                                            logger.error(f"Error parsing assessment JSON: {str(json_err)}")
                        
                        # Return the assessment data
                        return jsonify({
                            'success': True,
                            'complete': True,
                            'assessment': assessment_data.get('assessment') if isinstance(assessment_data, dict) and 'assessment' in assessment_data else assessment_data,
                            'raw_assessment': raw_assessment
                        })
                    else:
                        # Empty conversation file - assessment might still be in progress
                        return jsonify({
                            'success': True,
                            'complete': False,
                            'message': 'Assessment in progress, conversation file exists but is empty.'
                        })
            except Exception as e:
                logger.error(f"Error reading conversation file: {str(e)}")
        
        # Get progress from database
        progress = db.get_session_progress(session_id)
        
        return jsonify({
            'success': True,
            'complete': False,
            'progress': progress,
            'message': 'Assessment in progress. Please continue polling for results.'
        })
    except Exception as e:
        logger.error(f"Error getting assessment result: {str(e)}")
        return jsonify({'error': f'Error getting assessment result: {str(e)}'}), 500

@app.route('/api/assessment/history', methods=['GET'])
def get_assessment_history():
    """Get the complete question and answer history for the current assessment."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        return jsonify({'error': 'No active assessment session'}), 400
    
    try:
        # Get history from database
        history = db.get_assessment_history(session_id)
        
        # Get conversation file if it exists
        session_dir = os.path.join(SESSIONS_DIR, session_id)
        conv_file = os.path.join(session_dir, f'conversation.json')
        conversation = None
        
        if os.path.exists(conv_file):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conversation = json.load(f)
            except Exception as e:
                logger.error(f"Error reading conversation file: {str(e)}")
        
        return jsonify({
            'success': True,
            'history': history,
            'conversation': conversation
        })
    except Exception as e:
        logger.error(f"Error getting assessment history: {str(e)}")
        return jsonify({'error': f'Error getting assessment history: {str(e)}'}), 500

@app.route('/api/session/timing', methods=['GET'])
def get_session_timing():
    """Get timing information for the current session."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
        
    try:
        timing_data = db.get_session_timing(session_id)
        if timing_data:
            return jsonify({
                'success': True,
                'timing': timing_data
            })
        return jsonify({'error': 'No timing data found'}), 404
    except Exception as e:
        logger.error(f"Error getting session timing: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/start', methods=['POST'])
def start_content_creation():
    """Start content creation for a completed assessment session."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        # Check if session_id is provided in the request
        data = request.json
        if data and 'session_id' in data:
            session_id = data['session_id']
        else:
            logger.error("No active assessment session or session_id provided in request")
            return jsonify({'error': 'No active assessment session or session_id provided'}), 400
    
    logger.info(f"Starting content creation for session: {session_id}")
    
    try:
        # Check if content creation is already in progress or complete
        status = db.get_content_creation_status(session_id)
        logger.info(f"Current content creation status: {status}")
        
        # Only prevent if content creation is already completed
        if status and status['status'] == 'completed':
            logger.warning(f"Content creation already completed for session {session_id}")
            return jsonify({
                'success': False,
                'message': "Content creation already completed. View the generated course instead."
            }), 400
            
        # For any other status, we'll restart - including 'started' and 'in_progress'
        # Update status to started in database
        logger.info(f"Resetting content creation for session {session_id}")
        db.start_content_creation(session_id)
        
        # Create a function that will run the content creation asynchronously
        def run_background_content_creation(app_context):
            with app_context:
                async def async_content_creation():
                    try:
                        # Initialize content agent with session ID as run ID
                        agent = CourseContentAgent(run_id=session_id)
                        
                        # Get the conversation file path
                        conv_file = os.path.join(SESSIONS_DIR, session_id, 'conversation.json')
                        
                        if not os.path.exists(conv_file):
                            logger.error(f"Conversation file not found for session {session_id}")
                            db.update_content_creation_status(session_id, 'error')
                            # Store error message in a new field
                            db.store_content_creation_error(session_id, "Assessment conversation file not found")
                            return
                        
                        # Update status to in_progress once we start
                        db.update_content_creation_status(session_id, 'in_progress')
                        
                        # Generate the course
                        course_file = await agent.generate_course(conv_file)
                        
                        # Mark as completed when done
                        db.complete_content_creation(session_id)
                        
                        logger.info(f"Content creation completed for session {session_id}")
                        
                    except Exception as e:
                        logger.error(f"Content creation error: {str(e)}", exc_info=True)
                        db.update_content_creation_status(session_id, 'error')
                        db.store_content_creation_error(session_id, str(e))

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(async_content_creation())
                finally:
                    loop.close()
        
        # Start the background task with app context
        ctx = app.app_context()
        background_thread = Thread(target=run_background_content_creation, args=(ctx,))
        background_thread.daemon = True
        background_thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': "Content creation started in background. Use the status endpoint to check progress."
        })
        
    except Exception as e:
        logger.error(f"Error starting content creation: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error starting content creation: {str(e)}'}), 500

@app.route('/api/content/status', methods=['GET'])
def get_content_creation_status():
    """Get the status of content creation for the current session."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        # Check if session_id is provided in the request query parameters
        session_id = request.args.get('session_id')
        if not session_id:
            # Check if session_id is provided in the request JSON body
            data = request.get_json(silent=True)
            if data and 'session_id' in data:
                session_id = data['session_id']
            else:
                return jsonify({'error': 'No active session or session_id provided'}), 400
        
    try:
        # Get content creation status from database
        status = db.get_content_creation_status(session_id)
        
        if not status:
            return jsonify({'error': 'No content creation status found'}), 404
            
        # Get progress details from intermediate files
        progress = {
            'status': status['status'],
            'started_at': status['content_creation_start'],
            'completed_at': status['content_creation_finish'],
            'error_message': status.get('error_message', None),  # Add error message if it exists
            'modules': []
        }
        
        # Check intermediate directory for progress
        intermediate_dir = os.path.join(RUNS_DIR, session_id, 'intermediate')
        if os.path.exists(intermediate_dir):
            # Check for course plan
            if os.path.exists(os.path.join(intermediate_dir, 'course_plan.json')):
                with open(os.path.join(intermediate_dir, 'course_plan.json'), 'r') as f:
                    course_plan = json.load(f)
                    for module in course_plan['modules']:
                        module_progress = {
                            'name': module['name'],
                            'chapters': [],
                            'has_summary': os.path.exists(os.path.join(intermediate_dir, f"summary_{module['name']}.json")),
                            'has_quiz': os.path.exists(os.path.join(intermediate_dir, f"quiz_{module['name']}.json"))
                        }
                        
                        # Check chapter progress
                        for chapter in module['chapters']:
                            chapter_progress = {
                                'title': chapter['title'],
                                'has_plan': os.path.exists(os.path.join(intermediate_dir, f"chapter_plan_{module['name']}_{chapter['title']}.json")),
                                'pages_completed': len(glob.glob(os.path.join(intermediate_dir, f"page_{module['name']}_{chapter['title']}_*.json")))
                            }
                            module_progress['chapters'].append(chapter_progress)
                            
                        progress['modules'].append(module_progress)
        
        return jsonify({
            'success': True,
            'progress': progress
        })
        
    except Exception as e:
        logger.error(f"Error getting content creation status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/content/retry', methods=['POST'])
def retry_content_creation():
    """Retry content creation for a session regardless of its current status."""
    session_id = session.get('assessment_session_id')
    
    if not session_id:
        # Check if session_id is provided in the request
        data = request.json
        if data and 'session_id' in data:
            session_id = data['session_id']
        else:
            logger.error("No session_id provided in request")
            return jsonify({'error': 'No session ID provided'}), 400
    
    logger.info(f"Retrying content creation for session: {session_id}")
    
    try:
        # Check current status but allow retry regardless
        status = db.get_content_creation_status(session_id)
        
        if not status:
            logger.error(f"No content creation status found for session {session_id}")
            return jsonify({'error': 'No content creation status found'}), 404
        
        logger.info(f"Current status before retry: {status}")
            
        # Update status to started in database (force restart)
        db.start_content_creation(session_id)
        
        # Create a function that will run the content creation asynchronously
        def run_background_content_creation(app_context):
            with app_context:
                async def async_content_creation():
                    try:
                        # Initialize content agent with session ID as run ID
                        agent = CourseContentAgent(run_id=session_id)
                        
                        # Get the conversation file path
                        conv_file = os.path.join(SESSIONS_DIR, session_id, 'conversation.json')
                        
                        if not os.path.exists(conv_file):
                            logger.error(f"Conversation file not found for session {session_id}")
                            db.update_content_creation_status(session_id, 'error')
                            db.store_content_creation_error(session_id, "Assessment conversation file not found")
                            return
                        
                        # Update status to in_progress once we start
                        db.update_content_creation_status(session_id, 'in_progress')
                        
                        # Generate the course
                        course_file = await agent.generate_course(conv_file)
                        
                        # Mark as completed when done
                        db.complete_content_creation(session_id)
                        
                        logger.info(f"Content creation completed for session {session_id}")
                        
                    except Exception as e:
                        logger.error(f"Content creation error: {str(e)}", exc_info=True)
                        db.update_content_creation_status(session_id, 'error')
                        db.store_content_creation_error(session_id, str(e))

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(async_content_creation())
                finally:
                    loop.close()
        
        # Start the background task with app context
        ctx = app.app_context()
        background_thread = Thread(target=run_background_content_creation, args=(ctx,))
        background_thread.daemon = True
        background_thread.start()
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': "Content creation restarted. Use the status endpoint to check progress."
        })
        
    except Exception as e:
        logger.error(f"Error retrying content creation: {str(e)}", exc_info=True)
        return jsonify({'error': f'Error retrying content creation: {str(e)}'}), 500

@app.route('/api/assessment/sessions', methods=['GET'])
def get_assessment_sessions():
    """Get a list of all completed assessment sessions with content creation status."""
    try:
        # Get all sessions with assessment_status='completed'
        sessions = db.get_completed_assessment_sessions()
        return jsonify({
            'success': True,
            'sessions': sessions
        })
    except Exception as e:
        logger.error(f"Error getting assessment sessions: {str(e)}")
        return jsonify({'error': str(e)}), 500

def init_db():
    """Initialize the database tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create session timing table with assessment and content creation status
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS session_timing (
        session_id TEXT PRIMARY KEY,
        assessment_start TIMESTAMP,
        assessment_finish TIMESTAMP,
        content_creation_start TIMESTAMP,
        content_creation_finish TIMESTAMP,
        assessment_status TEXT CHECK(assessment_status IN ('started', 'in_progress', 'completed')) DEFAULT 'started',
        content_creation_status TEXT CHECK(content_creation_status IN ('not_started', 'started', 'in_progress', 'completed', 'error')) DEFAULT 'not_started',
        content_creation_error TEXT,
        FOREIGN KEY (session_id) REFERENCES assessment_data (session_id)
    )
    ''')
    
    # Check if content_creation_error column exists, add it if it doesn't
    cursor.execute("PRAGMA table_info(session_timing)")
    columns = [info[1] for info in cursor.fetchall()]
    if 'content_creation_error' not in columns:
        cursor.execute('ALTER TABLE session_timing ADD COLUMN content_creation_error TEXT')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    logger.info("Starting Flask server")
    init_db()  # Initialize database tables
    # Use debug mode only in development
    is_debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=is_debug, port=5000, threaded=True)