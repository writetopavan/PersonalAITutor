import sqlite3
import logging
from datetime import datetime
import os
import sys

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# Import config
from config.config import BASE_DIR, BASE_DATA_DIR, DB_PATH, LOG_LEVEL, LOG_FORMAT

# Configure logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('database.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"DB_PATH set to: {DB_PATH}")

class AssessmentDatabase:
    def __init__(self, db_name=None):
        if db_name is None:
            # Use path from configuration
            self.db_name = DB_PATH
        else:
            self.db_name = db_name
        logger.info(f"Using database at: {self.db_name}")
        self.init_database()

    def get_connection(self):
        """Create and return a database connection."""
        return sqlite3.connect(self.db_name)

    def init_database(self):
        """Initialize the database tables."""
        logger.info("Initializing assessment database")
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create assessment data table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS assessment_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question TEXT,
            answer TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create session timing table
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
        
        # Create error tracking table for detailed error logging
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            error_type TEXT,
            error_message TEXT,
            error_step TEXT,
            retry_count INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES session_timing (session_id)
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.debug("Database initialization complete")

    def store_question(self, session_id, question):
        """Store a question in the database."""
        logger.info(f"Storing question for session {session_id}")
        logger.debug(f"Question content: {question[:100]}...")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO assessment_data (session_id, question, answer) VALUES (?, ?, ?)",
            (session_id, question, None)
        )
        conn.commit()
        
        # Get the ID of the stored question for logging
        cursor.execute(
            "SELECT id FROM assessment_data WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logger.info(f"Question stored with ID: {result[0]}")
        else:
            logger.warning("Question was not stored properly")

    def store_answer(self, session_id, answer):
        """Store an answer in the database."""
        logger.info(f"Storing answer for session {session_id}")
        logger.debug(f"Answer content: {answer[:100]}...")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get the ID of the oldest unanswered question
        cursor.execute(
            "SELECT id FROM assessment_data WHERE session_id = ? AND answer IS NULL ORDER BY id ASC LIMIT 1",
            (session_id,)
        )
        result = cursor.fetchone()
        
        if result:
            cursor.execute(
                "UPDATE assessment_data SET answer = ? WHERE id = ?",
                (answer, result[0])
            )
            logger.info(f"Answer stored for question ID: {result[0]}")
        else:
            logger.warning(f"No unanswered questions found for session {session_id}")
        
        conn.commit()
        conn.close()

    def get_last_message(self, session_id):
        """Get the last answered message for the specified session."""
        logger.debug(f"Getting last message for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get counts of total and answered questions
        cursor.execute(
            "SELECT COUNT(*) FROM assessment_data WHERE session_id = ?",
            (session_id,)
        )
        total_questions = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM assessment_data WHERE session_id = ? AND answer IS NOT NULL",
            (session_id,)
        )
        answered_questions = cursor.fetchone()[0]
        
        # Return None if no questions/answers or incomplete
        if total_questions == 0 or answered_questions == 0 or answered_questions < total_questions:
            conn.close()
            logger.debug(f"Not all questions answered: {answered_questions}/{total_questions}")
            return None
        
        # Get the last answer
        cursor.execute(
            "SELECT question, answer FROM assessment_data WHERE session_id = ? AND answer IS NOT NULL ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result and result[1]:
            logger.debug(f"All questions answered. Found last message: {result[1][:50]}...")
            return result[1]
        
        logger.debug("No answered messages found")
        return None

    def get_next_question(self, session_id):
        """Get the next unanswered question for a session."""
        logger.debug(f"Getting next question for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT question FROM assessment_data WHERE session_id = ? AND answer IS NULL ORDER BY id ASC LIMIT 1",
            (session_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        if result:
            logger.info(f"Found next question: {result[0][:50]}...")
            return result[0]
        
        logger.debug("No unanswered questions found")
        return None

    def get_answer_for_question(self, session_id):
        """Get the assessment result, looking for the 'ASSESSMENT COMPLETE' marker."""
        logger.debug(f"Getting assessment result for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check answers first
        cursor.execute(
            "SELECT answer FROM assessment_data WHERE session_id = ? AND answer LIKE '%ASSESSMENT COMPLETE%' ORDER BY id DESC LIMIT 1",
            (session_id,)
        )
        result = cursor.fetchone()
        
        if not result:
            # Then check questions
            cursor.execute(
                "SELECT question FROM assessment_data WHERE session_id = ? AND question LIKE '%ASSESSMENT COMPLETE%' ORDER BY id DESC LIMIT 1",
                (session_id,)
            )
            result = cursor.fetchone()
        
        conn.close()
        
        if result:
            logger.info("Found assessment result with ASSESSMENT COMPLETE marker")
            return result[0]
        
        logger.debug("No assessment with ASSESSMENT COMPLETE marker found, returning last message")
        return self.get_last_message(session_id)

    def update_session_timing(self, session_id, **kwargs):
        """Update session timing information."""
        logger.debug(f"Updating session timing for {session_id}: {kwargs}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Build the update query dynamically based on provided kwargs
        update_fields = []
        values = []
        for key, value in kwargs.items():
            update_fields.append(f"{key} = ?")
            values.append(value)
        
        if update_fields:
            query = f"UPDATE session_timing SET {', '.join(update_fields)} WHERE session_id = ?"
            values.append(session_id)
            
            cursor.execute(query, values)
            conn.commit()
        
        conn.close()

    def init_session_timing(self, session_id):
        """Initialize a new session timing record."""
        logger.info(f"Initializing session timing for {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO session_timing 
                (session_id, assessment_start, assessment_status, content_creation_status) 
                VALUES (?, ?, ?, ?)
                """,
                (session_id, datetime.utcnow(), 'started', 'not_started')
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error initializing session timing: {str(e)}")
            raise
        finally:
            conn.close()

    def get_session_progress(self, session_id):
        """Get the progress of questions and answers for a session."""
        logger.debug(f"Getting session progress for {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Count total questions
            cursor.execute(
                "SELECT COUNT(*) FROM assessment_data WHERE session_id = ?",
                (session_id,)
            )
            total_records = cursor.fetchone()[0]
            
            # Count answered questions
            cursor.execute(
                "SELECT COUNT(*) FROM assessment_data WHERE session_id = ? AND answer IS NOT NULL",
                (session_id,)
            )
            answered_records = cursor.fetchone()[0]
            
            return {
                'total': total_records,
                'answered': answered_records
            }
        finally:
            conn.close()

    def get_session_timing(self, session_id):
        """Get all timing information for a session."""
        logger.debug(f"Getting session timing for {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT 
                    assessment_start,
                    assessment_finish,
                    content_creation_start,
                    content_creation_finish,
                    assessment_status,
                    content_creation_status
                FROM session_timing 
                WHERE session_id = ?
                """,
                (session_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return {
                    'assessment_start': row[0],
                    'assessment_finish': row[1],
                    'content_creation_start': row[2],
                    'content_creation_finish': row[3],
                    'assessment_status': row[4],
                    'content_creation_status': row[5]
                }
            return None
        finally:
            conn.close()

    def update_assessment_status(self, session_id, status):
        """Update the assessment status for a session."""
        logger.info(f"Updating assessment status to {status} for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE session_timing SET assessment_status = ? WHERE session_id = ?",
                (status, session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def complete_assessment(self, session_id):
        """Mark an assessment as completed with finish time."""
        logger.info(f"Marking assessment as completed for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                UPDATE session_timing 
                SET assessment_finish = ?, assessment_status = 'completed' 
                WHERE session_id = ? AND assessment_finish IS NULL
                """,
                (datetime.utcnow(), session_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_assessment_history(self, session_id):
        """Get the complete question and answer history for a session."""
        logger.debug(f"Getting assessment history for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT id, question, answer, timestamp 
                FROM assessment_data 
                WHERE session_id = ? 
                ORDER BY id ASC
                """,
                (session_id,)
            )
            rows = cursor.fetchall()
            
            history = [{
                'id': row[0],
                'question': row[1],
                'answer': row[2],
                'timestamp': row[3]
            } for row in rows]
            
            return history
        finally:
            conn.close()

    def start_content_creation(self, session_id: str):
        """Start or restart content creation for a session."""
        logger.info(f"Starting content creation for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, check if the error_message column exists
            cursor.execute("PRAGMA table_info(session_timing)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # If there's an error_message column, clear it
            if 'error_message' in column_names:
                cursor.execute("""
                    UPDATE session_timing 
                    SET content_creation_status = 'started',
                        content_creation_start = CURRENT_TIMESTAMP,
                        content_creation_finish = NULL,
                        error_message = NULL
                    WHERE session_id = ?
                """, (session_id,))
            else:
                cursor.execute("""
                    UPDATE session_timing 
                    SET content_creation_status = 'started',
                        content_creation_start = CURRENT_TIMESTAMP,
                        content_creation_finish = NULL
                    WHERE session_id = ?
                """, (session_id,))
            
            conn.commit()
            logger.info(f"Successfully reset content creation status for session {session_id}")
        except Exception as e:
            logger.error(f"Error starting content creation in database: {str(e)}")
            raise
        finally:
            conn.close()

    def complete_content_creation(self, session_id: str):
        """Mark content creation as completed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE session_timing 
                SET content_creation_status = 'completed',
                    content_creation_finish = CURRENT_TIMESTAMP
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
        finally:
            conn.close()

    def update_content_creation_status(self, session_id: str, status: str):
        """Update the content creation status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE session_timing 
                SET content_creation_status = ?
                WHERE session_id = ?
            """, (status, session_id))
            conn.commit()
        finally:
            conn.close()

    def get_content_creation_status(self, session_id: str) -> dict:
        """Get the content creation status and timing information."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, check if the error_message column exists
            cursor.execute("PRAGMA table_info(session_timing)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_error_column = 'error_message' in column_names
            
            # Select appropriate columns based on schema
            if has_error_column:
                cursor.execute("""
                    SELECT content_creation_status, content_creation_start, content_creation_finish, error_message
                    FROM session_timing 
                    WHERE session_id = ?
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT content_creation_status, content_creation_start, content_creation_finish
                    FROM session_timing 
                    WHERE session_id = ?
                """, (session_id,))
            
            row = cursor.fetchone()
            if row:
                result = {
                    'status': row[0],
                    'content_creation_start': row[1],
                    'content_creation_finish': row[2],
                }
                
                # Add error_message if column exists
                if has_error_column and len(row) > 3:
                    result['error_message'] = row[3]
                
                return result
            return None
        finally:
            conn.close()

    def store_content_creation_error(self, session_id: str, error_message: str, error_step: str = None, retry_count: int = None):
        """Store error message for content creation process with detailed tracking."""
        logger.error(f"Storing content creation error for session {session_id}: {error_message}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # First, check if the error_message column exists in session_timing
            cursor.execute("PRAGMA table_info(session_timing)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            
            # Add the column if it doesn't exist
            if 'error_message' not in column_names:
                cursor.execute("ALTER TABLE session_timing ADD COLUMN error_message TEXT")
                logger.info("Added error_message column to session_timing table")
            
            # Store the error message in session_timing
            cursor.execute("""
                UPDATE session_timing 
                SET error_message = ?
                WHERE session_id = ?
            """, (error_message[:500] if error_message else None, session_id))
            
            # Also store detailed error info in error_tracking table
            cursor.execute("""
                INSERT INTO error_tracking 
                (session_id, error_type, error_message, error_step, retry_count) 
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_id, 
                "content_creation", 
                error_message, 
                error_step, 
                retry_count
            ))
            
            conn.commit()
            logger.info(f"Stored detailed error information for session {session_id}")
        except Exception as e:
            logger.error(f"Error while storing error information: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
    
    def get_error_history(self, session_id: str):
        """Get the error history for a session."""
        logger.debug(f"Getting error history for session {session_id}")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT id, error_type, error_message, error_step, retry_count, timestamp
                FROM error_tracking
                WHERE session_id = ?
                ORDER BY timestamp DESC
            """, (session_id,))
            
            rows = cursor.fetchall()
            errors = []
            
            for row in rows:
                errors.append({
                    'id': row[0],
                    'error_type': row[1],
                    'error_message': row[2],
                    'error_step': row[3],
                    'retry_count': row[4],
                    'timestamp': row[5]
                })
            
            return errors
        finally:
            conn.close()

    def get_completed_assessment_sessions(self):
        """Get all sessions with completed assessments and their content creation status."""
        logger.debug("Fetching all completed assessment sessions")
        
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # First, check if the error_message column exists
            cursor.execute("PRAGMA table_info(session_timing)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]
            has_error_column = 'error_message' in column_names
            
            # Construct the query based on available columns
            if has_error_column:
                query = """
                    SELECT 
                        session_id, 
                        assessment_start, 
                        assessment_finish, 
                        content_creation_status, 
                        content_creation_start, 
                        content_creation_finish,
                        error_message
                    FROM session_timing 
                    WHERE assessment_status = 'completed'
                    ORDER BY assessment_finish DESC
                """
            else:
                query = """
                    SELECT 
                        session_id, 
                        assessment_start, 
                        assessment_finish, 
                        content_creation_status, 
                        content_creation_start, 
                        content_creation_finish
                    FROM session_timing 
                    WHERE assessment_status = 'completed'
                    ORDER BY assessment_finish DESC
                """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            sessions = []
            
            for row in rows:
                # Get assessment result for this session
                assessment_result = self.get_assessment_result(row[0])
                
                session_data = {
                    'session_id': row[0],
                    'assessment_start': row[1],
                    'assessment_finish': row[2],
                    'content_creation_status': row[3],
                    'content_creation_start': row[4],
                    'content_creation_finish': row[5],
                    'error_message': row[6] if has_error_column and len(row) > 6 else None,
                    'assessment_summary': assessment_result.get('summary', None) if assessment_result else None
                }
                sessions.append(session_data)
            
            return sessions
        finally:
            conn.close()

    def get_assessment_result(self, session_id):
        """Get the assessment result summary from the conversation file."""
        try:
            import os
            import json
            import re
            
            session_dir = os.path.join('data', 'sessions', session_id)
            conv_file = os.path.join(session_dir, f'conversation.json')
            
            if os.path.exists(conv_file):
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv_data = json.load(f)
                    conversation = conv_data.get('conversation', [])
                    
                    # Try to extract the assessment information
                    for msg in reversed(conversation):
                        if msg.get('source') == 'assessment_agent':
                            content = msg.get('content', '')
                            if "ASSESSMENT COMPLETE" in content:
                                # Multiple approaches to extract JSON
                                assessment_data = None
                                
                                # Approach 1: Try code block format
                                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                                if json_match:
                                    try:
                                        json_str = json_match.group(1).strip()
                                        assessment_json = json.loads(json_str)
                                        assessment_data = assessment_json.get('assessment', assessment_json)
                                    except json.JSONDecodeError as e:
                                        logger.debug(f"Failed to parse JSON from code block: {str(e)}")
                                
                                # Approach 2: Try to find JSON between curly braces if first approach failed
                                if not assessment_data:
                                    json_match = re.search(r'\{(?:[^{}]|(?R))*\}', content)
                                    if json_match:
                                        try:
                                            json_str = json_match.group(0)
                                            assessment_json = json.loads(json_str)
                                            assessment_data = assessment_json.get('assessment', assessment_json)
                                        except json.JSONDecodeError as e:
                                            logger.debug(f"Failed to parse JSON from curly braces: {str(e)}")
                                
                                # Approach 3: Try to extract key-value pairs if JSON parsing failed
                                if not assessment_data:
                                    # Look for key-value patterns
                                    skill_level = re.search(r'skill[_ ]level["\s:]+([^,\n}"]+)', content, re.I)
                                    topic = re.search(r'topic["\s:]+([^,\n}"]+)', content, re.I)
                                    learning_path = re.search(r'learning[_ ]path["\s:]+([^,\n}"]+)', content, re.I)
                                    
                                    assessment_data = {
                                        'skill_level': skill_level.group(1).strip() if skill_level else 'Unknown',
                                        'topic': topic.group(1).strip() if topic else 'Subject assessment',
                                        'learning_path': learning_path.group(1).strip() if learning_path else ''
                                    }
                                
                                if assessment_data:
                                    # Create summary with safe gets and proper truncation
                                    summary = {
                                        'skill_level': str(assessment_data.get('skill_level', 'Unknown')),
                                        'topic': str(assessment_data.get('topic', 'Subject assessment')),
                                        'learning_path': str(assessment_data.get('learning_path', ''))[:100] + '...' if len(str(assessment_data.get('learning_path', ''))) > 100 else str(assessment_data.get('learning_path', ''))
                                    }
                                    return {'assessment': assessment_data, 'summary': summary}
                                
                                logger.warning(f"Could not extract assessment data from content for session {session_id}")
            return None
        except Exception as e:
            logger.error(f"Error getting assessment result for session {session_id}: {str(e)}")
            return None

# Create a singleton instance
db = AssessmentDatabase() 