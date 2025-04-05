import asyncio
import os
import json
import sqlite3
import uuid
import logging
from datetime import datetime
from autogen_agentchat.conditions import ExternalTermination
from database import db  # Add this import at the top


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('assessment_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from datetime import datetime
from autogen_core import CancellationToken
from autogen_agentchat.messages import TextMessage
from config.config import OPENAI_API_KEY
# Create an OpenAI model client
model_client = OpenAIChatCompletionClient(
    model="gpt-4o-mini",
    # Get API key from secret key
    api_key=OPENAI_API_KEY
)

async def _user_input(prompt: str, cancellation_token: CancellationToken | None) -> str:
    # Get the session ID from the global variable
    session_id = current_session_id
    logger.debug(f"Waiting for user input for session {session_id}")
    
    data = None
    while data is None:
        # Pass the session ID to get_last_message
        data = get_last_message(session_id)
        if data is None:
            # Wait a bit before checking again
            await asyncio.sleep(1)
    
    logger.debug(f"Received user input: {data[:50]}...")
    return data

# Create the assessment agent
assessment_agent = AssistantAgent(
    "assessment_agent",
    model_client=model_client,
    system_message="""You are an educational assessment agent designed to evaluate a user's skill level on topics they want to learn.

Follow this assessment process:
1. Ask the user what topic they want to learn.
2. Generate 3-5 questions to assess their current skill level on that topic.
3. Based on their responses, either ask more questions for clarity or proceed to the next step.
4. Generate a comprehensive assessment summary.

IMPORTANT FORMATTING REQUIREMENTS:
- Format your questions in JSON format like this:
```json
{
  "question_number": 1,
  "question": "What is your current experience with [topic]?",
  "purpose": "To assess general familiarity with the topic"
}
```

- Format your final assessment summary in JSON format like this:
```json
{
  "assessment": {
    "topic": "The topic the user wants to learn",
    "skill_level": "Beginner/Intermediate/Advanced",
    "learning_path": "Recommended approach to learning",
    "immediate_topics": [
      "Brief description of Topic 1 that should be learned immediately",
      "Brief description of Topic 2 that should be learned immediately",
      "Brief description of Topic 3 that should be learned immediately"
    ],
    "future_topics": [
      {
        "name": "Future Topic 1",
        "description": "Why this should be learned later"
      },
      {
        "name": "Future Topic 2",
        "description": "Why this should be learned later"
      }
    ]
  }
}
```

Be friendly, encouraging, and professional. Adapt your questions based on the user's responses.
When you've completed the assessment, include "ASSESSMENT COMPLETE" after your JSON summary."""
)

# Create the user proxy agent with enhanced console input
user_proxy = UserProxyAgent(
    "user", 
    input_func=_user_input,
)

# Define a termination condition that stops when assessment is complete
termination = TextMentionTermination("ASSESSMENT COMPLETE")
external_termination = ExternalTermination()

# Create a team with the assessment agent and user
team = RoundRobinGroupChat([assessment_agent, user_proxy], termination_condition=external_termination | termination)

async def main(session_id=None):
    """Run the educational assessment agent with an optional session ID."""
    # Database is initialized when the module is imported
    
    # Use provided session ID or generate a new one
    global current_session_id
    if session_id:
        current_session_id = session_id
    else:
        current_session_id = str(uuid.uuid4())
    
    logger.info(f"Starting assessment session: {current_session_id}")
    
    # Print welcome message with clear instructions
    print("\n" + "="*50)
    print("🎓 EDUCATIONAL TOPIC ASSESSMENT 🎓".center(50))
    print("="*50)
    print("\nThis agent will assess your knowledge on a topic you want to learn")
    print("and provide personalized recommendations for your learning journey.")
    print("\nHow it works:")
    print("1. Tell the agent what topic you want to learn")
    print("2. Answer a few questions to assess your current knowledge")
    print("3. Receive a personalized learning plan in JSON format")
    print("\nType your responses and press Enter to continue.")
    print("-"*50 + "\n")
    
    # Run the assessment and stream to the console
    logger.info("Starting assessment conversation")
    async for message in team.run_stream(task="Start by asking the user what topic they want to learn about."):
        # Process each message
        if hasattr(message, 'content'):
            print(message.content)
            
            # Store agent messages that contain questions in the database
            if message.source == "assessment_agent" and "?" in message.content:
                logger.info(f"Received question from assessment agent: {message.content[:50]}...")
                db.store_question(current_session_id, message.content)
                print(message.content)

        else:
            logger.info("Processing conversation summary")
            conversation = []        
            # Process each message
            for msg in message.messages:
                if hasattr(msg, 'content'):
                    message_data = {
                        "source": msg.source,
                        "content": msg.content,
                        "type": msg.type
                    }
                    conversation.append(message_data)
            
            # Create a directory for the session if it doesn't exist
            session_dir = os.path.join('data', 'sessions', current_session_id)
            os.makedirs(session_dir, exist_ok=True)
            
            # Save with session ID in the filename
            filename = os.path.join(session_dir, f'conversation.json')
            
            # Save to JSON file
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "session_id": current_session_id,
                    "conversation": conversation
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Conversation saved to {filename}")
            print(f"Conversation saved to {filename}")
    
    # Print closing message
    logger.info("Assessment completed")
    print("\n" + "-"*50)
    print("Assessment completed! Good luck with your learning journey!")
    print("="*50 + "\n")

# Create a new function to start an assessment with a session ID
async def start_assessment(session_id):
    """Start a new assessment with the given session ID."""
    logger.info(f"Starting new assessment with session ID: {session_id}")
    # Just call the main function with the provided session ID
    await main(session_id)

def get_last_message(session_id=None):
    """Get the last answered message for the specified session."""
    sid = session_id if session_id is not None else current_session_id
    return db.get_last_message(sid)

def get_next_question(session_id):
    """Get the next unanswered question for a session."""
    return db.get_next_question(session_id)

def get_answer_for_question(session_id):
    """Get the assessment result."""
    return db.get_answer_for_question(session_id)

def set_user_response(session_id, answer):
    """Store the user's response to a question."""
    db.store_answer(session_id, answer)


if __name__ == "__main__":
    try:
        logger.info("Starting assessment in standalone mode")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("Assessment interrupted by user")
        print("\nAssessment interrupted. You can restart the assessment anytime.")
    except Exception as e:
        logger.error(f"Error in assessment: {str(e)}", exc_info=True)
        print(f"\nAn error occurred: {e}")
        print("Please check your API key and internet connection, then try again.") 