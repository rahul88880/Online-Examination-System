-- ============================================================
--  Online Examination System - MySQL schema
--  Run:  mysql -u root -p < schema.sql
-- ============================================================
CREATE DATABASE IF NOT EXISTS online_exam_system
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE online_exam_system;

-- Table 1: admins
CREATE TABLE IF NOT EXISTS admins (
    admin_id   INT AUTO_INCREMENT PRIMARY KEY,
    username   VARCHAR(50)  NOT NULL UNIQUE,
    email      VARCHAR(120) NOT NULL UNIQUE,
    password   VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Table 2: students
CREATE TABLE IF NOT EXISTS students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    full_name  VARCHAR(100) NOT NULL,
    email      VARCHAR(120) NOT NULL UNIQUE,
    mobile     VARCHAR(15)  NOT NULL,
    password   VARCHAR(255) NOT NULL,
    status     ENUM('active','inactive') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Table 3: exams
CREATE TABLE IF NOT EXISTS exams (
    exam_id                 INT AUTO_INCREMENT PRIMARY KEY,
    title                   VARCHAR(150) NOT NULL,
    description             TEXT,
    duration                INT NOT NULL COMMENT 'minutes',
    total_marks             INT NOT NULL,
    passing_marks           INT NOT NULL,
    status                  ENUM('active','inactive') NOT NULL DEFAULT 'inactive',
    allow_multiple_attempts TINYINT(1) NOT NULL DEFAULT 0,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Table 4: questions
CREATE TABLE IF NOT EXISTS questions (
    question_id    INT AUTO_INCREMENT PRIMARY KEY,
    exam_id        INT NOT NULL,
    question_text  TEXT NOT NULL,
    option_a       VARCHAR(255) NOT NULL,
    option_b       VARCHAR(255) NOT NULL,
    option_c       VARCHAR(255) NOT NULL,
    option_d       VARCHAR(255) NOT NULL,
    correct_option ENUM('A','B','C','D') NOT NULL,
    marks          INT NOT NULL DEFAULT 1,
    FOREIGN KEY (exam_id) REFERENCES exams(exam_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Table 5: exam_attempts
CREATE TABLE IF NOT EXISTS exam_attempts (
    attempt_id      INT AUTO_INCREMENT PRIMARY KEY,
    student_id      INT NOT NULL,
    exam_id         INT NOT NULL,
    start_time      DATETIME NOT NULL,
    submission_time DATETIME NULL,
    status          ENUM('in_progress','submitted') NOT NULL DEFAULT 'in_progress',
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (exam_id)    REFERENCES exams(exam_id)       ON DELETE CASCADE,
    INDEX idx_student_exam (student_id, exam_id)
) ENGINE=InnoDB;

-- Table 6: answers
CREATE TABLE IF NOT EXISTS answers (
    answer_id       INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id      INT NOT NULL,
    question_id     INT NOT NULL,
    selected_option ENUM('A','B','C','D') NULL,
    marks_obtained  INT NOT NULL DEFAULT 0,
    FOREIGN KEY (attempt_id)  REFERENCES exam_attempts(attempt_id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(question_id)    ON DELETE CASCADE,
    UNIQUE KEY uq_attempt_question (attempt_id, question_id)
) ENGINE=InnoDB;

-- Table 7: results
CREATE TABLE IF NOT EXISTS results (
    result_id      INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id     INT NOT NULL UNIQUE,
    student_id     INT NOT NULL,
    exam_id        INT NOT NULL,
    marks_obtained INT NOT NULL,
    total_marks    INT NOT NULL,
    percentage     DECIMAL(5,2) NOT NULL,
    result_status  ENUM('Pass','Fail') NOT NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(attempt_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id)      ON DELETE CASCADE,
    FOREIGN KEY (exam_id)    REFERENCES exams(exam_id)            ON DELETE CASCADE
) ENGINE=InnoDB;
