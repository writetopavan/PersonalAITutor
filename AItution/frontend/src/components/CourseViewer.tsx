import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Container,
  Box,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemText,
  ListItemButton,
  Paper,
  CircularProgress,
  Alert,
  IconButton,
  AppBar,
  Toolbar,
  Button,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormControl,
  FormLabel,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Course, Module, Chapter, QuizQuestion } from '../types';

const drawerWidth = 280;

interface QuizProps {
  questions: QuizQuestion[];
}

const Quiz: React.FC<QuizProps> = ({ questions }) => {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState('');
  const [showResult, setShowResult] = useState(false);

  const handleAnswerSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSelectedAnswer(event.target.value);
  };

  const handleNext = () => {
    if (currentQuestion < questions.length - 1) {
      setCurrentQuestion(prev => prev + 1);
      setSelectedAnswer('');
      setShowResult(false);
    }
  };

  const handlePrevious = () => {
    if (currentQuestion > 0) {
      setCurrentQuestion(prev => prev - 1);
      setSelectedAnswer('');
      setShowResult(false);
    }
  };

  const handleCheck = () => {
    setShowResult(true);
  };

  const question = questions[currentQuestion];
  if (!question) return null;

  return (
    <Box sx={{ mt: 3 }}>
      <Paper sx={{ p: 3 }}>
        <FormControl component="fieldset">
          <FormLabel component="legend">
            Question {currentQuestion + 1} of {questions.length}
          </FormLabel>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            {question.question}
          </Typography>
          <RadioGroup value={selectedAnswer} onChange={handleAnswerSelect}>
            {question.multiple_choice.map((choice, index) => (
              <FormControlLabel
                key={index}
                value={choice}
                control={<Radio />}
                label={choice}
              />
            ))}
          </RadioGroup>
        </FormControl>

        {showResult && (
          <Alert severity={selectedAnswer === question.answer ? "success" : "error"} sx={{ mt: 2 }}>
            {selectedAnswer === question.answer 
              ? "Correct!" 
              : `Incorrect. The correct answer is: ${question.answer}`}
          </Alert>
        )}

        <Box sx={{ mt: 3, display: 'flex', justifyContent: 'space-between' }}>
          <Button
            variant="contained"
            onClick={handlePrevious}
            disabled={currentQuestion === 0}
          >
            Previous
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={handleCheck}
            disabled={!selectedAnswer}
          >
            Check Answer
          </Button>
          <Button
            variant="contained"
            onClick={handleNext}
            disabled={currentQuestion === questions.length - 1}
          >
            Next
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

const CourseViewer: React.FC = () => {
  const { courseId } = useParams<{ courseId: string }>();
  const navigate = useNavigate();
  const [course, setCourse] = useState<Course | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [selectedPage, setSelectedPage] = useState<number>(0);
  const [showQuiz, setShowQuiz] = useState(false);

  useEffect(() => {
    const fetchCourse = async () => {
      try {
        setLoading(true);
        setError(null);
        console.log('Fetching course:', courseId); // Debug log
        const response = await fetch(`http://localhost:5000/data/runs/${courseId}/course.json`);
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Fetched course data:', data); // Debug log
        setCourse(data);
        if (data.modules.length > 0) {
          setSelectedModule(data.modules[0]);
          if (data.modules[0].chapters.length > 0) {
            setSelectedChapter(data.modules[0].chapters[0]);
          }
        }
      } catch (error) {
        console.error('Error fetching course:', error);
        setError('Failed to load course. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    if (courseId) {
      fetchCourse();
    }
  }, [courseId]);

  if (loading) {
    return (
      <Container sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error || !course) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert 
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={() => navigate('/')}>
              Go Back
            </Button>
          }
        >
          {error || 'Course not found'}
        </Alert>
      </Container>
    );
  }

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <IconButton
            edge="start"
            color="inherit"
            onClick={() => navigate('/')}
            sx={{ mr: 2 }}
          >
            <ArrowBackIcon />
          </IconButton>
          <Typography variant="h6" noWrap component="div">
            {course.name}
          </Typography>
        </Toolbar>
      </AppBar>
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            mt: '64px', // Height of AppBar
          },
        }}
      >
        <Box sx={{ overflow: 'auto' }}>
          <List>
            {course.modules.map((module) => (
              <React.Fragment key={module.name}>
                <ListItem disablePadding>
                  <ListItemButton
                    selected={selectedModule?.name === module.name}
                    onClick={() => {
                      setSelectedModule(module);
                      if (module.chapters.length > 0) {
                        setSelectedChapter(module.chapters[0]);
                        setSelectedPage(0);
                      }
                      setShowQuiz(false);
                    }}
                  >
                    <ListItemText 
                      primary={module.name}
                      secondary={`${module.chapters.length} chapters`}
                    />
                  </ListItemButton>
                </ListItem>
                {selectedModule?.name === module.name && (
                  <List component="div" disablePadding>
                    {module.chapters.map((chapter) => (
                      <ListItem key={chapter.title} disablePadding>
                        <ListItemButton
                          selected={selectedChapter?.title === chapter.title}
                          onClick={() => {
                            setSelectedChapter(chapter);
                            setSelectedPage(0);
                            setShowQuiz(false);
                          }}
                          sx={{ pl: 4 }}
                        >
                          <ListItemText 
                            primary={chapter.title}
                            secondary={`${chapter.pages.length} pages`}
                          />
                        </ListItemButton>
                      </ListItem>
                    ))}
                    <ListItem disablePadding>
                      <ListItemButton
                        selected={showQuiz}
                        onClick={() => {
                          setShowQuiz(true);
                          setSelectedChapter(null);
                        }}
                        sx={{ pl: 4, bgcolor: showQuiz ? 'action.selected' : 'inherit' }}
                      >
                        <ListItemText 
                          primary="Module Quiz"
                          secondary={`${module.quiz?.length || 0} questions`}
                        />
                      </ListItemButton>
                    </ListItem>
                  </List>
                )}
              </React.Fragment>
            ))}
          </List>
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          mt: '64px', // Height of AppBar
          overflow: 'auto',
        }}
      >
        {selectedModule && (
          <Container maxWidth="lg">
            {showQuiz ? (
              <>
                <Typography variant="h4" gutterBottom>
                  {selectedModule.name} - Module Quiz
                </Typography>
                {selectedModule.quiz && selectedModule.quiz.length > 0 ? (
                  <Quiz questions={selectedModule.quiz} />
                ) : (
                  <Alert severity="info">No quiz available for this module.</Alert>
                )}
              </>
            ) : selectedChapter && (
              <>
                <Typography variant="h4" gutterBottom>
                  {selectedChapter.title}
                </Typography>
                <Typography variant="subtitle1" color="text.secondary" gutterBottom>
                  {selectedChapter.description}
                </Typography>
                <Paper sx={{ p: 3, my: 3 }}>
                  {selectedChapter.pages && selectedChapter.pages.length > 0 ? (
                    <div
                      dangerouslySetInnerHTML={{
                        __html: selectedChapter.pages[selectedPage]?.content || '',
                      }}
                    />
                  ) : (
                    <Alert severity="info">No content available for this chapter.</Alert>
                  )}
                </Paper>
                <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between' }}>
                  <Button
                    variant="contained"
                    onClick={() => setSelectedPage((prev) => Math.max(0, prev - 1))}
                    disabled={selectedPage === 0}
                  >
                    Previous Page
                  </Button>
                  <Typography variant="body2" sx={{ alignSelf: 'center' }}>
                    Page {selectedPage + 1} of {selectedChapter.pages.length}
                  </Typography>
                  <Button
                    variant="contained"
                    onClick={() =>
                      setSelectedPage((prev) =>
                        Math.min(selectedChapter.pages.length - 1, prev + 1)
                      )
                    }
                    disabled={selectedPage === selectedChapter.pages.length - 1}
                  >
                    Next Page
                  </Button>
                </Box>
              </>
            )}
          </Container>
        )}
      </Box>
    </Box>
  );
};

export default CourseViewer; 