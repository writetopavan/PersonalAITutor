import React, { useState, useEffect } from 'react';
import { 
  Box, 
  Container, 
  Typography, 
  Button, 
  Paper,
  Grid,
  Card,
  CardContent,
  CardActions,
  Divider,
  Chip,
  CircularProgress,
  ButtonGroup
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import VisibilityIcon from '@mui/icons-material/Visibility';
import RestartAltIcon from '@mui/icons-material/RestartAlt';

interface Course {
  title?: string;
  description?: string;
  run_id: string;
  modules?: Array<{
    name: string;
    description?: string;
  }>;
}

interface AssessmentSession {
  session_id: string;
  assessment_start: string;
  assessment_finish: string;
  content_creation_status: string;
  content_creation_start: string | null;
  content_creation_finish: string | null;
  error_message: string | null;
  assessment_summary: {
    skill_level: string;
    topic: string;
    learning_path: string;
  } | null;
}

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<AssessmentSession[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [contentCreationLoading, setContentCreationLoading] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCoursesAndSessions = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Fetch courses
        const coursesResponse = await fetch('http://localhost:5000/data/runs');
        if (!coursesResponse.ok) {
          throw new Error(`Failed to fetch courses: ${coursesResponse.statusText}`);
        }
        const coursesData = await coursesResponse.json();
        setCourses(coursesData);
        
        // Fetch assessment sessions - handle failure gracefully
        try {
          const sessionsResponse = await fetch('http://localhost:5000/api/assessment/sessions', {
            credentials: 'include'
          });
          if (sessionsResponse.ok) {
            const sessionsData = await sessionsResponse.json();
            setSessions(sessionsData.sessions || []);
          } else {
            console.error('Failed to fetch sessions:', await sessionsResponse.text());
            // Don't throw error here, just set empty sessions
            setSessions([]);
          }
        } catch (sessionErr) {
          console.error('Error fetching sessions:', sessionErr);
          // Don't throw error here either, just set empty sessions
          setSessions([]);
        }
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };
    
    fetchCoursesAndSessions();
  }, []);
  
  const handleStartAssessment = () => {
    navigate('/assessment');
  };
  
  const handleViewCourse = (courseId: string) => {
    navigate(`/course/${courseId}`);
  };
  
  const handleContinueContentCreation = async (sessionId: string) => {
    // Set loading state for this specific session
    setContentCreationLoading(prev => ({ ...prev, [sessionId]: true }));
    
    try {
      // Find the session to determine if we should use start or retry endpoint
      const session = sessions.find(s => s.session_id === sessionId);
      const endpoint = session?.content_creation_status === 'error' 
        ? 'http://localhost:5000/api/content/retry'
        : 'http://localhost:5000/api/content/start';
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }), // Include session_id in the body
        credentials: 'include',
      });
      
      // Parse the response regardless of status
      const data = await response.json();
      console.log('Content creation response:', data);
      
      if (!response.ok) {
        // Display the error message from the server if available
        throw new Error(data.message || data.error || 
          `Failed to ${session?.content_creation_status === 'error' ? 'retry' : 'start'} content creation: ${response.statusText}`);
      }
      
      if (data.success) {
        // Navigate to course progress page
        navigate(`/course-progress/${sessionId}`);
      } else {
        setError(data.message || 'Failed to process content creation request');
      }
    } catch (err) {
      console.error('Error with content creation:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
      // Reset loading state for this session
      setContentCreationLoading(prev => ({ ...prev, [sessionId]: false }));
    }
  };
  
  const handleViewProgress = (sessionId: string) => {
    navigate(`/course-progress/${sessionId}`);
  };
  
  const getStatusColor = (status: string): 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'in_progress':
        return 'info';
      case 'started':
        return 'primary';
      case 'error':
        return 'error';
      default:
        return 'default';
    }
  };
  
  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleString();
  };
  
  // Filter sessions that need content creation attention
  const pendingSessions = sessions.filter(session => 
    session.content_creation_status === 'not_started' || 
    session.content_creation_status === 'error' ||
    session.content_creation_status === 'started' ||
    session.content_creation_status === 'in_progress'  // Also include sessions in progress
  );

  const getStatusLabel = (status: string): string => {
    switch (status) {
      case 'not_started':
        return 'Not Started';
      case 'started':
        return 'Started (Incomplete)';
      case 'in_progress':
        return 'In Progress';
      case 'completed':
        return 'Completed';
      case 'error':
        return 'Failed';
      default:
        return status;
    }
  };

  const getStatusDescription = (status: string): string => {
    switch (status) {
      case 'not_started':
        return 'Content creation has not been started yet';
      case 'started':
        return 'Content creation was started but did not complete';
      case 'error':
        return 'Content creation failed with an error';
      default:
        return '';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h3" component="h1" gutterBottom align="center" sx={{ mb: 4 }}>
          Personalized AI Tutor
        </Typography>
        <Typography variant="h5" component="h2" gutterBottom align="center" sx={{ mb: 6, color: 'text.secondary' }}>
          Learn Any Subject
        </Typography>
        
        {error && (
          <Paper sx={{ p: 2, mb: 3, bgcolor: 'error.light' }}>
            <Typography color="error">{error}</Typography>
          </Paper>
        )}
        
        <Box sx={{ mb: 6 }}>
          <Paper sx={{ p: 3, bgcolor: 'primary.light', color: 'primary.contrastText' }}>
            <Typography variant="h5" gutterBottom>
              Personalized Learning Journey
            </Typography>
            <Typography paragraph>
              Take an assessment to create a customized learning path tailored to your knowledge level and interests.
            </Typography>
            <Button 
              variant="contained" 
              color="secondary" 
              size="large"
              onClick={handleStartAssessment}
            >
              Start New Assessment
            </Button>
          </Paper>
        </Box>
        
        <Box sx={{ mb: 6 }}>
          <Typography variant="h4" gutterBottom>
            Available Courses
          </Typography>
          
          {courses.length === 0 ? (
            <Paper sx={{ p: 3, textAlign: 'center' }}>
              <Typography>No courses available yet. Start an assessment to create your first course!</Typography>
            </Paper>
          ) : (
            <Grid container spacing={3}>
              {courses.map((course) => (
                <Grid item xs={12} md={6} lg={4} key={course.run_id}>
                  <Card>
                    <CardContent>
                      <Typography variant="h6" gutterBottom>
                        {course.title || course?.modules?.[0]?.name || 'Untitled Course'}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {course.description || course?.modules?.[0]?.description || 'No description available'}
                      </Typography>
                    </CardContent>
                    <CardActions>
                      <Button
                        fullWidth
                        variant="outlined"
                        onClick={() => handleViewCourse(course.run_id)}
                      >
                        View Course
                      </Button>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </Box>
        
        {pendingSessions.length > 0 && (
          <Box sx={{ mb: 4 }}>
            <Typography variant="h4" gutterBottom>
              Pending Content Creation
            </Typography>
            <Typography paragraph>
              The following assessments have been completed but are waiting for content creation:
            </Typography>
            
            <Grid container spacing={3}>
              {pendingSessions.map((session) => (
                <Grid item xs={12} md={6} lg={4} key={session.session_id}>
                  <Card>
                    <CardContent>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', mb: 1 }}>
                        <Typography variant="h6" gutterBottom>
                          {session.assessment_summary?.topic || 'Assessment'}
                        </Typography>
                        <Chip 
                          label={getStatusLabel(session.content_creation_status)} 
                          color={getStatusColor(session.content_creation_status)}
                          size="small"
                        />
                      </Box>
                      
                      <Typography variant="body2" color="text.secondary">
                        Skill Level: {session.assessment_summary?.skill_level || 'Unknown'}
                      </Typography>
                      
                      <Typography variant="body2" sx={{ mt: 1 }}>
                        Completed on: {formatDate(session.assessment_finish)}
                      </Typography>
                      
                      {session.content_creation_start && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          Content creation started: {formatDate(session.content_creation_start)}
                        </Typography>
                      )}
                      
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {getStatusDescription(session.content_creation_status)}
                      </Typography>
                      
                      {session.error_message && (
                        <Typography variant="body2" color="error" sx={{ mt: 1 }}>
                          Error: {session.error_message}
                        </Typography>
                      )}
                      
                      {session.assessment_summary?.learning_path && (
                        <Typography variant="body2" sx={{ mt: 1 }}>
                          {session.assessment_summary.learning_path}
                        </Typography>
                      )}
                    </CardContent>
                    <Divider />
                    <CardActions>
                      <ButtonGroup fullWidth>
                        <Button
                          variant="contained"
                          color={session.content_creation_status === 'error' ? 'error' : 'primary'}
                          onClick={() => handleContinueContentCreation(session.session_id)}
                          disabled={contentCreationLoading[session.session_id]}
                          startIcon={contentCreationLoading[session.session_id] ? <CircularProgress size={16} /> : <RestartAltIcon />}
                        >
                          {contentCreationLoading[session.session_id] 
                            ? 'Processing...' 
                            : session.content_creation_status === 'not_started' 
                              ? 'Generate Course' 
                              : session.content_creation_status === 'error'
                                ? 'Retry Generation'
                                : 'Restart Generation'}
                        </Button>
                        {(session.content_creation_status === 'started' || 
                          session.content_creation_status === 'in_progress' ||
                          session.content_creation_status === 'error') && (
                          <Button
                            variant="outlined"
                            onClick={() => handleViewProgress(session.session_id)}
                            startIcon={<VisibilityIcon />}
                          >
                            View Progress
                          </Button>
                        )}
                      </ButtonGroup>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>
        )}
      </Box>
    </Container>
  );
};

export default HomePage; 