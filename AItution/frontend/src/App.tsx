import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import CourseList from './components/CourseList';
import CourseViewer from './components/CourseViewer';
import Assessment from './components/Assessment';
import CourseProgress from './components/CourseProgress';
import HomePage from './components/HomePage';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/courses" element={<CourseList />} />
          <Route path="/course/:courseId" element={<CourseViewer />} />
          <Route path="/assessment" element={<Assessment />} />
          <Route path="/course-progress/:sessionId" element={<CourseProgress />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App; 