-- TestR
-- Schema Version: 1.0.0
-- Apply with: mysql -h HOST -u USER -p testr < migrations/schema.sql
-- WARNING: This will DROP and recreate the database if run twice.
-- For production: use a migration tool or apply incrementally.

CREATE DATABASE IF NOT EXISTS testr
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE testr;

CREATE TABLE schools (
  id        BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code      VARCHAR(10)  NOT NULL,
  name      VARCHAR(100) NOT NULL,
  created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_schools_code UNIQUE (code)
);

CREATE TABLE branches (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  code       VARCHAR(10)  NOT NULL,
  name       VARCHAR(100) NOT NULL,
  school_id  BIGINT UNSIGNED NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_branches_code UNIQUE (code),
  CONSTRAINT fk_branches_school
    FOREIGN KEY (school_id) REFERENCES schools(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_branches_school ON branches(school_id);

CREATE TABLE users (
  id                    BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  email                 VARCHAR(100) NOT NULL,
  password_hash         VARCHAR(255) NOT NULL,
  role                  ENUM('admin','teacher','student') NOT NULL,
  first_name            VARCHAR(50)  NOT NULL,
  last_name             VARCHAR(50)  NOT NULL DEFAULT '',
  is_active             BOOLEAN      NOT NULL DEFAULT TRUE,
  force_password_reset  BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_users_email UNIQUE (email),
  CONSTRAINT valid_user_emails CHECK (
    email REGEXP '^[0-9]{2}[a-zA-Z]{3}[0-9]{3}@[a-zA-Z]+\\\\.clg\\\\.ac\\\\.in$' OR
    email REGEXP '^[a-zA-Z]+\\\\.[a-zA-Z]+@clg\\\\.ac\\\\.in$' OR
    email = 'admin@clg.ac.in'
  )
);

CREATE INDEX idx_users_role     ON users(role);
CREATE INDEX idx_users_active   ON users(is_active);

CREATE TABLE student_profiles (
  user_id      BIGINT UNSIGNED PRIMARY KEY,
  batch_year   CHAR(2)         NOT NULL,
  branch_id    BIGINT UNSIGNED NOT NULL,
  roll_number  VARCHAR(10)     NOT NULL,
  CONSTRAINT uq_student_identity
    UNIQUE (batch_year, branch_id, roll_number),
  CONSTRAINT fk_sp_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sp_branch
    FOREIGN KEY (branch_id) REFERENCES branches(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_sp_batch_branch ON student_profiles(batch_year, branch_id);

CREATE TABLE active_sessions (
  id                  BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id             BIGINT UNSIGNED NOT NULL,
  access_token_jti    VARCHAR(64)  NOT NULL,
  refresh_token_jti   VARCHAR(64)  NOT NULL,
  ip_address          VARCHAR(45)  NOT NULL,
  created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at          DATETIME NOT NULL,
  CONSTRAINT uq_session_user    UNIQUE (user_id),
  CONSTRAINT uq_session_access  UNIQUE (access_token_jti),
  CONSTRAINT uq_session_refresh UNIQUE (refresh_token_jti),
  CONSTRAINT fk_session_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE TABLE ip_logs (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id         BIGINT UNSIGNED NULL,
  email_attempted VARCHAR(100)    NOT NULL,
  ip_address      VARCHAR(45)     NOT NULL,
  action          ENUM(
                    'login_success',
                    'login_failed',
                    'logout',
                    'exam_attempt_start'
                  ) NOT NULL,
  created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_iplog_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_iplogs_user      ON ip_logs(user_id);
CREATE INDEX idx_iplogs_ip        ON ip_logs(ip_address);
CREATE INDEX idx_iplogs_created   ON ip_logs(created_at);

CREATE TABLE password_reset_tokens (
  id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id          BIGINT UNSIGNED NOT NULL,
  token            VARCHAR(128)    NOT NULL,
  created_by       BIGINT UNSIGNED NOT NULL,
  is_used          BOOLEAN         NOT NULL DEFAULT FALSE,
  expires_at       DATETIME        NOT NULL,
  created_at       DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_prt_token UNIQUE (token),
  CONSTRAINT fk_prt_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_prt_admin
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_prt_user ON password_reset_tokens(user_id);

CREATE TABLE courses (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  course_code VARCHAR(15)  NOT NULL,
  name        VARCHAR(100) NOT NULL,
  description TEXT,
  branch_id   BIGINT UNSIGNED NOT NULL,
  year        CHAR(2)      NOT NULL,
  mode        ENUM('T','P') NOT NULL,
  is_active   BOOLEAN      NOT NULL DEFAULT TRUE,
  created_by  BIGINT UNSIGNED NOT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_courses_code UNIQUE (course_code),
  CONSTRAINT fk_courses_branch
    FOREIGN KEY (branch_id) REFERENCES branches(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_courses_creator
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_courses_branch    ON courses(branch_id);
CREATE INDEX idx_courses_active    ON courses(is_active);
CREATE INDEX idx_courses_year      ON courses(year);

CREATE TABLE course_enrollments (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  course_id    BIGINT UNSIGNED NOT NULL,
  student_id   BIGINT UNSIGNED NOT NULL,
  enrolled_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  enrolled_by  BIGINT UNSIGNED NOT NULL,
  CONSTRAINT uq_enrollment UNIQUE (course_id, student_id),
  CONSTRAINT fk_enroll_course
    FOREIGN KEY (course_id) REFERENCES courses(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_enroll_student
    FOREIGN KEY (student_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_enroll_admin
    FOREIGN KEY (enrolled_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_enroll_course   ON course_enrollments(course_id);
CREATE INDEX idx_enroll_student  ON course_enrollments(student_id);

CREATE TABLE course_assignments (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  course_id    BIGINT UNSIGNED NOT NULL,
  teacher_id   BIGINT UNSIGNED NOT NULL,
  assigned_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  assigned_by  BIGINT UNSIGNED NOT NULL,
  CONSTRAINT uq_assignment UNIQUE (course_id, teacher_id),
  CONSTRAINT fk_assign_course
    FOREIGN KEY (course_id) REFERENCES courses(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assign_teacher
    FOREIGN KEY (teacher_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assign_admin
    FOREIGN KEY (assigned_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_assign_course   ON course_assignments(course_id);
CREATE INDEX idx_assign_teacher  ON course_assignments(teacher_id);

CREATE TABLE exams (
  id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  course_id               BIGINT UNSIGNED NOT NULL,
  created_by              BIGINT UNSIGNED NOT NULL,
  title                   VARCHAR(200)    NOT NULL,
  description             TEXT,
  duration_minutes        INT UNSIGNED    NOT NULL,
  negative_marking_factor DECIMAL(4,2)    NOT NULL DEFAULT 0.00,
  total_marks             DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  passing_marks           DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  start_time              DATETIME        NOT NULL,
  end_time                DATETIME        NOT NULL,
  is_published            BOOLEAN         NOT NULL DEFAULT FALSE,
  results_published       BOOLEAN         NOT NULL DEFAULT FALSE,
  published_at            DATETIME        NULL,
  results_published_at    DATETIME        NULL,
  created_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at              DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_exams_course
    FOREIGN KEY (course_id) REFERENCES courses(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_exams_teacher
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT chk_exam_times
    CHECK (end_time > start_time),
  CONSTRAINT chk_passing_marks
    CHECK (passing_marks <= total_marks)
);

CREATE INDEX idx_exams_course     ON exams(course_id);
CREATE INDEX idx_exams_teacher    ON exams(created_by);
CREATE INDEX idx_exams_start      ON exams(start_time);
CREATE INDEX idx_exams_published  ON exams(is_published);

CREATE TABLE questions (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  exam_id        BIGINT UNSIGNED NOT NULL,
  question_text  TEXT            NOT NULL,
  question_type  ENUM('mcq','subjective') NOT NULL,
  marks          DECIMAL(5,2)    NOT NULL,
  order_index    INT UNSIGNED    NOT NULL DEFAULT 0,
  word_limit     INT UNSIGNED    NULL DEFAULT NULL,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_questions_exam
    FOREIGN KEY (exam_id) REFERENCES exams(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_marks_positive CHECK (marks > 0)
);

CREATE INDEX idx_questions_exam   ON questions(exam_id);
CREATE INDEX idx_questions_order  ON questions(exam_id, order_index);

CREATE TABLE mcq_options (
  id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  question_id   BIGINT UNSIGNED NOT NULL,
  option_label  CHAR(1)         NOT NULL,
  option_text   TEXT            NOT NULL,
  is_correct    BOOLEAN         NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_option_label UNIQUE (question_id, option_label),
  CONSTRAINT fk_options_question
    FOREIGN KEY (question_id) REFERENCES questions(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT chk_option_label CHECK (option_label IN ('A','B','C','D'))
);

CREATE INDEX idx_options_question ON mcq_options(question_id);

CREATE TABLE exam_attempts (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  exam_id      BIGINT UNSIGNED NOT NULL,
  student_id   BIGINT UNSIGNED NOT NULL,
  ip_address   VARCHAR(45)     NOT NULL,
  status       ENUM('in_progress','submitted','auto_submitted') NOT NULL DEFAULT 'in_progress',
  started_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submitted_at DATETIME NULL DEFAULT NULL,
  CONSTRAINT uq_attempt UNIQUE (exam_id, student_id),
  CONSTRAINT fk_attempt_exam
    FOREIGN KEY (exam_id) REFERENCES exams(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_attempt_student
    FOREIGN KEY (student_id) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_attempt_exam     ON exam_attempts(exam_id);
CREATE INDEX idx_attempt_student  ON exam_attempts(student_id);
CREATE INDEX idx_attempt_status   ON exam_attempts(status);

CREATE TABLE answers (
  id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  attempt_id              BIGINT UNSIGNED NOT NULL,
  question_id             BIGINT UNSIGNED NOT NULL,
  selected_option_id      BIGINT UNSIGNED NULL DEFAULT NULL,
  subjective_text         TEXT            NULL DEFAULT NULL,
  is_correct              BOOLEAN         NULL DEFAULT NULL,
  marks_awarded           DECIMAL(5,2)    NULL DEFAULT NULL,
  CONSTRAINT uq_answer UNIQUE (attempt_id, question_id),
  CONSTRAINT fk_answers_attempt
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_answers_question
    FOREIGN KEY (question_id) REFERENCES questions(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_answers_option
    FOREIGN KEY (selected_option_id) REFERENCES mcq_options(id)
    ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_answers_attempt   ON answers(attempt_id);
CREATE INDEX idx_answers_question  ON answers(question_id);

CREATE TABLE subjective_grades (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  answer_id    BIGINT UNSIGNED NOT NULL,
  graded_by    BIGINT UNSIGNED NOT NULL,
  marks_awarded DECIMAL(5,2)  NOT NULL,
  feedback     TEXT            NULL,
  graded_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_sg_answer UNIQUE (answer_id),
  CONSTRAINT fk_sg_answer
    FOREIGN KEY (answer_id) REFERENCES answers(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_sg_teacher
    FOREIGN KEY (graded_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE TABLE exam_results (
  id                       BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  attempt_id               BIGINT UNSIGNED NOT NULL,
  exam_id                  BIGINT UNSIGNED NOT NULL,
  student_id               BIGINT UNSIGNED NOT NULL,
  mcq_marks_awarded        DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  subjective_marks_awarded DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  negative_marks_deducted  DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  total_marks_awarded      DECIMAL(7,2)    NOT NULL DEFAULT 0.00,
  is_pass                  BOOLEAN         NULL DEFAULT NULL,
  published_by             BIGINT UNSIGNED NULL DEFAULT NULL,
  published_at             DATETIME        NULL DEFAULT NULL,
  computed_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_result_attempt UNIQUE (attempt_id),
  CONSTRAINT fk_result_attempt
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_result_exam
    FOREIGN KEY (exam_id) REFERENCES exams(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_result_student
    FOREIGN KEY (student_id) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_result_publisher
    FOREIGN KEY (published_by) REFERENCES users(id)
    ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_result_exam      ON exam_results(exam_id);
CREATE INDEX idx_result_student   ON exam_results(student_id);
CREATE INDEX idx_result_published ON exam_results(published_at);

CREATE TABLE proctor_violations (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  attempt_id     BIGINT UNSIGNED NOT NULL,
  violation_type ENUM(
                   'tab_switch',
                   'fullscreen_exit',
                   'camera_unavailable',
                   'copy_paste_attempt'
                 ) NOT NULL,
  occurred_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
  details        VARCHAR(255) NULL,
  CONSTRAINT fk_pv_attempt
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_pv_attempt ON proctor_violations(attempt_id);
CREATE INDEX idx_pv_type    ON proctor_violations(attempt_id, violation_type);

CREATE TABLE proctor_snapshots (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  attempt_id   BIGINT UNSIGNED NOT NULL,
  gcs_path     VARCHAR(500)    NOT NULL,
  captured_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_ps_attempt
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_ps_attempt ON proctor_snapshots(attempt_id);
CREATE INDEX idx_ps_time    ON proctor_snapshots(attempt_id, captured_at);

CREATE TABLE notifications (
  id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  user_id    BIGINT UNSIGNED NOT NULL,
  title      VARCHAR(200)    NOT NULL,
  message    TEXT            NOT NULL,
  is_read    BOOLEAN         NOT NULL DEFAULT FALSE,
  created_at DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_notif_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE
);

CREATE INDEX idx_notif_user     ON notifications(user_id);
CREATE INDEX idx_notif_unread   ON notifications(user_id, is_read);

CREATE TABLE forum_threads (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  title       VARCHAR(200)    NOT NULL,
  created_by  BIGINT UNSIGNED NOT NULL,
  is_pinned   BOOLEAN         NOT NULL DEFAULT FALSE,
  is_locked   BOOLEAN         NOT NULL DEFAULT FALSE,
  is_deleted  BOOLEAN         NOT NULL DEFAULT FALSE,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_ft_creator
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_ft_pinned    ON forum_threads(is_pinned);
CREATE INDEX idx_ft_created   ON forum_threads(created_at);
CREATE INDEX idx_ft_creator   ON forum_threads(created_by);

CREATE TABLE forum_posts (
  id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  thread_id      BIGINT UNSIGNED NOT NULL,
  parent_post_id BIGINT UNSIGNED NULL DEFAULT NULL,
  content        TEXT            NOT NULL,
  created_by     BIGINT UNSIGNED NOT NULL,
  is_deleted     BOOLEAN         NOT NULL DEFAULT FALSE,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                   ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_fp_thread
    FOREIGN KEY (thread_id) REFERENCES forum_threads(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_fp_parent
    FOREIGN KEY (parent_post_id) REFERENCES forum_posts(id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_fp_creator
    FOREIGN KEY (created_by) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_fp_thread  ON forum_posts(thread_id);
CREATE INDEX idx_fp_parent  ON forum_posts(parent_post_id);
CREATE INDEX idx_fp_creator ON forum_posts(created_by);

CREATE TABLE system_logs (
  id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  event_type  ENUM(
                'exam_created',
                'exam_published',
                'results_published',
                'users_created',
                'course_created',
                'course_activated',
                'course_deactivated'
              ) NOT NULL,
  actor_id    BIGINT UNSIGNED NOT NULL,
  description VARCHAR(500)    NOT NULL,
  metadata    JSON            NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_sl_actor
    FOREIGN KEY (actor_id) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_sl_type    ON system_logs(event_type);
CREATE INDEX idx_sl_actor   ON system_logs(actor_id);
CREATE INDEX idx_sl_created ON system_logs(created_at);

CREATE TABLE audit_logs (
  id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  admin_id     BIGINT UNSIGNED NOT NULL,
  action       VARCHAR(100)    NOT NULL,
  target_type  VARCHAR(50)     NOT NULL,
  target_id    VARCHAR(50)     NULL,
  details      JSON            NULL,
  ip_address   VARCHAR(45)     NOT NULL,
  created_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_al_admin
    FOREIGN KEY (admin_id) REFERENCES users(id)
    ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_al_admin   ON audit_logs(admin_id);
CREATE INDEX idx_al_action  ON audit_logs(action);
CREATE INDEX idx_al_target  ON audit_logs(target_type, target_id);
CREATE INDEX idx_al_created ON audit_logs(created_at);
