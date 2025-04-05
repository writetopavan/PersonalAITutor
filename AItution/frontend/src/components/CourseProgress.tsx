import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Typography,
  Paper,
  CircularProgress,
  Button,
  Alert,
  LinearProgress,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import HourglassEmptyIcon from '@mui/icons-material/HourglassEmpty';
import ErrorIcon from '@mui/icons-material/Error';
import ReplayIcon from '@mui/icons-material/Replay';

interface ModuleProgress {
  name: string;
  chapters: Array<{
    title: string;
    has_plan: boolean;
    pages_completed: number;
  }>;
  has_summary: boolean;
  has_quiz: boolean;
}

interface CourseProgress {
  status: string;
  started_at: string;
  completed_at: string | null;
  error_message?: string | null;
  modules: ModuleProgress[];
}

// Define params type for React Router v6
type CourseProgressParams = {
  sessionId?: string;
};

const CourseProgress: React.FC = () => {
  const params = useParams<CourseProgressParams>();
  const sessionId = params.sessionId || '';
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<CourseProgress | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [pollingActive, setPollingActive] = useState<boolean>(true);
  const [retryLoading, setRetryLoading] = useState<boolean>(false);

  // Calculate overall progress percentage
  const calculateProgress = (progressData: CourseProgress) => {
    if (!progressData || !progressData.modules || progressData.modules.length === 0) {
      return 0;
    }

    let totalItems = 0;
    let completedItems = 0;

    progressData.modules.forEach(module => {
      // Count module summary
      totalItems++;
      if (module.has_summary) completedItems++;

      // Count module quiz
      totalItems++;
      if (module.has_quiz) completedItems++;

      // Count each chapter and its pages
      module.chapters.forEach(chapter => {
        // Chapter plan
        totalItems++;
        if (chapter.has_plan) completedItems++;

        // Estimate number of pages (assuming average 3 pages per chapter)
        const estimatedPages = 3;
        totalItems += estimatedPages;
        completedItems += Math.min(chapter.pages_completed, estimatedPages);
      });
    });

    return totalItems > 0 ? Math.floor((completedItems / totalItems) * 100) : 0;
  };

  // Format timestamp to readable date
  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return 'Not yet';
    return new Date(timestamp).toLocaleString();
  };

  // Handle retry for course creation
  const handleRetry = async () => {
    if (!sessionId) return;
    
    setRetryLoading(true);
    try {
      const response = await fetch(`http://localhost:5000/api/content/retry`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
        credentials: 'include',
      });
      
      if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
      }

      const data = await response.json();
      
      if (data.success) {
        setError(null);
        setPollingActive(true);
        // Reset progress to show as restarted
        if (progress) {
          setProgress({
            ...progress,
            status: 'started',
            error_message: null
          });
        }
      } else {
        throw new Error(data.message || 'Failed to retry course creation');
      }
    } catch (error) {
      console.error('Error retrying course creation:', error);
      setError(error instanceof Error ? error.message : 'An unexpected error occurred while retrying');
    } finally {
      setRetryLoading(false);
    }
  };

  useEffect(() => {
    // Only poll if the course is not completed yet
    if (!pollingActive || !sessionId) return;

    const fetchProgress = async () => {
      try {
        const response = await fetch(`http://localhost:5000/api/content/status?session_id=${sessionId}`, {
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
        
        if (data.success && data.progress) {
          setProgress(data.progress);
          setLoading(false);
          
          // Stop polling if course creation is completed or failed
          if (data.progress.status === 'completed' || data.progress.status === 'error') {
            setPollingActive(false);
          }
        } else {
          throw new Error('Invalid response data');
        }
      } catch (error) {
        console.error('Error fetching course progress:', error);
        setError(error instanceof Error ? error.message : 'An unexpected error occurred');
        setLoading(false);
        setPollingActive(false);
      }
    };

    fetchProgress();
    
    // Set up polling interval
    const interval = setInterval(fetchProgress, 5000);
    
    return () => {
      clearInterval(interval);
    };
  }, [sessionId, pollingActive]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  // Calculate progress percentage
  const progressPercentage = progress ? calculateProgress(progress) : 0;
  
  // Determine status display
  const getStatusDisplay = () => {
    if (!progress) return { text: 'Unknown', color: 'default' };
    
    switch (progress.status) {
      case 'started':
        return { text: 'Started', color: 'info' };
      case 'in_progress':
        return { text: 'In Progress', color: 'info' };
      case 'completed':
        return { text: 'Completed', color: 'success' };
      case 'error':
        return { text: 'Error', color: 'error' };
      default:
        return { text: progress.status, color: 'default' };
    }
  };
  
  const statusDisplay = getStatusDisplay();

  return (
    <Container maxWidth="md">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom align="center">
          Course Creation Progress
        </Typography>

        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Paper sx={{ p: 3, mt: 4 }}>
          <Box sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Status: <span style={{ color: statusDisplay.color === 'success' ? 'green' : statusDisplay.color === 'error' ? 'red' : 'blue' }}>
                {statusDisplay.text}
              </span>
            </Typography>
            <Typography variant="body1">
              Started at: {formatTimestamp(progress?.started_at || null)}
            </Typography>
            {progress?.completed_at && (
              <Typography variant="body1">
                Completed at: {formatTimestamp(progress.completed_at)}
              </Typography>
            )}
          </Box>

          {progress?.status === 'error' && (
            <Alert 
              severity="error" 
              sx={{ mb: 3 }}
              action={
                <Button 
                  color="inherit" 
                  size="small" 
                  onClick={handleRetry}
                  startIcon={<ReplayIcon />}
                  disabled={retryLoading}
                >
                  {retryLoading ? 'Retrying...' : 'Retry'}
                </Button>
              }
            >
              <Typography variant="subtitle2">Course creation failed</Typography>
              <Typography variant="body2">
                {progress.error_message || 'An error occurred during course creation. Please try again.'}
              </Typography>
            </Alert>
          )}

          <Box sx={{ mb: 4 }}>
            <Typography variant="body2" sx={{ mb: 1 }}>
              Overall progress: {progressPercentage}%
            </Typography>
            <LinearProgress 
              variant="determinate" 
              value={progressPercentage} 
              sx={{ 
                height: 10, 
                borderRadius: 5,
                backgroundColor: progress?.status === 'error' ? 'rgba(211, 47, 47, 0.2)' : undefined,
                '& .MuiLinearProgress-bar': {
                  backgroundColor: progress?.status === 'error' ? '#d32f2f' : undefined,
                }
              }} 
            />
          </Box>

          <Divider sx={{ my: 3 }} />

          {progress?.modules && progress.modules.length > 0 ? (
            <List>
              {progress.modules.map((module, moduleIndex) => (
                <Box key={moduleIndex} sx={{ mb: 3 }}>
                  <Typography variant="h6">
                    Module: {module.name}
                  </Typography>
                  
                  <ListItem>
                    <ListItemIcon>
                      {module.has_summary ? 
                        <CheckCircleIcon color="success" /> : 
                        progress?.status === 'error' ? 
                        <ErrorIcon color="error" /> :
                        <HourglassEmptyIcon color="disabled" />
                      }
                    </ListItemIcon>
                    <ListItemText primary="Module Summary" />
                  </ListItem>
                  
                  <ListItem>
                    <ListItemIcon>
                      {module.has_quiz ? 
                        <CheckCircleIcon color="success" /> : 
                        progress?.status === 'error' ? 
                        <ErrorIcon color="error" /> :
                        <HourglassEmptyIcon color="disabled" />
                      }
                    </ListItemIcon>
                    <ListItemText primary="Module Quiz" />
                  </ListItem>
                  
                  <Typography variant="subtitle1" sx={{ mt: 2, mb: 1 }}>
                    Chapters:
                  </Typography>
                  
                  <List sx={{ pl: 4 }}>
                    {module.chapters.map((chapter, chapterIndex) => (
                      <Box key={chapterIndex} sx={{ mb: 2 }}>
                        <Typography variant="subtitle2">
                          {chapter.title}
                        </Typography>
                        
                        <ListItem dense>
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            {chapter.has_plan ? 
                              <CheckCircleIcon color="success" fontSize="small" /> : 
                              progress?.status === 'error' ? 
                              <ErrorIcon color="error" fontSize="small" /> :
                              <RadioButtonUncheckedIcon color="disabled" fontSize="small" />
                            }
                          </ListItemIcon>
                          <ListItemText primary="Chapter Plan" />
                        </ListItem>
                        
                        <ListItem dense>
                          <ListItemIcon sx={{ minWidth: 36 }}>
                            {chapter.pages_completed > 0 ? 
                              <CheckCircleIcon color="success" fontSize="small" /> : 
                              progress?.status === 'error' ? 
                              <ErrorIcon color="error" fontSize="small" /> :
                              <RadioButtonUncheckedIcon color="disabled" fontSize="small" />
                            }
                          </ListItemIcon>
                          <ListItemText 
                            primary={`Pages: ${chapter.pages_completed} completed`} 
                          />
                        </ListItem>
                      </Box>
                    ))}
                  </List>
                  
                  {moduleIndex < progress.modules.length - 1 && (
                    <Divider sx={{ my: 2 }} />
                  )}
                </Box>
              ))}
            </List>
          ) : (
            <Typography variant="body1">
              No module data available yet. Course creation may still be in initial stages.
            </Typography>
          )}

          <Box sx={{ mt: 4, display: 'flex', justifyContent: 'space-between' }}>
            <Button
              variant="outlined"
              onClick={() => navigate('/')}
            >
              Back to Home
            </Button>
            
            {progress?.status === 'completed' && (
              <Button
                variant="contained"
                color="primary"
                onClick={() => navigate(`/course/${sessionId}`)}
              >
                View Created Course
              </Button>
            )}
            
            {progress?.status === 'error' && (
              <Button
                variant="contained"
                color="error"
                onClick={handleRetry}
                startIcon={<ReplayIcon />}
                disabled={retryLoading}
              >
                {retryLoading ? 'Retrying...' : 'Retry Course Creation'}
              </Button>
            )}
          </Box>
        </Paper>
      </Box>
    </Container>
  );
};

export default CourseProgress; 