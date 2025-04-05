import json
import os
import asyncio
import logging
import sys
import traceback
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_core import CancellationToken
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.base import TaskResult
from autogen_core.model_context import BufferedChatCompletionContext

# Add project root to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Import config
from config.config import (
    BASE_DIR, BASE_DATA_DIR, RUNS_DIR, SESSIONS_DIR, 
    LOG_LEVEL, LOG_FORMAT, OPENAI_API_KEY
)

# Import database
from AItution.backend.database import AssessmentDatabase

# Ensure directories exist
os.makedirs(RUNS_DIR, exist_ok=True)
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler('course_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"BASE_DATA_DIR set to: {BASE_DATA_DIR}")
logger.info(f"RUNS_DIR set to: {RUNS_DIR}")
logger.info(f"SESSIONS_DIR set to: {SESSIONS_DIR}")

@dataclass
class QuizQuestion:
    question_type: str
    question: str
    multiple_choice: List[str]
    answer: str

@dataclass
class ChapterPage:
    title: str
    description: str
    content: str  # HTML content

@dataclass
class Chapter:
    title: str
    description: str
    pages: List[ChapterPage]  # List of pages in the chapter

@dataclass
class Module:
    name: str
    description: str
    chapters: List[Chapter]
    summary: str
    quiz: List[QuizQuestion]

@dataclass
class Course:
    name: str
    description: str
    modules: List[Module]
    created_at: str

class CourseContentAgent:
    def __init__(self, run_id: Optional[str] = None, session_id: Optional[str] = None):
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(RUNS_DIR, self.run_id)
        self.course_data_dir = os.path.join(self.run_dir, "courses")
        self.session_id = session_id
        os.makedirs(self.course_data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.run_dir, "intermediate"), exist_ok=True)
        logger.info(f"Initialized CourseContentAgent with run_id: {self.run_id}")
        logger.info(f"Created directories: {self.run_dir}, {self.course_data_dir}")
        
        # Initialize database connection
        self.db = AssessmentDatabase()
        
        # Verify session_id and error tracking tables if provided
        if self.session_id:
            self._verify_session_and_tables()
        
        # Initialize OpenAI client
        self.model_client = OpenAIChatCompletionClient(
            model="gpt-4o",
            api_key=OPENAI_API_KEY
        )
        
        # Create specialized agents
        self.planning_agent = AssistantAgent(
            "course_planner",
            model_client=self.model_client,
            system_message="""You are a course planning expert. You are expert at creating course structure for which student will pay for.
            Course should be structured in a way that is easy to understand, detailed and comprehensive. no short cuts. You are professional at this.
            Your role is to:
            1. Analyze the assessment conversation to identify:
               - The specific topic the student wants to learn
               - Their current skill level in that topic
               - Any specific areas they want to focus on
            2. Create a detailed course plan that is SPECIFICALLY tailored to:
               - The exact topic from the assessment (not defaulting to Python or any other topic)
               - The student's demonstrated skill level
               - Their specific learning needs and goals
            3. Ensure the plan aligns with the student's skill level and learning goals
            4. Output the plan in JSON format with the following structure:
            {
                "course_name": "string (must reflect the actual topic from assessment)",
                "course_description": "string (must be specific to the assessed topic and level)",
                "modules": [
                    {
                        "name": "string",
                        "description": "string",
                        "chapters": [
                            {
                                "title": "string",
                                "description": "string"
                            }
                        ]
                    }
                ]
            }
            5. Address any feedback from the reviewer and improve the plan accordingly
            
            IMPORTANT: Never default to creating a Python programming course unless the assessment specifically indicates the student wants to learn Python. The course must be based on the topic identified in the assessment conversation."""
        )

        # Create course plan reviewer agent
        self.course_plan_reviewer = AssistantAgent(
            "course_plan_reviewer",
            model_client=self.model_client,
            system_message="""You are a course planning expert. You are expert at reviewing course plans.
            The plan should be structured in a way that is easy to understand, detailed and comprehensive. no short cuts.
            You are professional at this. This is going to be a paid course so ensure you are not missing any important details.
            Your role is to:
            1. Review the course plan thoroughly
            2. Check for completeness, clarity, and educational value
            3. Ensure all necessary topics are covered
            4. Verify the progression of topics is logical
            5. Provide specific feedback for improvements
            6. Respond with 'APPROVE' when the plan meets all requirements
            7. If there are issues, provide detailed feedback for the planner to address"""
        )
        
        self.content_agent = AssistantAgent(
            "content_creator",
            model_client=self.model_client,
            system_message="""You are an expert content creator. Your role is to:
            1. Create engaging and educational content for each chapter
            2. Format the content in HTML with proper structure and styling
            3. Include examples, explanations, and practice exercises
            4. Ensure content is appropriate for the student's skill level
            5. Output the content in HTML format""",
            model_context=BufferedChatCompletionContext(buffer_size=2)
        )
        
        self.quiz_agent = AssistantAgent(
            "quiz_creator",
            model_client=self.model_client,
            system_message="""You are a quiz creation expert. Your role is to:
            1. Create comprehensive quiz questions for each module
            2. Ensure questions test understanding of key concepts
            3. Provide clear multiple-choice options
            4. Output quiz questions in JSON format with the following structure:
            {
                "questions": [
                    {
                        "question_type": "multiple_choice",
                        "question": "string",
                        "multiple_choice": ["string"],
                        "answer": "string"
                    }
                ]
            }"""
        )
        
        self.summary_agent = AssistantAgent(
            "summary_creator",
            model_client=self.model_client,
            system_message="""You are a content summarization expert. Your role is to:
            1. Create concise and informative summaries for each module
            2. Highlight key concepts and learning outcomes
            3. Connect concepts across chapters
            4. Output summaries in clear, structured text format"""
        )

        self.chapter_planning_agent = AssistantAgent(
            "chapter_planner",
            model_client=self.model_client,
            system_message="""You are a chapter planning expert. Your role is to:
            1. Analyze the chapter description and module context
            2. Break down the chapter into logical pages/sections
            3. Create a detailed plan for each page
            4. Output the plan in JSON format with the following structure:
            {
                "pages": [
                    {
                        "title": "string",
                        "description": "string",
                        "learning_objectives": ["string"],
                        "key_concepts": ["string"]
                    }
                ]
            }
            5. Ensure each page builds upon previous pages
            6. Make sure all aspects of the chapter description are covered"""
        )

        # Add semaphore for rate limiting
        self.api_semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent operations

    def _verify_session_and_tables(self) -> None:
        """Verify the session_id exists and error tracking tables are properly set up."""
        logger.info(f"Verifying session_id '{self.session_id}' and error tracking tables")
        
        # Check if session exists in the database
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            # Check if session exists in session_timing
            cursor.execute(
                "SELECT COUNT(*) FROM session_timing WHERE session_id = ?",
                (self.session_id,)
            )
            session_count = cursor.fetchone()[0]
            
            if session_count == 0:
                logger.warning(f"Session '{self.session_id}' not found in database. Creating session record.")
                self.db.init_session_timing(self.session_id)
            
            # Check if error_tracking table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='error_tracking'")
            has_error_table = cursor.fetchone() is not None
            
            if not has_error_table:
                logger.warning("Error tracking table not found. Initializing database tables.")
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
                logger.info("Error tracking table created")
            
            logger.info(f"Session and database tables verified for '{self.session_id}'")
        
        except Exception as e:
            logger.error(f"Error verifying session and tables: {str(e)}")
        finally:
            conn.close()

    async def create_course_plan(self, assessment_conversation: str, max_retries: int = 3) -> Course:
        """Create a course plan using the planning agent and reviewer team with retry logic."""
        logger.info("Starting course plan creation")
        
        # Check if intermediate result exists
        intermediate_file = os.path.join(self.run_dir, "intermediate", "course_plan.json")
        if os.path.exists(intermediate_file):
            logger.info(f"Found existing course plan at {intermediate_file}")
            with open(intermediate_file, 'r') as f:
                plan_json = json.load(f)
                return self._create_course_from_plan(plan_json)

        retry_count = 0
        base_delay = 2  # Base delay in seconds
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempt {retry_count + 1}/{max_retries} to create course plan")
                # Define termination condition for team chat
                text_termination = TextMentionTermination("APPROVE")
                
                # Create team with planner and reviewer
                team = RoundRobinGroupChat(
                    [self.planning_agent, self.course_plan_reviewer],
                    termination_condition=text_termination
                )
                
                # Initial task for the team
                task = f"""Based on this assessment conversation, create a detailed course plan:
                {assessment_conversation}
                
                The planner will create the plan, and the reviewer will provide feedback.
                The process continues until the reviewer approves the plan.
                Output the final plan in the specified JSON format."""
                
                # Reset the team for a new task
                await team.reset()
                
                # Run the team chat with streaming
                final_result = ""
                async for message in team.run_stream(task=task):  # type: ignore
                    if isinstance(message, TaskResult):
                        print("Stop Reason:", message.stop_reason)
                        break
                    else:
                        print(message.content)
                
                # Extract the final approved plan
                plan_json = None
                for data in reversed(message.messages):
                    if data.source == "course_planner":
                        plan_json = self._extract_json_from_result(data.content)
                        break

                # Save intermediate result
                with open(intermediate_file, "w") as f:
                    json.dump(plan_json, f, indent=2)

                return self._create_course_from_plan(plan_json)

            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Failed to create course plan after {max_retries} attempts. Error: {str(e)}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Retry {retry_count}/{max_retries} for course plan creation after {delay} seconds. Error: {str(e)}")
                await asyncio.sleep(delay)

    def _create_course_from_plan(self, plan_json: Dict) -> Course:
        """Create a Course object from the plan JSON."""
        logger.info(f"Creating course: {plan_json['course_name']}")
        course = Course(
            name=plan_json["course_name"],
            description=plan_json["course_description"],
            modules=[],
            created_at=datetime.now().isoformat()
        )
        
        for module_data in plan_json["modules"]:
            logger.info(f"Creating module: {module_data['name']}")
            # Create chapters list from the module data
            chapters = [
                Chapter(
                    title=chapter_data["title"],
                    description=chapter_data["description"],
                    pages=[]  # Pages will be generated later
                )
                for chapter_data in module_data["chapters"]
            ]
            
            module = Module(
                name=module_data["name"],
                description=module_data["description"],
                chapters=chapters,
                summary="",
                quiz=[]
            )
            course.modules.append(module)
        
        return course

    async def plan_chapter_pages(self, module: Module, chapter: Chapter, max_retries: int = 3) -> List[ChapterPage]:
        """Plan the pages for a chapter using the chapter planning agent with retry logic."""
        logger.info(f"Planning pages for chapter '{chapter.title}' in module '{module.name}'")
        
        # Check if intermediate result exists
        intermediate_file = os.path.join(self.run_dir, "intermediate", f"chapter_plan_{module.name}_{chapter.title}.json")
        if os.path.exists(intermediate_file):
            logger.info(f"Found existing chapter plan at {intermediate_file}")
            with open(intermediate_file, 'r') as f:
                plan_data = json.load(f)
                return [ChapterPage(**page) for page in plan_data["pages"]]

        retry_count = 0
        base_delay = 2  # Base delay in seconds
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempt {retry_count + 1}/{max_retries} to plan pages for chapter '{chapter.title}'")
                task = f"""Create a detailed plan for the chapter '{chapter.title}' in module '{module.name}'.
                Module description: {module.description}
                Chapter description: {chapter.description}
                
                Break down the chapter into logical pages and provide details for each page.
                Output the plan in the specified JSON format."""
                
                response = await self.chapter_planning_agent.on_messages(
                    [TextMessage(content=task, source="user")],
                    cancellation_token=CancellationToken()
                )
                result = response.chat_message.content
                plan_json = self._extract_json_from_result(result)
                
                # Create ChapterPage objects with empty content
                pages = [
                    ChapterPage(
                        title=page_data["title"],
                        description=page_data["description"],
                        content=""  # Content will be generated later
                    )
                    for page_data in plan_json["pages"]
                ]

                # Save intermediate result
                with open(intermediate_file, 'w') as f:
                    json.dump({"pages": [page.__dict__ for page in pages]}, f, indent=2)

                return pages

            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Failed to plan pages for chapter '{chapter.title}' after {max_retries} attempts. Error: {str(e)}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Retry {retry_count}/{max_retries} for chapter page planning after {delay} seconds. Error: {str(e)}")
                await asyncio.sleep(delay)

    async def generate_page_content(self, module: Module, chapter: Chapter, page: ChapterPage, max_retries: int = 3) -> ChapterPage:
        """Generate content for a specific page using the content agent with retry logic."""
        logger.info(f"Generating content for page '{page.title}' in chapter '{chapter.title}' of module '{module.name}'")
        
        # Check if intermediate result exists
        intermediate_file = os.path.join(self.run_dir, "intermediate", f"page_{module.name}_{chapter.title}_{page.title}.json")
        if os.path.exists(intermediate_file):
            logger.info(f"Found existing page content at {intermediate_file}")
            with open(intermediate_file, 'r') as f:
                page_data = json.load(f)
                return ChapterPage(**page_data)

        retry_count = 0
        base_delay = 1  # Base delay in seconds
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempt {retry_count + 1}/{max_retries} to generate content for page '{page.title}'")
                task = f"""Create content for the page '{page.title}' in chapter '{chapter.title}' of module '{module.name}'.
                Module description: {module.description}
                Chapter description: {chapter.description}
                Page description: {page.description}
                
                Create engaging HTML content with proper structure and styling that fulfills the page description.
                Include examples, explanations, and practice exercises.
                End with 'CONTENT_COMPLETE'."""
                
                response = await self.content_agent.on_messages(
                    [TextMessage(content=task, source="user")],
                    cancellation_token=CancellationToken()
                )
                result = response.chat_message.content
                content = self._extract_html_from_result(result)
                
                page = ChapterPage(
                    title=page.title,
                    description=page.description,
                    content=content
                )

                # Save intermediate result
                with open(intermediate_file, 'w') as f:
                    json.dump(page.__dict__, f, indent=2)

                return page

            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Failed to generate content for page '{page.title}' after {max_retries} attempts. Error: {str(e)}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Retry {retry_count}/{max_retries} for page '{page.title}' after {delay} seconds. Error: {str(e)}")
                await asyncio.sleep(delay)

    def _serialize_dataclass(self, obj):
        """Helper method to serialize dataclass objects to dictionary."""
        if hasattr(obj, '__dict__'):
            return {k: self._serialize_dataclass(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, list):
            return [self._serialize_dataclass(item) for item in obj]
        else:
            return obj

    async def generate_chapter_content(self, module: Module, chapter_title: str, max_retries: int = 3) -> Optional[Chapter]:
        """Generate content for a specific chapter using the content agent with graceful failure handling."""
        logger.info(f"Generating content for chapter '{chapter_title}' in module '{module.name}'")
        
        try:
            # Find the chapter object
            chapter = next((ch for ch in module.chapters if ch.title == chapter_title), None)
            if not chapter:
                logger.error(f"Chapter {chapter_title} not found in module {module.name}")
                return None  # Return None instead of raising error
            
            # First plan the pages
            try:
                planned_pages = await self.plan_chapter_pages(module, chapter)
                if not planned_pages:
                    logger.error(f"No pages planned for chapter '{chapter_title}'")
                    return None
                
                # Initialize pages list with planned pages
                chapter.pages = []
                
                # Generate content for each planned page
                for page in planned_pages:
                    try:
                        page_content = await self.generate_page_content(module, chapter, page)
                        if page_content:
                            chapter.pages.append(page_content)
                        else:
                            logger.warning(f"Skipping failed page '{page.title}' in chapter '{chapter_title}'")
                    except Exception as e:
                        logger.error(f"Failed to generate content for page '{page.title}': {str(e)}")
                        continue
                
                # Save intermediate progress if we have any pages
                if chapter.pages:
                    self._save_chapter_content(chapter, module.name)
                
                return chapter
                
            except Exception as e:
                logger.error(f"Failed to plan pages for chapter '{chapter_title}': {str(e)}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating chapter '{chapter_title}': {str(e)}")
            return None

    def _save_chapter_content(self, chapter: Chapter, module_name: str) -> None:
        """Save chapter content to intermediate file."""
        try:
            intermediate_file = os.path.join(self.run_dir, "intermediate", f"chapter_{module_name}_{chapter.title}.json")
            chapter_data = {
                "title": chapter.title,
                "description": chapter.description,
                "pages": [
                    {
                        "title": page.title,
                        "description": page.description,
                        "content": page.content
                    }
                    for page in chapter.pages
                ]
            }
            
            with open(intermediate_file, 'w') as f:
                json.dump(chapter_data, f, indent=2)
            
            logger.info(f"Saved chapter content for '{chapter.title}' in module '{module_name}'")
        except Exception as e:
            logger.error(f"Failed to save chapter content: {str(e)}")

    def _save_intermediate_module(self, module: Module) -> None:
        """Save intermediate module state to disk."""
        try:
            intermediate_file = os.path.join(self.run_dir, "intermediate", f"module_{module.name}.json")
            module_data = {
                "name": module.name,
                "description": module.description,
                "chapters": [
                    {
                        "title": chapter.title,
                        "description": chapter.description,
                        "pages": [
                            {
                                "title": page.title,
                                "description": page.description,
                                "content": page.content
                            }
                            for page in chapter.pages
                        ]
                    }
                    for chapter in module.chapters
                ],
                "summary": module.summary,
                "quiz": [q.__dict__ for q in module.quiz] if module.quiz else []
            }
            
            with open(intermediate_file, 'w') as f:
                json.dump(module_data, f, indent=2)
            
            logger.info(f"Saved intermediate state for module '{module.name}'")
        except Exception as e:
            logger.error(f"Failed to save intermediate module state: {str(e)}")
            # Don't raise the error - this is a non-critical operation
            pass

    async def generate_module_quiz(self, module: Module, max_retries: int = 3) -> List[QuizQuestion]:
        """Generate quiz questions for a module using the quiz agent with retry logic."""
        logger.info(f"Generating quiz for module '{module.name}'")
        
        # Check if intermediate result exists
        intermediate_file = os.path.join(self.run_dir, "intermediate", f"quiz_{module.name}.json")
        if os.path.exists(intermediate_file):
            logger.info(f"Found existing quiz at {intermediate_file}")
            with open(intermediate_file, 'r') as f:
                quiz_data = json.load(f)
                return [QuizQuestion(**q) for q in quiz_data]

        retry_count = 0
        base_delay = 2  # Base delay in seconds
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempt {retry_count + 1}/{max_retries} to generate quiz for module '{module.name}'")
                task = f"""Create quiz questions for the module '{module.name}'.
                Module description: {module.description}
                Module chapters: {[chapter.title for chapter in module.chapters]}
                
                Create comprehensive quiz questions in the specified JSON format.
                End with 'QUIZ_COMPLETE'."""
                
                response = await self.quiz_agent.on_messages(
                    [TextMessage(content=task, source="user")],
                    cancellation_token=CancellationToken()
                )
                result = response.chat_message.content
                quiz_json = self._extract_json_from_result(result)
                
                quiz_questions = [
                    QuizQuestion(
                        question_type=q["question_type"],
                        question=q["question"],
                        multiple_choice=q["multiple_choice"],
                        answer=q["answer"]
                    )
                    for q in quiz_json["questions"]
                ]

                # Save intermediate result
                with open(intermediate_file, 'w') as f:
                    json.dump([q.__dict__ for q in quiz_questions], f, indent=2)

                return quiz_questions

            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Failed to generate quiz for module '{module.name}' after {max_retries} attempts. Error: {str(e)}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Retry {retry_count}/{max_retries} for quiz generation after {delay} seconds. Error: {str(e)}")
                await asyncio.sleep(delay)

    async def generate_module_summary(self, module: Module, max_retries: int = 3) -> str:
        """Generate a summary for a module using the summary agent with retry logic."""
        logger.info(f"Generating summary for module '{module.name}'")
        
        # Check if intermediate result exists
        intermediate_file = os.path.join(self.run_dir, "intermediate", f"summary_{module.name}.json")
        if os.path.exists(intermediate_file):
            logger.info(f"Found existing summary at {intermediate_file}")
            with open(intermediate_file, 'r') as f:
                summary_data = json.load(f)
                return summary_data["summary"]

        retry_count = 0
        base_delay = 2  # Base delay in seconds
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempt {retry_count + 1}/{max_retries} to generate summary for module '{module.name}'")
                task = f"""Create a summary for the module '{module.name}'.
                Module description: {module.description}
                Chapters: {[chapter.title for chapter in module.chapters]}
                
                Create a concise and informative summary.
                End with 'SUMMARY_COMPLETE'."""
                
                response = await self.summary_agent.on_messages(
                    [TextMessage(content=task, source="user")],
                    cancellation_token=CancellationToken()
                )
                result = response.chat_message.content
                summary = self._extract_text_from_result(result)

                # Save intermediate result
                with open(intermediate_file, 'w') as f:
                    json.dump({"summary": summary}, f, indent=2)

                return summary

            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    logger.error(f"Failed to generate summary for module '{module.name}' after {max_retries} attempts. Error: {str(e)}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Retry {retry_count}/{max_retries} for summary generation after {delay} seconds. Error: {str(e)}")
                await asyncio.sleep(delay)

    def _extract_json_from_result(self, result: str) -> Dict:
        """Extract JSON from agent result."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                start = result.find('{')
                end = result.rfind('}') + 1
                if start < 0 or end <= 0 or start >= end:
                    raise ValueError(f"Could not find valid JSON brackets in result (attempt {attempt+1}/{max_attempts})")
                json_str = result[start:end]
                return json.loads(json_str)
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"JSON extraction attempt {attempt+1} failed: {str(e)}. Retrying...")
                    # Try alternative approach
                    try:
                        # Look for json code blocks
                        if "```json" in result:
                            json_blocks = result.split("```json")
                            for block in json_blocks[1:]:  # Skip the part before the first ```json
                                end_block = block.find("```")
                                if end_block > 0:
                                    json_candidate = block[:end_block].strip()
                                    return json.loads(json_candidate)
                        # Try to find any JSON-like structure
                        import re
                        json_pattern = r'\{(?:[^{}]|(?R))*\}'
                        matches = re.findall(json_pattern, result)
                        if matches:
                            for match in matches:
                                try:
                                    return json.loads(match)
                                except:
                                    continue
                    except:
                        pass
                else:
                    logger.error(f"Failed to extract JSON after {max_attempts} attempts: {str(e)}")
                    raise ValueError(f"Failed to extract JSON from result: {str(e)}")

    def _extract_html_from_result(self, result: str) -> str:
        """Extract HTML content from agent result."""
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # First attempt: find HTML between first < and last >
                start = result.find('<')
                end = result.rfind('>') + 1
                if start < 0 or end <= 0 or start >= end:
                    raise ValueError(f"Could not find valid HTML tags in result (attempt {attempt+1}/{max_attempts})")
                return result[start:end]
            except Exception as e:
                if attempt < max_attempts - 1:
                    logger.warning(f"HTML extraction attempt {attempt+1} failed: {str(e)}. Retrying...")
                    # Try alternative approach
                    try:
                        # Look for HTML in code blocks
                        if "```html" in result:
                            html_blocks = result.split("```html")
                            for block in html_blocks[1:]:
                                end_block = block.find("```")
                                if end_block > 0:
                                    html_candidate = block[:end_block].strip()
                                    return html_candidate
                        
                        # Try to find any HTML-like structure with key tags
                        import re
                        # Look for a block with both opening and closing html tags
                        html_pattern = r'<html[\s\S]*?</html>'
                        matches = re.findall(html_pattern, result, re.IGNORECASE)
                        if matches:
                            return matches[0]
                        
                        # Look for a body section
                        body_pattern = r'<body[\s\S]*?</body>'
                        matches = re.findall(body_pattern, result, re.IGNORECASE)
                        if matches:
                            return matches[0]
                    except:
                        pass
                else:
                    logger.error(f"Failed to extract HTML after {max_attempts} attempts: {str(e)}")
                    # Last resort: return whatever content we have rather than failing
                    if "CONTENT_COMPLETE" in result:
                        # Try to get everything before CONTENT_COMPLETE
                        return result.split("CONTENT_COMPLETE")[0].strip()
                    return result  # Return the original content as a fallback

    def _extract_text_from_result(self, result: str) -> str:
        """Extract text content from agent result."""
        try:
            if "SUMMARY_COMPLETE" in result:
                return result.split("SUMMARY_COMPLETE")[0].strip()
            elif "QUIZ_COMPLETE" in result:
                return result.split("QUIZ_COMPLETE")[0].strip()
            else:
                # Just return the text as is
                return result.strip()
        except Exception as e:
            logger.error(f"Failed to extract text: {str(e)}")
            # Return the original result as a fallback
            return result

    def save_course(self, course: Course):
        """Save the course content to a JSON file."""
        filename = os.path.join(self.course_data_dir, f"{course.name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        course_dict = {
            "name": course.name,
            "description": course.description,
            "created_at": course.created_at,
            "modules": [
                {
                    "name": module.name,
                    "description": module.description,
                    "chapters": [
                        {
                            "title": chapter.title,
                            "description": chapter.description,
                            "pages": [
                                {
                                    "title": page.title,
                                    "description": page.description,
                                    "content": page.content
                                }
                                for page in chapter.pages
                            ]
                        }
                        for chapter in module.chapters
                    ],
                    "summary": module.summary,
                    "quiz": [
                        {
                            "question_type": q.question_type,
                            "question": q.question,
                            "multiple_choice": q.multiple_choice,
                            "answer": q.answer
                        }
                        for q in module.quiz
                    ]
                }
                for module in course.modules
            ]
        }

        with open(filename, 'w') as f:
            json.dump(course_dict, f, indent=2)
        
        return filename

    async def generate_module_content(self, module: Module) -> Module:
        """Generate content for a module with parallel chapter content generation."""
        logger.info(f"Starting content generation for module '{module.name}'")
        
        try:
            # Create tasks for parallel chapter generation
            chapter_tasks = [
                self.generate_chapter_content(module, chapter.title)
                for chapter in module.chapters
            ]
            
            # Add rate limiting to prevent overwhelming the API
            semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent chapter generations
            
            async def generate_chapter_with_semaphore(task):
                async with semaphore:
                    return await task
            
            # Execute chapter generation in parallel with rate limiting
            chapter_results = await asyncio.gather(
                *(generate_chapter_with_semaphore(task) for task in chapter_tasks),
                return_exceptions=True
            )
            
            # Process results and handle failures
            successful_chapters = []
            for chapter, result in zip(module.chapters, chapter_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to generate chapter '{chapter.title}': {str(result)}")
                    continue
                if result:  # If chapter generation was successful
                    successful_chapters.append(result)
                    # Save intermediate chapter state
                    self._save_chapter_content(result, module.name)
            
            # Update module with successful chapters
            module.chapters = successful_chapters
            
            # Generate module summary if we have any successful chapters
            if successful_chapters:
                try:
                    logger.info(f"Generating summary for module '{module.name}'")
                    module.summary = await self.generate_module_summary(module)
                except Exception as e:
                    logger.error(f"Failed to generate summary for module '{module.name}': {str(e)}")
                    module.summary = ""  # Set empty summary on failure
            
            # Generate module quiz if we have any successful chapters
            if successful_chapters:
                try:
                    logger.info(f"Generating quiz for module '{module.name}'")
                    module.quiz = await self.generate_module_quiz(module)
                except Exception as e:
                    logger.error(f"Failed to generate quiz for module '{module.name}': {str(e)}")
                    module.quiz = []  # Set empty quiz on failure
            
            # Save intermediate module state
            self._save_intermediate_module(module)
            
            return module
            
        except Exception as e:
            logger.error(f"Failed to generate module content for '{module.name}': {str(e)}")
            raise

    async def generate_course(self, assessment_file: str) -> Tuple[str, Dict[str, List[str]]]:
        """Generate course content with tracking of successful and failed components."""
        failures = {
            'modules': [],
            'chapters': [],
            'pages': []
        }
        
        try:
            # Load assessment conversation
            with open(assessment_file, 'r') as f:
                assessment_data = json.load(f)
                assessment_conversation = "\n".join(
                    f"{msg['source']}: {msg['content']}"
                    for msg in assessment_data['conversation']
                )
            logger.info("Loaded assessment conversation")
            
            # Create course plan
            logger.info("Creating course plan")
            course = await self.create_course_plan(assessment_conversation)
            
            # Process each module
            successful_modules = []
            for module in course.modules:
                try:
                    processed_module = await self.generate_module_content(module)
                    if processed_module.chapters:  # If module has any successful chapters
                        successful_modules.append(processed_module)
                    else:
                        failures['modules'].append(module.name)
                except Exception as e:
                    failures['modules'].append(module.name)
                    logger.error(f"Failed to generate module '{module.name}': {str(e)}")
                    continue
            
            # Update course with successful modules
            course.modules = successful_modules
            
            # Save partial course even if some components failed
            if successful_modules:
                course_file = self.save_course(course)
                return course_file, failures
            else:
                raise RuntimeError("No modules were successfully generated")
            
        except Exception as e:
            logger.error(f"Critical error in course generation: {str(e)}")
            raise

    def _update_status(self, status: str, error_message: Optional[str] = None):
        """Update content creation status in database."""
        if self.session_id:
            if error_message:
                self.db.store_content_creation_error(self.session_id, error_message)
            self.db.update_content_creation_status(self.session_id, status)

async def main():
    logger.info("Starting course generation process")
    # Example usage
    run_id = "grammer_2"
    session_id = "grammer_session_1"  # Add session_id for database tracking
    agent = CourseContentAgent(run_id=run_id, session_id=session_id)
    assessment_file = "data/assessment/conversation_20250317_213358.json"
    try:
        course_file, failures = await agent.generate_course(assessment_file)
        logger.info(f"Course generation completed. Course saved to: {course_file}")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Failures: {failures}")
    except Exception as e:
        logger.error(f"Course generation failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 