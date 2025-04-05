# PersonalAITutor - AI-Powered Learning Platform

Built with AutoGen 0.4.8, AItution leverages multiple AI agents to create a personalized learning experience:
- Assessment Agent: Evaluates student knowledge through interactive conversations
- Content Creation Agent: Generates customized course content based on assessment results
- Course Plan Reviewer Agent: Ensures high-quality and structured learning materials

## Overview

AItution is an innovative AI-powered learning platform that creates personalized learning experiences. The platform uses advanced AI agents to:
1. Assess student knowledge and capabilities through interactive conversations
2. Generate customized course content based on assessment results
3. Create structured learning modules with quizzes and exercises
4. Provide real-time feedback and adaptive learning paths

## Features

- 🤖 AI-powered assessment system
- 📚 Automated course content generation
- 🎯 Personalized learning paths
- 📝 Interactive quizzes and exercises
- 📊 Progress tracking
- 🔄 Real-time content adaptation
- 🌐 Web-based interface

## Prerequisites

- Python 3.8 or higher
- Node.js 14+ (for frontend)
- OpenAI API key
- SQLite3

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/AItution.git
cd AItution
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

3. Install backend dependencies:
```bash
pip install -r requirements.txt
```

4. Install frontend dependencies:
```bash
cd frontend
npm install
```

## Environment Setup

1. Navigate to the `config` directory:
```bash
cd config
cp secrets.py.example secrets.py
```

2. Edit `secrets.py` with your configuration:
```python
OPENAI_API_KEY = 'your-openai-api-key'
FLASK_SECRET_KEY = 'your-secret-key'
```

3. Set up environment variables (optional):
```bash
# On Windows
set FLASK_ENV=development
set OPENAI_API_KEY=your-api-key

# On macOS/Linux
export FLASK_ENV=development
export OPENAI_API_KEY=your-api-key
```

## Running the Application

1. Start the backend server:
```bash
cd backend
python server.py
```

2. Start the frontend development server:
```bash
cd frontend
npm start
```

3. Access the application at `http://localhost:3000`

## API Documentation

### Assessment Endpoints

#### Start Assessment
- **POST** `/api/assessment/start`
- Starts a new assessment session
- Returns: `{ "success": true, "session_id": "uuid" }`

#### Get Question
- **GET** `/api/assessment/question`
- Retrieves the next question in the assessment
- Returns: `{ "success": true, "question": "...", "formatted_question": {} }`

#### Submit Answer
- **POST** `/api/assessment/answer`
- Submit answer to current question
- Body: `{ "answer": "user's answer" }`

#### Get Assessment Result
- **GET** `/api/assessment/result`
- Retrieves final assessment results
- Returns: `{ "success": true, "assessment": {} }`

### Content Creation Endpoints

#### Start Content Creation
- **POST** `/api/content/start`
- Begins course content generation
- Returns: `{ "success": true, "session_id": "uuid" }`

#### Get Content Status
- **GET** `/api/content/status`
- Checks content creation progress
- Returns: `{ "success": true, "progress": {} }`

## Usage Examples

### Starting an Assessment

```python
import requests

# Start assessment
response = requests.post('http://localhost:5000/api/assessment/start')
session_id = response.json()['session_id']

# Get first question
question = requests.get('http://localhost:5000/api/assessment/question').json()

# Submit answer
requests.post('http://localhost:5000/api/assessment/answer', 
             json={'answer': 'User response'})

# Get results
results = requests.get('http://localhost:5000/api/assessment/result').json()
```

### Creating Course Content

```python
import requests

# Start content creation
response = requests.post('http://localhost:5000/api/content/start', 
                        json={'session_id': 'your-session-id'})

# Check progress
status = requests.get('http://localhost:5000/api/content/status', 
                     params={'session_id': 'your-session-id'}).json()
```

## Contributing

We welcome contributions to AItution! Here's how you can help:

1. Fork the repository
2. Create a new branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Run tests (`python -m pytest`)
5. Commit your changes (`git commit -am 'Add new feature'`)
6. Push to the branch (`git push origin feature/improvement`)
7. Create a Pull Request

Please ensure your PR:
- Includes tests for new features
- Updates documentation as needed
- Follows the existing code style
- Includes a clear description of changes

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- 📫 For bugs and features, open an issue on GitHub
- 💬 For questions, start a discussion
- 📝 Check out our [Wiki](../../wiki) for more documentation

## Acknowledgments

- OpenAI for their powerful AI models
- The open-source community for various tools and libraries
- All contributors who help improve AItution 
