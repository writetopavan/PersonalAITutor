import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Grid,
  Card,
  CardContent,
  CardActions,
  Typography,
  Button,
  CircularProgress,
  Alert,
  Box,
} from '@mui/material';
import { Course } from '../types';

const CourseList: React.FC = () => {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchCourses = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch('http://localhost:5000/data/runs');
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Fetched courses:', data); // Debug log
        setCourses(data);
      } catch (error) {
        console.error('Error fetching courses:', error);
        setError('Failed to load courses. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchCourses();
  }, []);

  if (loading) {
    return (
      <Container sx={{ mt: 4, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Container>
    );
  }

  if (error) {
    return (
      <Container sx={{ mt: 4 }}>
        <Alert severity="error">{error}</Alert>
      </Container>
    );
  }

  return (
    <Container sx={{ mt: 4 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 4 }}>
        <Typography variant="h4" component="h1">
          Available Courses
        </Typography>
        <Button
          variant="contained"
          color="primary"
          onClick={() => navigate('/assessment')}
          sx={{ ml: 2 }}
        >
          Start Assessment
        </Button>
      </Box>

      {!courses.length ? (
        <Alert severity="info">No courses available.</Alert>
      ) : (
        <Grid container spacing={3}>
          {courses.map((course) => (
            <Grid item xs={12} sm={6} md={4} key={course.name}>
              <Card>
                <CardContent>
                  <Typography variant="h6" component="h2">
                    {course.name}
                  </Typography>
                  <Typography color="textSecondary" gutterBottom>
                    Created: {new Date(course.created_at).toLocaleDateString()}
                  </Typography>
                  <Typography variant="body2">
                    {course.description}
                  </Typography>
                  <Typography variant="body2" color="textSecondary">
                    Modules: {course.modules.length}
                  </Typography>
                </CardContent>
                <CardActions>
                  <Button
                    size="small"
                    color="primary"
                    onClick={() => navigate(`/course/${course.run_id}`)}
                  >
                    View Course
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
    </Container>
  );
};

export default CourseList; 