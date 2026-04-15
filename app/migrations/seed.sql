-- TestR Seed Data
-- Run after schema.sql
-- Passwords are bcrypt hashes

USE testr;

-- ── Schools ──────────────────────────────────────────────────────────────────
INSERT IGNORE INTO schools (code, name) VALUES
  ('se', 'School of Engineering'),
  ('sm', 'School of Management'),
  ('ss', 'School of Sciences');

-- ── Branches ─────────────────────────────────────────────────────────────────
INSERT IGNORE INTO branches (code, name, school_id) VALUES
  ('CSE',  'Computer Science Engineering',        (SELECT id FROM (SELECT id FROM schools WHERE code='se') AS s)),
  ('ECE',  'Electronics & Communication Eng.',    (SELECT id FROM (SELECT id FROM schools WHERE code='se') AS s)),
  ('MECH', 'Mechanical Engineering',              (SELECT id FROM (SELECT id FROM schools WHERE code='se') AS s)),
  ('CIVIL','Civil Engineering',                   (SELECT id FROM (SELECT id FROM schools WHERE code='se') AS s)),
  ('IT',   'Information Technology',              (SELECT id FROM (SELECT id FROM schools WHERE code='se') AS s)),
  ('MBA',  'Master of Business Administration',   (SELECT id FROM (SELECT id FROM schools WHERE code='sm') AS s)),
  ('BBA',  'Bachelor of Business Administration', (SELECT id FROM (SELECT id FROM schools WHERE code='sm') AS s)),
  ('MSC',  'Master of Science',                   (SELECT id FROM (SELECT id FROM schools WHERE code='ss') AS s)),
  ('BSC',  'Bachelor of Science',                 (SELECT id FROM (SELECT id FROM schools WHERE code='ss') AS s));

-- ── Admin ─────────────────────────────────────────────────────────────────────
-- Password: Admin@TestR2024  (bcrypt hash)
INSERT IGNORE INTO users (email, password_hash, role, first_name, last_name, is_active, force_password_reset) VALUES
  ('admin@clg.ac.in',
   '$2b$12$jl5ImJ4aswrEaQtqTkb3rOzfL5DRbdWD4opGUq5fVhZaKFRmO/4Ji',
   'admin', 'System', 'Admin', 1, 1);

-- ── Teachers ─────────────────────────────────────────────────────────────────
-- Password: T1Pass123, T2Pass123, T3Pass123
INSERT IGNORE INTO users (email, password_hash, role, first_name, last_name, is_active) VALUES
  ('john.doe@clg.ac.in',
   '$2b$12$Iu/46/na/9JCnqWh8HMoOeb/s/XMITExC7xdun8ztd3LY/ChpcP5W',
   'teacher', 'John', 'Doe', 1),
  ('jane.smith@clg.ac.in',
   '$2b$12$vrJjAHwgYiHkx.6tCBDuWeU18GxGCcwOxtj82opU7LetJES.YMUqm',
   'teacher', 'Jane', 'Smith', 1),
  ('robert.brown@clg.ac.in',
   '$2b$12$oY3R97sYcyIJ7a4pcgTS4ufLTZvXEtwR281QNitvp8dW4ZI/5pCTS',
   'teacher', 'Robert', 'Brown', 1);

-- ── Students ─────────────────────────────────────────────────────────────────
-- Password: S1Pass123, S2Pass123, S3Pass123
INSERT IGNORE INTO users (email, password_hash, role, first_name, last_name, is_active) VALUES
  ('24cse240@se.clg.ac.in',
   '$2b$12$mI2W.iT/MbpDVBXoUxcHnOIEkg3tN/QldXMcphvEKEHdAOirD3Eyq',
   'student', 'Alice', 'Wonder', 1),
  ('24cse241@se.clg.ac.in',
   '$2b$12$X12S8QyE0Zmgwhv.X.UfZOATg0fATPgYmU0H9OqvBMqCk9FUyk10.',
   'student', 'Bob', 'Builder', 1),
  ('24cse242@se.clg.ac.in',
   '$2b$12$etr3eYEGe4Pn9CarOCEcnu2tSGetOFhraNZNWU/dKVOmHufdqqgHW',
   'student', 'Charlie', 'Chaplin', 1);

