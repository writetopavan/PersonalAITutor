/// <reference types="node" />

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Paper,
  CircularProgress,
  Grid,
  Alert,
  Divider,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';

interface Question {
  question_number: number;
  question: string;
  purpose?: string;
}

interface FormattedQuestion {
  question_number: number;
  question: string;
  purpose?: string;
}

// Interface for collections of questions
interface QuestionCollection {
  questions: Question[];
  [key: string]: any;
}

interface AssessmentState {
  isStarted: boolean;
  sessionId: string | null;
  currentQuestion: Question | null;
  questions: Question[]; // For multiple questions
  formattedQuestion: FormattedQuestion | null;
  answers: Record<number, string>;
  multipleQuestionsMode: boolean;
  assessment: {
    topic?: string;
    skill_level: string;
    learning_path: string;
    immediate_topics: string[];
    future_topics: Array<{
      name: string;
      description: string;
    }>;
  } | null;
  loading: boolean;
  pollingActive: boolean;
  progress: {
    total: number;
    answered: number;
  } | null;
  courseCreationStarted: boolean;
  courseCreationLoading: boolean;
}

const Assessment: React.FC = () => {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [state, setState] = useState<AssessmentState>({
    isStarted: false,
    sessionId: null,
    currentQuestion: null,
    questions: [],
    formattedQuestion: null,
    answers: {},
    multipleQuestionsMode: false,
    assessment: null,
    loading: false,
    pollingActive: false,
    progress: null,
    courseCreationStarted: false,
    courseCreationLoading: false,
  });
  
  // Add a ref to track if a request is in progress
  const isRequestInProgress = useRef(false);
  const lastRequestTime = useRef(0);
  const MIN_REQUEST_INTERVAL = 1000; // Minimum time between requests in ms

  // 1. First, add a dedicated ref to track if we're already fetching results
  const isResultFetchInProgress = useRef(false);

  // Polling function for questions
  useEffect(() => {
    let pollingInterval: ReturnType<typeof setTimeout> | null = null;
    
    // Only poll if polling is active AND we don't have results yet
    if (state.pollingActive && 
        state.sessionId && 
        !state.assessment && 
        !state.loading) {
      
      pollingInterval = setInterval(() => {
        // Only make a new request if no request is in progress and enough time has passed
        const now = Date.now();
        if (!isRequestInProgress.current && 
            !isResultFetchInProgress.current && 
            (now - lastRequestTime.current) > MIN_REQUEST_INTERVAL) {
          fetchNextQuestion();
        }
      }, 2000);
    }
    
    return () => {
      if (pollingInterval) {
        clearInterval(pollingInterval);
      }
    };
  }, [state.pollingActive, state.sessionId, state.assessment, state.loading]);

  // 2. Modify the auto-fetch useEffect to check this ref
  useEffect(() => {
    if (state.isStarted && 
        !state.pollingActive && 
        !state.currentQuestion && 
        state.questions.length === 0 && 
        !state.assessment &&
        !state.loading &&
        !isRequestInProgress.current &&
        !isResultFetchInProgress.current) {  // Add this check
      
      // Set the flag before calling
      isResultFetchInProgress.current = true;
      getAssessmentResults();
    }
  }, [state.isStarted, state.pollingActive, state.currentQuestion, 
      state.questions.length, state.assessment, state.loading]);

  // Reset any error messages when state changes
  useEffect(() => {
    if (state.assessment || state.currentQuestion || state.questions.length > 0) {
      setError(null);
    }
  }, [state.assessment, state.currentQuestion, state.questions.length]);

  const startAssessment = async () => {
    // Prevent starting if already in progress
    if (isRequestInProgress.current) return;
    
    setError(null);
    setState(prev => ({ ...prev, loading: true }));
    isRequestInProgress.current = true;
    
    try {
      const response = await fetch('http://localhost:5000/api/assessment/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Important for session cookie handling
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Received start response:', data);
      
      if (!data.success) {
        throw new Error('Failed to start assessment');
      }

      setState(prev => ({
        ...prev,
        isStarted: true,
        sessionId: data.session_id,
        loading: false,
        pollingActive: true,
      }));
      
      // Wait a short time before first poll to avoid race conditions
      setTimeout(() => {
        isRequestInProgress.current = false;
      }, 500);
    } catch (error) {
      console.error('Error starting assessment:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      setState(prev => ({ ...prev, loading: false }));
      isRequestInProgress.current = false;
    }
  };

  const fetchNextQuestion = async () => {
    // Prevent duplicate requests
    if (!state.sessionId || state.assessment || isRequestInProgress.current) return;
    
    isRequestInProgress.current = true;
    lastRequestTime.current = Date.now();
    
    try {
      const response = await fetch('http://localhost:5000/api/assessment/question', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Question response:', data);
      
      if (data.assessment_complete) {
        console.log('Assessment complete detected, fetching results...');
        
        // First stop the polling to prevent more question requests
        setState(prev => ({
          ...prev,
          pollingActive: false,
          loading: true,
          currentQuestion: null,
          questions: [],
        }));

        // Clear request flags
        isRequestInProgress.current = false;
        isResultFetchInProgress.current = false;
        
        try {
          // Immediately fetch results
          const resultResponse = await fetch('http://localhost:5000/api/assessment/result', {
            method: 'GET',
            headers: {
              'Content-Type': 'application/json',
            },
            credentials: 'include',
          });
          
          if (!resultResponse.ok) {
            throw new Error(`API Error: ${resultResponse.status}`);
          }

          const resultData = await resultResponse.json();
          console.log('Assessment result response:', resultData);
          
          if (resultData.success && resultData.complete && resultData.assessment) {
            // Extract the nested assessment object
            const assessment = resultData.assessment.assessment || resultData.assessment;
            
            // Validate the assessment data structure
            if (!validateAssessment(assessment)) {
                console.error('Invalid assessment data structure:', assessment);
                setError('Received invalid assessment data structure');
                return;
            }

            // Ensure arrays exist
            if (!assessment.immediate_topics) assessment.immediate_topics = [];
            if (!assessment.future_topics) assessment.future_topics = [];
            
            // Update state with results
            setState(prev => ({
                ...prev,
                assessment: assessment,  // Use the extracted assessment
                loading: false,
                pollingActive: false,
                currentQuestion: null,
                questions: [],
                progress: null
            }));
            
            // Clear all request flags
            isRequestInProgress.current = false;
            isResultFetchInProgress.current = false;
          } else {
            console.log('Result data incomplete or invalid:', resultData);
            // Re-enable polling if results aren't ready
            setState(prev => ({
              ...prev,
              loading: false,
              pollingActive: true,
            }));
            isRequestInProgress.current = false;
            isResultFetchInProgress.current = false;
          }
        } catch (resultError) {
          console.error('Error fetching results:', resultError);
          setError(resultError instanceof Error ? resultError.message : 'Failed to fetch assessment results');
          // Re-enable polling on error
          setState(prev => ({
            ...prev,
            loading: false,
            pollingActive: true,
          }));
          isRequestInProgress.current = false;
          isResultFetchInProgress.current = false;
        }
        return;
      }
      
      // If still processing, update progress if available
      if (data.processing && data.progress) {
        setState(prev => ({
          ...prev,
          progress: data.progress,
          loading: false,
        }));
        isRequestInProgress.current = false;
        return;
      }
      
      // If we have a question, display it
      if (data.question) {
        // Check if we have a formatted question
        const formattedQuestion = data.formatted_question as FormattedQuestion | undefined;
        
        // Check if we have multiple questions or a single question
        let multipleQuestionsMode = false;
        let questions: Question[] = [];
        
        // Check if formatted_question is an array
        if (formattedQuestion && Array.isArray(formattedQuestion)) {
          multipleQuestionsMode = true;
          questions = formattedQuestion as unknown as Question[];
        } 
        // Check if formatted_question has a questions array property
        else if (formattedQuestion && 
                 typeof formattedQuestion === 'object' && 
                 'questions' in formattedQuestion && 
                 Array.isArray((formattedQuestion as unknown as QuestionCollection).questions)) {
          multipleQuestionsMode = true;
          questions = (formattedQuestion as unknown as QuestionCollection).questions;
        } 
        // Check for multiple JSON blocks in the question string
        else if (typeof data.question === 'string' && data.question.includes('```json')) {
          try {
            // Extract all JSON blocks from the string
            const jsonMatches = data.question.match(/```json\s*([\s\S]*?)\s*```/g);
            
            if (jsonMatches && jsonMatches.length > 0) {
              // Parse each JSON block into a question object
              const parsedQuestions = jsonMatches.map((match, index) => {
                // Extract the JSON content from the markdown code block
                const jsonContent = match.replace(/```json\s*([\s\S]*?)\s*```/, '$1');
                try {
                  const questionObj = JSON.parse(jsonContent);
                  // Ensure each question has a question_number
                  if (!questionObj.question_number) {
                    questionObj.question_number = index + 1;
                  }
                  return questionObj as Question;
                } catch (e) {
                  console.error('Error parsing JSON question:', e);
                  return null;
                }
              }).filter(q => q !== null);
              
              if (parsedQuestions.length > 0) {
                multipleQuestionsMode = true;
                questions = parsedQuestions as Question[];
              }
            }
          } catch (e) {
            console.error('Error extracting JSON questions:', e);
          }
        }
        // Otherwise try to parse the raw question string to see if it contains multiple questions
        else if (typeof data.question === 'string') {
          try {
            // Look for patterns that might indicate multiple questions
            const questionTexts = data.question.split(/Question \d+:/);
            if (questionTexts.length > 2) { // More than one question found (first split will be empty)
              multipleQuestionsMode = true;
              questions = questionTexts.slice(1).map((text, index) => ({
                question_number: index + 1,
                question: text.trim(),
              }));
            }
          } catch (e) {
            console.error('Error parsing multiple questions:', e);
          }
        }
        
        if (multipleQuestionsMode && questions.length > 0) {
          console.log('Multiple questions detected:', questions);
          setState(prev => ({
            ...prev,
            questions: questions,
            multipleQuestionsMode: true,
            loading: false,
            pollingActive: false, // Stop polling in multiple questions mode
          }));
        } else {
          // Single question mode
          setState(prev => ({
            ...prev,
            currentQuestion: {
              question_number: formattedQuestion?.question_number || 1,
              question: data.question,
              purpose: formattedQuestion?.purpose,
            },
            formattedQuestion: formattedQuestion || null,
            multipleQuestionsMode: false,
            loading: false,
            pollingActive: false, // Stop polling when we have a single question
          }));
        }
      }
      isRequestInProgress.current = false;
    } catch (error) {
      console.error('Error fetching question:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      setState(prev => ({
        ...prev,
        loading: false,
        pollingActive: false, // Stop polling on error
      }));
      isRequestInProgress.current = false;
    }
  };

  const handleCurrentAnswerChange = (answer: string) => {
    if (!state.currentQuestion) return;
    
    setState(prev => ({
      ...prev,
      answers: {
        ...prev.answers,
        [prev.currentQuestion?.question_number || 0]: answer,
      },
    }));
  };

  const handleMultipleAnswerChange = (questionNumber: number, answer: string) => {
    setState(prev => ({
      ...prev,
      answers: {
        ...prev.answers,
        [questionNumber]: answer,
      },
    }));
  };

  const submitCurrentAnswer = async () => {
    if (!state.currentQuestion || !state.sessionId || isRequestInProgress.current) return;
    
    const questionNumber = state.currentQuestion.question_number;
    const answer = state.answers[questionNumber] || '';
    
    if (!answer.trim()) {
      setError('Please provide an answer before submitting.');
      return;
    }
    
    setState(prev => ({ ...prev, loading: true }));
    isRequestInProgress.current = true;
    
    try {
      const response = await fetch('http://localhost:5000/api/assessment/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          answer: answer,
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Answer submission response:', data);
      
      if (data.success) {
        // Clear current question to show loading state
        setState(prev => ({
          ...prev,
          currentQuestion: null,
          loading: false,
          pollingActive: true, // Re-enable polling to fetch the next question
        }));
        
        // Wait a short time before allowing next request
        setTimeout(() => {
          isRequestInProgress.current = false;
        }, 500);
      } else {
        throw new Error('Failed to submit answer');
      }
    } catch (error) {
      console.error('Error submitting answer:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      setState(prev => ({ ...prev, loading: false }));
      isRequestInProgress.current = false;
    }
  };

  const submitAllAnswers = async () => {
    if (!state.sessionId || state.questions.length === 0 || isRequestInProgress.current) return;
    
    // Validate all questions have answers
    const unansweredQuestions = state.questions.filter(
      q => !state.answers[q.question_number] || !state.answers[q.question_number].trim()
    );
    
    if (unansweredQuestions.length > 0) {
      setError(`Please answer all questions before submitting. Missing answers for question(s) ${unansweredQuestions.map(q => q.question_number).join(', ')}.`);
      return;
    }
    
    setState(prev => ({ ...prev, loading: true }));
    isRequestInProgress.current = true;
    
    try {
      // Format all answers into a single string with question numbers
      const formattedAnswers = Object.entries(state.answers)
        .map(([questionNumber, answer]) => {
          // Find the corresponding question to get the actual question text
          const question = state.questions.find(q => q.question_number.toString() === questionNumber);
          const questionText = question ? question.question : `Question ${questionNumber}`;
          return `Question ${questionNumber}: ${answer}`;
        })
        .join('\n\n');
      
      console.log('Submitting formatted answers:', formattedAnswers);
      
      const response = await fetch('http://localhost:5000/api/assessment/answer', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({
          answer: formattedAnswers,
        }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Multiple answers submission response:', data);
      
      if (data.success) {
        // Reset questions and start polling for results
        setState(prev => ({
          ...prev,
          questions: [],
          currentQuestion: null,
          multipleQuestionsMode: false,
          loading: false,
          pollingActive: true, // Re-enable polling
        }));
        
        // Wait a short time before allowing next request
        setTimeout(() => {
          isRequestInProgress.current = false;
        }, 500);
      } else {
        throw new Error('Failed to submit answers');
      }
    } catch (error) {
      console.error('Error submitting answers:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      setState(prev => ({ ...prev, loading: false }));
      isRequestInProgress.current = false;
    }
  };

  // 3. Update the getAssessmentResults function to handle the flag correctly
  const getAssessmentResults = async () => {
    console.log('Fetching assessment results...');
    if (!state.sessionId || isResultFetchInProgress.current) {
      console.log('Cannot fetch results: no session ID or already fetching results');
      return;
    }
    
    // Set both flags to prevent any other requests during result fetching
    isResultFetchInProgress.current = true;
    isRequestInProgress.current = true;
    
    setState(prev => ({
      ...prev,
      loading: true,
      pollingActive: false // Ensure polling is stopped while fetching results
    }));
    
    try {
      console.log('Making request to /api/assessment/result endpoint');
      const response = await fetch('http://localhost:5000/api/assessment/result', {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      console.log('Assessment result response:', data);
      
      if (data.success && data.complete && data.assessment) {
        console.log('Assessment is complete, updating UI with results');
        // Update state with results and ensure we're in a clean state
        setState(prev => ({
          ...prev,
          assessment: data.assessment,
          loading: false,
          pollingActive: false,
          currentQuestion: null,
          questions: [],
          progress: null
        }));
        
        // Clear all request flags
        isResultFetchInProgress.current = false;
        isRequestInProgress.current = false;
      } else {
        console.log('Assessment not complete yet:', data);
        // Reset to polling state if results aren't ready
        setState(prev => ({
          ...prev,
          loading: false,
          pollingActive: true,
          assessment: null
        }));
        
        isResultFetchInProgress.current = false;
        isRequestInProgress.current = false;
      }
    } catch (error) {
      console.error('Error getting assessment results:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      // Reset to polling state on error
      setState(prev => ({ 
        ...prev, 
        loading: false,
        pollingActive: true,
      }));
      
      isResultFetchInProgress.current = false;
      isRequestInProgress.current = false;
    }
  };

  const validateAssessment = (assessment: any): boolean => {
    // Handle nested assessment object
    const actualAssessment = assessment.assessment || assessment;
    
    return (
        actualAssessment &&
        typeof actualAssessment.skill_level === 'string' &&
        typeof actualAssessment.learning_path === 'string' &&
        Array.isArray(actualAssessment.immediate_topics) &&
        Array.isArray(actualAssessment.future_topics)
    );
  };

  const startCourseCreation = async () => {
    if (!state.sessionId || isRequestInProgress.current || state.courseCreationStarted) return;
    
    setState(prev => ({ ...prev, courseCreationLoading: true }));
    isRequestInProgress.current = true;
    
    try {
      const response = await fetch('http://localhost:5000/api/content/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API Error: ${response.status} - ${errorText}`);
      }

      const data = await response.json();
      console.log('Course creation start response:', data);
      
      if (data.success) {
        setState(prev => ({
          ...prev,
          courseCreationStarted: true,
          courseCreationLoading: false,
        }));
        
        // Navigate to course creation progress page
        navigate(`/course-progress/${state.sessionId}`);
      } else {
        throw new Error('Failed to start course creation');
      }
    } catch (error) {
      console.error('Error starting course creation:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred');
      setState(prev => ({ ...prev, courseCreationLoading: false }));
      isRequestInProgress.current = false;
    }
  };

  if (state.loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          Educational Topic Assessment
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        {!state.isStarted ? (
          <Paper sx={{ p: 3, mt: 4 }}>
            <Typography variant="h6" gutterBottom>
              Ready to start your educational assessment?
            </Typography>
            <Typography paragraph>
              This assessment will help determine your knowledge level and create a personalized learning path.
            </Typography>
            <Button
              variant="contained"
              onClick={startAssessment}
              disabled={state.loading}
            >
              {state.loading ? 'Starting...' : 'Start Assessment'}
            </Button>
          </Paper>
        ) : !state.assessment ? (
          <Paper sx={{ p: 3, mt: 4 }}>
            {state.multipleQuestionsMode && state.questions.length > 0 ? (
              // Multiple questions mode
              <>
                <Typography variant="h6" gutterBottom>
                  Assessment Questions
                </Typography>
                <Typography paragraph>
                  Please answer all questions below.
                </Typography>
                
                <Grid container spacing={3} sx={{ mb: 3 }}>
                  {state.questions.map((question) => (
                    <Grid item xs={12} key={question.question_number || Math.random()}>
                      <Typography variant="subtitle1" gutterBottom>
                        Question {question.question_number || ''}:
                      </Typography>
                      <Typography paragraph>
                        {question.question}
                      </Typography>
                      <TextField
                        fullWidth
                        multiline
                        rows={4}
                        value={state.answers[question.question_number] || ''}
                        onChange={(e) => handleMultipleAnswerChange(question.question_number, e.target.value)}
                        placeholder="Your answer"
                        sx={{ mb: 2 }}
                      />
                      <Divider sx={{ my: 2 }} />
                    </Grid>
                  ))}
                </Grid>
                
                <Button
                  variant="contained"
                  onClick={submitAllAnswers}
                  disabled={state.questions.length === 0 || state.questions.some(q => 
                    !state.answers[q.question_number] || !state.answers[q.question_number].trim()
                  )}
                >
                  Submit All Answers
                </Button>
              </>
            ) : state.currentQuestion ? (
              // Single question mode
              <>
                <Typography variant="h6" gutterBottom>
                  Question {state.currentQuestion.question_number}
                </Typography>
                <Typography paragraph>
                  {state.formattedQuestion?.question || state.currentQuestion.question}
                </Typography>
                <TextField
                  fullWidth
                  multiline
                  rows={4}
                  value={state.answers[state.currentQuestion.question_number] || ''}
                  onChange={(e) => handleCurrentAnswerChange(e.target.value)}
                  placeholder="Your answer"
                  sx={{ mb: 2 }}
                />
                <Button
                  variant="contained"
                  onClick={submitCurrentAnswer}
                  disabled={!state.answers[state.currentQuestion.question_number]}
                >
                  Submit Answer
                </Button>
              </>
            ) : state.progress ? (
              <Box sx={{ textAlign: 'center', my: 4 }}>
                <Typography variant="h6" gutterBottom>
                  Assessment in Progress
                </Typography>
                <Typography paragraph>
                  Processing questions: {state.progress.answered} of {state.progress.total} answered
                </Typography>
                <CircularProgress />
              </Box>
            ) : (
              <Box sx={{ textAlign: 'center', my: 4 }}>
                <Typography variant="h6" gutterBottom>
                  Preparing your questions...
                </Typography>
                <CircularProgress />
              </Box>
            )}
          </Paper>
        ) : (
          <Paper sx={{ p: 3, mt: 4 }}>
            <Typography variant="h5" gutterBottom>
              Assessment Complete!
            </Typography>
            <Typography variant="h6" gutterBottom>
              Your Skill Level: {state.assessment.skill_level}
            </Typography>
            <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
              Recommended Learning Path:
            </Typography>
            <Typography paragraph>{state.assessment.learning_path}</Typography>

            <Typography variant="h6" gutterBottom>
              Immediate Topics to Focus On:
            </Typography>
            <ul>
              {state.assessment.immediate_topics?.map((topic, index) => (
                <li key={index}>
                  <Typography>{topic}</Typography>
                </li>
              )) || 'No immediate topics available'}
            </ul>

            <Typography variant="h6" gutterBottom sx={{ mt: 3 }}>
              Future Topics:
            </Typography>
            <ul>
              {state.assessment.future_topics?.map((topic, index) => (
                <li key={index}>
                  <Typography variant="subtitle1">{topic.name}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {topic.description}
                  </Typography>
                </li>
              )) || 'No future topics available'}
            </ul>

            <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
              <Button
                variant="outlined"
                onClick={() => navigate('/')}
              >
                Back to Home
              </Button>
              
              <Button
                variant="contained"
                color="primary"
                onClick={startCourseCreation}
                disabled={state.courseCreationLoading || state.courseCreationStarted}
                startIcon={state.courseCreationLoading ? <CircularProgress size={20} /> : null}
              >
                {state.courseCreationLoading ? 'Starting...' : 'Create Personalized Course'}
              </Button>
            </Box>
          </Paper>
        )}

        {/* Only show this when we're waiting for results */}
        {state.isStarted && 
          !state.assessment && 
          !state.currentQuestion && 
          state.questions.length === 0 && 
          !state.pollingActive && 
          !state.loading && 
          !isResultFetchInProgress.current && (
          <Box sx={{ textAlign: 'center', my: 4 }}>
            <Typography variant="h6" gutterBottom>
              Assessment appears complete! Loading results...
            </Typography>
            <CircularProgress sx={{ mb: 2 }} />
            <Button 
              variant="contained" 
              onClick={() => {
                isResultFetchInProgress.current = false;
                isRequestInProgress.current = false;
                getAssessmentResults();
              }}
              sx={{ display: 'block', mx: 'auto', mt: 2 }}
            >
              Manually Load Results
            </Button>
          </Box>
        )}
      </Box>
    </Container>
  );
};

export default Assessment; 