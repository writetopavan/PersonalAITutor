export interface QuizQuestion {
  question_type: string;
  question: string;
  multiple_choice: string[];
  answer: string;
}

export interface ChapterPage {
  title: string;
  description: string;
  content: string;
}

export interface Chapter {
  title: string;
  description: string;
  pages: ChapterPage[];
}

export interface Module {
  name: string;
  description: string;
  chapters: Chapter[];
  summary: string;
  quiz: QuizQuestion[];
}

export interface Course {
  name: string;
  description: string;
  created_at: string;
  modules: Module[];
  run_id: string;
} 