-- ── Student Profiles ─────────────────────────────────────────────────────────
INSERT IGNORE INTO student_profiles (user_id, batch_year, branch_id, roll_number) VALUES
  ((SELECT id FROM users WHERE email='24cse240@se.clg.ac.in'),
   '22', (SELECT id FROM branches WHERE code='CSE'), '001'),
  ((SELECT id FROM users WHERE email='24cse241@se.clg.ac.in'),
   '22', (SELECT id FROM branches WHERE code='CSE'), '002'),
  ((SELECT id FROM users WHERE email='24cse242@se.clg.ac.in'),
   '22', (SELECT id FROM branches WHERE code='CSE'), '003');

-- ── Courses ───────────────────────────────────────────────────────────────────
INSERT IGNORE INTO courses (course_code, name, description, branch_id, year, mode, created_by) VALUES
  ('22CS101T', 'Data Structures', 'Fundamentals of Data Structures',
   (SELECT id FROM branches WHERE code='CSE'), '22', 'T',
   (SELECT id FROM users WHERE email='admin@clg.ac.in')),
  ('22CS101P', 'Data Structures Lab', 'Practical Implementation of Data Structures',
   (SELECT id FROM branches WHERE code='CSE'), '22', 'P',
   (SELECT id FROM users WHERE email='admin@clg.ac.in')),
  ('22CS102T', 'Algorithms', 'Introduction to Algorithms',
   (SELECT id FROM branches WHERE code='CSE'), '22', 'T',
   (SELECT id FROM users WHERE email='admin@clg.ac.in'));

-- ── Course Assignments ────────────────────────────────────────────────────────
INSERT IGNORE INTO course_assignments (course_id, teacher_id, assigned_by) VALUES
  ((SELECT id FROM courses WHERE course_code='22CS101T'),
   (SELECT id FROM users WHERE email='john.doe@clg.ac.in'),
   (SELECT id FROM users WHERE email='admin@clg.ac.in')),
  ((SELECT id FROM courses WHERE course_code='22CS102T'),
   (SELECT id FROM users WHERE email='jane.smith@clg.ac.in'),
   (SELECT id FROM users WHERE email='admin@clg.ac.in'));

-- ── Course Enrollments ────────────────────────────────────────────────────────
INSERT IGNORE INTO course_enrollments (course_id, student_id, enrolled_by) VALUES
  ((SELECT id FROM courses WHERE course_code='22CS101T'),
   (SELECT id FROM users WHERE email='24cse240@se.clg.ac.in'),
   (SELECT id FROM users WHERE email='admin@clg.ac.in')),
  ((SELECT id FROM courses WHERE course_code='22CS101T'),
   (SELECT id FROM users WHERE email='24cse241@se.clg.ac.in'),
   (SELECT id FROM users WHERE email='admin@clg.ac.in')),
  ((SELECT id FROM courses WHERE course_code='22CS102T'),
   (SELECT id FROM users WHERE email='24cse240@se.clg.ac.in'),
   (SELECT id FROM users WHERE email='admin@clg.ac.in'));

-- ── Sample Exam ──────────────────────────────────────────────────────────────
INSERT IGNORE INTO exams (course_id, created_by, title, description, duration_minutes, total_marks, passing_marks, start_time, end_time, is_published) VALUES
  ((SELECT id FROM courses WHERE course_code='22CS101T'),
   (SELECT id FROM users WHERE email='john.doe@clg.ac.in'),
   'DS Midterm', 'Midterm examination for Data Structures',
   60, 20, 8,
   DATE_ADD(NOW(), INTERVAL 1 DAY),
   DATE_ADD(NOW(), INTERVAL 26 HOUR),
   1);

-- ── Sample Question & Options ─────────────────────────────────────────────────
SET @exam_id = (SELECT id FROM exams WHERE title='DS Midterm' LIMIT 1);
INSERT IGNORE INTO questions (exam_id, question_text, question_type, marks, order_index) VALUES
  (@exam_id, 'What is the time complexity of searching in a Hash Table?', 'mcq', 2, 1),
  (@exam_id, 'Describe the difference between Stack and Queue.', 'subjective', 5, 2);

SET @q1_id = (SELECT id FROM questions WHERE exam_id=@exam_id AND order_index=1 LIMIT 1);
INSERT IGNORE INTO mcq_options (question_id, option_label, option_text, is_correct) VALUES
  (@q1_id, 'A', 'O(1)',      1),
  (@q1_id, 'B', 'O(n)',      0),
  (@q1_id, 'C', 'O(log n)', 0),
  (@q1_id, 'D', 'O(n^2)',   0);
