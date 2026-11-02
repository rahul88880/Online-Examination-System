# Online Examination System (Flask + MySQL)

A college mini project with an **Admin** and **Student** module: exam & question CRUD, student management,
timed online exams, automatic marks calculation, and saved results.

**Tech stack:** HTML5, CSS3, Bootstrap 5, Bootstrap Icons, Python Flask, MySQL (mysql-connector-python),
Flask sessions, Werkzeug password hashing, Flask-WTF (CSRF protection).

---

## 1. Requirements
- Python 3.9 or newer
- MySQL Server 8.x (or MariaDB 10.5+) running locally
- VS Code (with the *Python* extension)

## 2. Installation (step by step)

### Step 1 - Open the project in VS Code
`File -> Open Folder...` and select the `online_exam_system` folder. Open the terminal with `Ctrl + ~`.

### Step 2 - Create a virtual environment and install packages
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```
In VS Code press `Ctrl+Shift+P` -> **Python: Select Interpreter** -> choose the `venv` interpreter.

### Step 3 - Create the database
```bash
mysql -u root -p < schema.sql
```
(or open `schema.sql` in MySQL Workbench and run it). This creates the database `online_exam_system` and all 7 tables.

### Step 4 - Configure the connection
Copy `.env.example` to `.env` and edit it:
```
SECRET_KEY=any-long-random-text
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=online_exam_system
```

### Step 5 - Add the admin account and sample data
Pick **one** option:

**A) Sample data (recommended for testing)** - creates 1 admin, 5 students, 3 exams and 30 questions:
```bash
python seed_data.py
```

**B) Your own secure admin account** - the password is typed hidden and stored only as a hash:
```bash
python create_admin.py
```

### Step 6 - Run the app
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.
(In VS Code you can also press `F5` -> *Python File* while `app.py` is open.)

## 3. Sample logins (created by `seed_data.py`)

| Role    | Login                                   | Password       |
|---------|-----------------------------------------|----------------|
| Admin   | `admin@exam.com` (or username `admin`)  | `Admin@123`    |
| Student | `student1@example.com` ... `student5@example.com` | `Student@123` |

> Change the sample passwords before using the system anywhere other than your own computer.

On the login page choose **Student** or **Admin** before signing in.

## 4. Sample exams
| Exam | Questions | Duration | Total / Pass | Attempts |
|------|-----------|----------|--------------|----------|
| Python Programming Basics | 10 | 15 min | 10 / 4  | once |
| Database Management System | 10 | 20 min | 20 / 8  | once |
| Computer Fundamentals | 10 | 10 min | 10 / 4  | multiple allowed |

## 5. Features

**Admin:** dashboard statistics and recent results, create/edit/delete/activate/deactivate exams,
add/edit/delete questions (4 options, correct answer, marks), search students and activate/deactivate accounts,
view all results with search by student name and filter by exam.

**Student:** register and log in, dashboard, list of active exams, instructions page, timed exam
(question palette, answered/unanswered indicator, auto-save, auto-submit), instant result, result history.

## 6. How the important requirements are met
| Requirement | Implementation |
|---|---|
| Timer continues after refresh | `exam_attempts.start_time` is saved on the server; remaining time = `start_time + duration - now`, calculated by the server on every page load. |
| Answers survive refresh | Each answer is auto-saved through `/student/save-answer/<attempt_id>` (AJAX). |
| Auto-submit at zero | `static/js/exam_timer.js` submits the form; the server also auto-grades any expired attempt when it is opened again. |
| One attempt only (unless allowed) | `start_exam` checks `exams.allow_multiple_attempts` and previous submitted attempts. |
| Correct answers hidden | `take_exam` never selects `correct_option`; marks are calculated only on the server in `finalize_attempt()`. |
| Marks cannot be modified | The browser sends only selected options; marks/percentage/status are computed from the database. |
| Password security | `werkzeug.security.generate_password_hash / check_password_hash`. |
| Role-based access | `@login_required('admin' / 'student')` decorator on every protected route. |
| Students cannot see others' results | Result queries always include `student_id = session user`. |
| SQL injection | All queries use parameters (`%s`). |
| CSRF | `Flask-WTF CSRFProtect` - every form and AJAX call sends a token. |

Formula: `Percentage = (Marks Obtained / Total Marks) x 100` - **Pass** if `Marks Obtained >= Passing Marks`.
Tip: keep the sum of question marks equal to the exam's *Total Marks* (the Questions page warns you if they differ).

## 7. Project structure
```
online_exam_system/
    app.py               - all Flask routes and logic
    config.py            - settings (reads .env)
    schema.sql           - MySQL database + tables
    seed_data.py         - sample admin, students, exams, questions
    create_admin.py      - secure admin creation (hidden password prompt)
    requirements.txt
    .env.example
    templates/
        base.html, index.html, login.html, register.html, error.html
        admin/    dashboard, exams, add_exam, edit_exam, questions, add_question,
                  edit_question, students, results  (+ _exam_form, _question_form partials)
        student/  dashboard, available_exams, exam_instructions, take_exam, result, my_results
    static/
        css/style.css
        js/exam_timer.js
```

## 8. Routes
| URL | Method | Purpose |
|---|---|---|
| `/`, `/register`, `/login`, `/logout` | GET / POST | Authentication |
| `/admin/dashboard` | GET | Admin dashboard |
| `/admin/exams` | GET | List exams |
| `/admin/exams/add` | GET, POST | Create exam |
| `/admin/exams/edit/<exam_id>` | GET, POST | Edit exam |
| `/admin/exams/delete/<exam_id>` | POST | Delete exam |
| `/admin/exams/toggle/<exam_id>` | POST | Activate / deactivate exam |
| `/admin/questions/<exam_id>` | GET | List questions |
| `/admin/questions/add/<exam_id>` | GET, POST | Add question |
| `/admin/questions/edit/<question_id>` | GET, POST | Edit question |
| `/admin/questions/delete/<question_id>` | POST | Delete question |
| `/admin/students` | GET | Search / view students |
| `/admin/students/toggle/<student_id>` | POST | Activate / deactivate student |
| `/admin/results` | GET | Results with search and exam filter |
| `/student/dashboard` | GET | Student dashboard |
| `/student/exams` | GET | Available exams |
| `/student/exam/<exam_id>` | GET | Instructions |
| `/student/start-exam/<exam_id>` | POST | Start / resume attempt |
| `/student/take-exam/<attempt_id>` | GET | Exam page |
| `/student/save-answer/<attempt_id>` | POST (AJAX) | Auto-save one answer |
| `/student/submit-exam/<attempt_id>` | POST | Submit and grade |
| `/student/result/<attempt_id>` | GET | Result page |
| `/student/my-results` | GET | Result history |

Delete actions use `POST` forms (protected by CSRF token and a confirmation dialog) because browsers cannot send `DELETE` from plain HTML forms.

## 9. Troubleshooting
- **`Access denied for user 'root'`** - fix `MYSQL_USER` / `MYSQL_PASSWORD` in `.env`.
- **`Unknown database 'online_exam_system'`** - run Step 3 (`schema.sql`).
- **`ModuleNotFoundError`** - activate the virtual environment and run `pip install -r requirements.txt`.
- **Page looks unstyled** - Bootstrap loads from a CDN, so an internet connection is needed.
- **Port already in use** - stop the other Flask app or change the port in the last line of `app.py`.
