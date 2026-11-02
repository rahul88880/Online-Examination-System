"""
Online Examination System - Flask backend
Run with:  python app.py
"""
import os
import re
from datetime import datetime, timedelta
from functools import wraps

import mysql.connector
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, session, url_for)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config, db_settings

app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)  # CSRF protection for every POST request

OPTIONS = ("A", "B", "C", "D")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_RE = re.compile(r"^[0-9]{10}$")
GRACE_SECONDS = 15  # network delay allowed when the timer hits zero


# ----------------------------------------------------------------------
# Database helpers (all queries are parameterised -> no SQL injection)
# ----------------------------------------------------------------------
def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**db_settings())
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None and db.is_connected():
        db.close()


def query(sql, args=(), one=False):
    """Run a SELECT and return a list of dicts (or one dict / None)."""
    cur = get_db().cursor(dictionary=True)
    try:
        cur.execute(sql, args)
        rows = cur.fetchall()
    finally:
        cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run INSERT / UPDATE / DELETE, commit, and return the last inserted id."""
    db = get_db()
    cur = db.cursor()
    try:
        cur.execute(sql, args)
        db.commit()
        return cur.lastrowid
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


# ----------------------------------------------------------------------
# Template filters / error pages
# ----------------------------------------------------------------------
@app.template_filter("dt")
def format_datetime(value, fmt="%d %b %Y, %I:%M %p"):
    return value.strftime(fmt) if value else "-"


@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403,
                           message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404,
                           message="The page you are looking for was not found."), 404


@app.errorhandler(mysql.connector.Error)
def db_error(_e):
    app.logger.exception("Database error")
    return render_template("error.html", code=500,
                           message="A database error occurred. Please try again."), 500


# ----------------------------------------------------------------------
# Authentication helpers (role based access control)
# ----------------------------------------------------------------------
def dashboard_for(role):
    return url_for("admin_dashboard" if role == "admin" else "student_dashboard")


def login_required(role):
    """Allow only logged-in users with the given role ('admin' or 'student')."""
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if "role" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session["role"] != role:
                abort(403)
            # Make sure the account still exists / is still active
            if role == "student":
                user = query("SELECT status FROM students WHERE student_id=%s",
                             (session["user_id"],), one=True)
                if not user or user["status"] != "active":
                    session.clear()
                    flash("Your account is deactivated. Please contact the admin.", "danger")
                    return redirect(url_for("login"))
            else:
                if not query("SELECT 1 AS ok FROM admins WHERE admin_id=%s",
                             (session["user_id"],), one=True):
                    session.clear()
                    return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapper
    return decorator


def to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


# ----------------------------------------------------------------------
# Public / authentication routes
# ----------------------------------------------------------------------
@app.route("/")
def index():
    if "role" in session:
        return redirect(dashboard_for(session["role"]))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if "role" in session:
        return redirect(dashboard_for(session["role"]))
    form = {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("full_name", "email", "mobile")}
        form["email"] = form["email"].lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        errors = []

        if len(form["full_name"]) < 3:
            errors.append("Full name must be at least 3 characters long.")
        if not EMAIL_RE.match(form["email"]):
            errors.append("Please enter a valid email address.")
        if not MOBILE_RE.match(form["mobile"]):
            errors.append("Mobile number must contain exactly 10 digits.")
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            errors.append("Password must be at least 8 characters and contain letters and numbers.")
        if password != confirm:
            errors.append("Password and confirm password do not match.")
        if not errors and query("SELECT 1 AS x FROM students WHERE email=%s",
                                (form["email"],), one=True):
            errors.append("This email address is already registered.")

        if not errors:
            try:
                execute("INSERT INTO students (full_name, email, mobile, password) "
                        "VALUES (%s, %s, %s, %s)",
                        (form["full_name"], form["email"], form["mobile"],
                         generate_password_hash(password)))
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for("login"))
            except mysql.connector.IntegrityError:
                errors.append("This email address is already registered.")
        for e in errors:
            flash(e, "danger")
    return render_template("register.html", form=form)


@app.route("/login", methods=["GET", "POST"])
def login():
    if "role" in session:
        return redirect(dashboard_for(session["role"]))
    if request.method == "POST":
        role = request.form.get("role", "student")
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash("Please enter your email/username and password.", "danger")
            return render_template("login.html", role=role)

        if role == "admin":
            user = query("SELECT * FROM admins WHERE email=%s OR username=%s",
                         (identifier.lower(), identifier), one=True)
            id_field, name_field = "admin_id", "username"
        else:
            role = "student"
            user = query("SELECT * FROM students WHERE email=%s",
                         (identifier.lower(),), one=True)
            id_field, name_field = "student_id", "full_name"

        if not user or not check_password_hash(user["password"], password):
            flash("Invalid login credentials.", "danger")
            return render_template("login.html", role=role)
        if role == "student" and user["status"] != "active":
            flash("Your account is deactivated. Please contact the admin.", "danger")
            return render_template("login.html", role=role)

        session.clear()  # prevents session fixation
        session.permanent = True
        session["role"] = role
        session["user_id"] = user[id_field]
        session["name"] = user[name_field]
        flash(f"Welcome back, {user[name_field]}!", "success")
        return redirect(dashboard_for(role))
    return render_template("login.html", role=request.args.get("role", "student"))


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ----------------------------------------------------------------------
# Admin: dashboard
# ----------------------------------------------------------------------
@app.route("/admin")
def admin_root():
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/dashboard")
@login_required("admin")
def admin_dashboard():
    stats = {
        "students": query("SELECT COUNT(*) AS c FROM students", one=True)["c"],
        "exams": query("SELECT COUNT(*) AS c FROM exams", one=True)["c"],
        "questions": query("SELECT COUNT(*) AS c FROM questions", one=True)["c"],
        "attempts": query("SELECT COUNT(*) AS c FROM exam_attempts", one=True)["c"],
    }
    recent = query("""SELECT r.*, s.full_name, e.title
                      FROM results r
                      JOIN students s ON s.student_id = r.student_id
                      JOIN exams e ON e.exam_id = r.exam_id
                      ORDER BY r.created_at DESC LIMIT 8""")
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


# ----------------------------------------------------------------------
# Admin: exam management
# ----------------------------------------------------------------------
def read_exam_form(form):
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "duration": to_int(form.get("duration")),
        "total_marks": to_int(form.get("total_marks")),
        "passing_marks": to_int(form.get("passing_marks")),
        "status": form.get("status", "inactive"),
        "allow_multiple_attempts": 1 if form.get("allow_multiple_attempts") else 0,
    }
    errors = []
    if len(data["title"]) < 3:
        errors.append("Exam title must be at least 3 characters long.")
    if not data["duration"] or data["duration"] < 1 or data["duration"] > 600:
        errors.append("Duration must be between 1 and 600 minutes.")
    if not data["total_marks"] or data["total_marks"] < 1:
        errors.append("Total marks must be a positive number.")
    if data["passing_marks"] is None or data["passing_marks"] < 0:
        errors.append("Passing marks must be zero or more.")
    elif data["total_marks"] and data["passing_marks"] > data["total_marks"]:
        errors.append("Passing marks cannot be greater than total marks.")
    if data["status"] not in ("active", "inactive"):
        errors.append("Invalid exam status.")
    return data, errors


def get_exam_or_404(exam_id):
    exam = query("SELECT * FROM exams WHERE exam_id=%s", (exam_id,), one=True)
    if not exam:
        abort(404)
    return exam


@app.route("/admin/exams")
@login_required("admin")
def admin_exams():
    exams = query("""SELECT e.*,
                     (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.exam_id) AS question_count,
                     (SELECT COUNT(*) FROM exam_attempts a WHERE a.exam_id = e.exam_id) AS attempt_count
                     FROM exams e ORDER BY e.created_at DESC, e.exam_id DESC""")
    return render_template("admin/exams.html", exams=exams)


@app.route("/admin/exams/add", methods=["GET", "POST"])
@login_required("admin")
def admin_add_exam():
    exam = {"status": "active", "allow_multiple_attempts": 0}
    if request.method == "POST":
        exam, errors = read_exam_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            exam_id = execute("""INSERT INTO exams (title, description, duration, total_marks,
                                 passing_marks, status, allow_multiple_attempts)
                                 VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                              (exam["title"], exam["description"], exam["duration"],
                               exam["total_marks"], exam["passing_marks"], exam["status"],
                               exam["allow_multiple_attempts"]))
            flash("Exam created. Now add questions to it.", "success")
            return redirect(url_for("admin_questions", exam_id=exam_id))
    return render_template("admin/add_exam.html", exam=exam)


@app.route("/admin/exams/edit/<int:exam_id>", methods=["GET", "POST"])
@login_required("admin")
def admin_edit_exam(exam_id):
    exam = get_exam_or_404(exam_id)
    if request.method == "POST":
        data, errors = read_exam_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            data["exam_id"] = exam_id
            exam = data
        else:
            execute("""UPDATE exams SET title=%s, description=%s, duration=%s, total_marks=%s,
                       passing_marks=%s, status=%s, allow_multiple_attempts=%s
                       WHERE exam_id=%s""",
                    (data["title"], data["description"], data["duration"], data["total_marks"],
                     data["passing_marks"], data["status"], data["allow_multiple_attempts"],
                     exam_id))
            flash("Exam updated successfully.", "success")
            return redirect(url_for("admin_exams"))
    return render_template("admin/edit_exam.html", exam=exam)


@app.route("/admin/exams/delete/<int:exam_id>", methods=["POST"])
@login_required("admin")
def admin_delete_exam(exam_id):
    get_exam_or_404(exam_id)
    execute("DELETE FROM exams WHERE exam_id=%s", (exam_id,))
    flash("Exam and all its questions, attempts and results were deleted.", "success")
    return redirect(url_for("admin_exams"))


@app.route("/admin/exams/toggle/<int:exam_id>", methods=["POST"])
@login_required("admin")
def admin_toggle_exam(exam_id):
    exam = get_exam_or_404(exam_id)
    new_status = "inactive" if exam["status"] == "active" else "active"
    execute("UPDATE exams SET status=%s WHERE exam_id=%s", (new_status, exam_id))
    flash(f"Exam is now {new_status}.", "success")
    return redirect(url_for("admin_exams"))


# ----------------------------------------------------------------------
# Admin: question management
# ----------------------------------------------------------------------
def read_question_form(form):
    data = {
        "question_text": form.get("question_text", "").strip(),
        "option_a": form.get("option_a", "").strip(),
        "option_b": form.get("option_b", "").strip(),
        "option_c": form.get("option_c", "").strip(),
        "option_d": form.get("option_d", "").strip(),
        "correct_option": form.get("correct_option", ""),
        "marks": to_int(form.get("marks")),
    }
    errors = []
    if len(data["question_text"]) < 5:
        errors.append("Question text must be at least 5 characters long.")
    for letter in "abcd":
        if not data[f"option_{letter}"]:
            errors.append(f"Option {letter.upper()} is required.")
        elif len(data[f"option_{letter}"]) > 255:
            errors.append(f"Option {letter.upper()} is too long (max 255 characters).")
    if data["correct_option"] not in OPTIONS:
        errors.append("Please select the correct answer.")
    if not data["marks"] or data["marks"] < 1:
        errors.append("Marks must be a positive number.")
    return data, errors


@app.route("/admin/questions/<int:exam_id>")
@login_required("admin")
def admin_questions(exam_id):
    exam = get_exam_or_404(exam_id)
    questions = query("SELECT * FROM questions WHERE exam_id=%s ORDER BY question_id", (exam_id,))
    marks_sum = sum(q["marks"] for q in questions)
    return render_template("admin/questions.html", exam=exam, questions=questions,
                           marks_sum=marks_sum)


@app.route("/admin/questions/add/<int:exam_id>", methods=["GET", "POST"])
@login_required("admin")
def admin_add_question(exam_id):
    exam = get_exam_or_404(exam_id)
    question = {"marks": 1}
    if request.method == "POST":
        question, errors = read_question_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
        else:
            execute("""INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c,
                       option_d, correct_option, marks) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (exam_id, question["question_text"], question["option_a"], question["option_b"],
                     question["option_c"], question["option_d"], question["correct_option"],
                     question["marks"]))
            flash("Question added successfully.", "success")
            if request.form.get("save_and_add"):
                return redirect(url_for("admin_add_question", exam_id=exam_id))
            return redirect(url_for("admin_questions", exam_id=exam_id))
    return render_template("admin/add_question.html", exam=exam, question=question)


@app.route("/admin/questions/edit/<int:question_id>", methods=["GET", "POST"])
@login_required("admin")
def admin_edit_question(question_id):
    question = query("SELECT * FROM questions WHERE question_id=%s", (question_id,), one=True)
    if not question:
        abort(404)
    exam = get_exam_or_404(question["exam_id"])
    if request.method == "POST":
        data, errors = read_question_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            data["question_id"] = question_id
            question = data
        else:
            execute("""UPDATE questions SET question_text=%s, option_a=%s, option_b=%s, option_c=%s,
                       option_d=%s, correct_option=%s, marks=%s WHERE question_id=%s""",
                    (data["question_text"], data["option_a"], data["option_b"], data["option_c"],
                     data["option_d"], data["correct_option"], data["marks"], question_id))
            flash("Question updated successfully.", "success")
            return redirect(url_for("admin_questions", exam_id=exam["exam_id"]))
    return render_template("admin/edit_question.html", exam=exam, question=question)


@app.route("/admin/questions/delete/<int:question_id>", methods=["POST"])
@login_required("admin")
def admin_delete_question(question_id):
    question = query("SELECT exam_id FROM questions WHERE question_id=%s", (question_id,), one=True)
    if not question:
        abort(404)
    execute("DELETE FROM questions WHERE question_id=%s", (question_id,))
    flash("Question deleted.", "success")
    return redirect(url_for("admin_questions", exam_id=question["exam_id"]))


# ----------------------------------------------------------------------
# Admin: students and results
# ----------------------------------------------------------------------
@app.route("/admin/students")
@login_required("admin")
def admin_students():
    search = request.args.get("q", "").strip()
    sql = """SELECT s.*,
             (SELECT COUNT(*) FROM exam_attempts a
              WHERE a.student_id = s.student_id AND a.status='submitted') AS attempts
             FROM students s"""
    params = []
    if search:
        sql += " WHERE s.full_name LIKE %s OR s.email LIKE %s"
        params = [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY s.created_at DESC, s.student_id DESC"
    return render_template("admin/students.html", students=query(sql, params), search=search)


@app.route("/admin/students/toggle/<int:student_id>", methods=["POST"])
@login_required("admin")
def admin_toggle_student(student_id):
    student = query("SELECT * FROM students WHERE student_id=%s", (student_id,), one=True)
    if not student:
        abort(404)
    new_status = "inactive" if student["status"] == "active" else "active"
    execute("UPDATE students SET status=%s WHERE student_id=%s", (new_status, student_id))
    flash(f"{student['full_name']}'s account is now {new_status}.", "success")
    return redirect(request.referrer or url_for("admin_students"))


@app.route("/admin/results")
@login_required("admin")
def admin_results():
    search = request.args.get("q", "").strip()
    exam_id = to_int(request.args.get("exam_id"))
    sql = """SELECT r.*, s.full_name, s.email, e.title, a.submission_time
             FROM results r
             JOIN students s ON s.student_id = r.student_id
             JOIN exams e ON e.exam_id = r.exam_id
             JOIN exam_attempts a ON a.attempt_id = r.attempt_id
             WHERE 1=1"""
    params = []
    if search:
        sql += " AND s.full_name LIKE %s"
        params.append(f"%{search}%")
    if exam_id:
        sql += " AND r.exam_id = %s"
        params.append(exam_id)
    sql += " ORDER BY a.submission_time DESC, r.result_id DESC"
    exams = query("SELECT exam_id, title FROM exams ORDER BY title")
    return render_template("admin/results.html", results=query(sql, params), exams=exams,
                           search=search, exam_id=exam_id)


# ----------------------------------------------------------------------
# Student: exam helpers
# ----------------------------------------------------------------------
def finalize_attempt(attempt_id):
    """Grade an attempt ON THE SERVER and store the result.
    Marks are always calculated from the database, never taken from the browser."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM exam_attempts WHERE attempt_id=%s FOR UPDATE", (attempt_id,))
        attempt = cur.fetchone()
        if not attempt or attempt["status"] == "submitted":
            db.rollback()
            return
        cur.execute("SELECT * FROM exams WHERE exam_id=%s", (attempt["exam_id"],))
        exam = cur.fetchone()
        cur.execute("""SELECT q.question_id, q.correct_option, q.marks,
                              a.answer_id, a.selected_option
                       FROM questions q
                       LEFT JOIN answers a ON a.question_id = q.question_id AND a.attempt_id = %s
                       WHERE q.exam_id = %s""", (attempt_id, attempt["exam_id"]))
        obtained = 0
        for row in cur.fetchall():
            if row["answer_id"] is None:
                continue  # unanswered question
            marks = row["marks"] if row["selected_option"] == row["correct_option"] else 0
            obtained += marks
            cur.execute("UPDATE answers SET marks_obtained=%s WHERE answer_id=%s",
                        (marks, row["answer_id"]))

        total = exam["total_marks"]
        percentage = min(round(obtained * 100.0 / total, 2), 100) if total else 0
        status = "Pass" if obtained >= exam["passing_marks"] else "Fail"
        deadline = attempt["start_time"] + timedelta(minutes=exam["duration"])
        submitted_at = min(datetime.now(), deadline)

        cur.execute("UPDATE exam_attempts SET status='submitted', submission_time=%s "
                    "WHERE attempt_id=%s", (submitted_at, attempt_id))
        cur.execute("""INSERT INTO results (attempt_id, student_id, exam_id, marks_obtained,
                       total_marks, percentage, result_status) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (attempt_id, attempt["student_id"], attempt["exam_id"], obtained, total,
                     percentage, status))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def get_own_attempt(attempt_id):
    """Fetch an attempt only if it belongs to the logged-in student."""
    attempt = query("""SELECT a.*, e.title, e.duration
                       FROM exam_attempts a JOIN exams e ON e.exam_id = a.exam_id
                       WHERE a.attempt_id=%s AND a.student_id=%s""",
                    (attempt_id, session["user_id"]), one=True)
    if not attempt:
        abort(404)
    attempt["deadline"] = attempt["start_time"] + timedelta(minutes=attempt["duration"])
    return attempt


def exams_with_status(student_id):
    return query("""SELECT e.*,
        (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.exam_id) AS question_count,
        (SELECT COUNT(*) FROM exam_attempts a WHERE a.exam_id = e.exam_id
            AND a.student_id = %s AND a.status = 'submitted') AS submitted_count,
        (SELECT a.attempt_id FROM exam_attempts a WHERE a.exam_id = e.exam_id
            AND a.student_id = %s AND a.status = 'in_progress' LIMIT 1) AS active_attempt
        FROM exams e WHERE e.status = 'active' ORDER BY e.created_at DESC, e.exam_id DESC""",
                 (student_id, student_id))


def save_answer_row(attempt_id, question_id, option):
    execute("""INSERT INTO answers (attempt_id, question_id, selected_option)
               VALUES (%s,%s,%s)
               ON DUPLICATE KEY UPDATE selected_option = VALUES(selected_option)""",
            (attempt_id, question_id, option))


# ----------------------------------------------------------------------
# Student routes
# ----------------------------------------------------------------------
@app.route("/student/dashboard")
@login_required("student")
def student_dashboard():
    sid = session["user_id"]
    attempted = query("SELECT COUNT(*) AS c FROM exam_attempts WHERE student_id=%s "
                      "AND status='submitted'", (sid,), one=True)["c"]
    exams = exams_with_status(sid)
    recent = query("""SELECT r.*, e.title, a.submission_time
                      FROM results r
                      JOIN exams e ON e.exam_id = r.exam_id
                      JOIN exam_attempts a ON a.attempt_id = r.attempt_id
                      WHERE r.student_id=%s ORDER BY a.submission_time DESC LIMIT 5""", (sid,))
    return render_template("student/dashboard.html", attempted=attempted,
                           exams=exams[:4], exam_total=len(exams), recent=recent)


@app.route("/student/exams")
@login_required("student")
def student_exams():
    return render_template("student/available_exams.html",
                           exams=exams_with_status(session["user_id"]))


@app.route("/student/exam/<int:exam_id>")
@login_required("student")
def exam_instructions(exam_id):
    exam = query("""SELECT e.*, (SELECT COUNT(*) FROM questions q WHERE q.exam_id = e.exam_id)
                    AS question_count FROM exams e WHERE e.exam_id=%s AND e.status='active'""",
                 (exam_id,), one=True)
    if not exam:
        flash("This exam is not available.", "warning")
        return redirect(url_for("student_exams"))
    return render_template("student/exam_instructions.html", exam=exam)


@app.route("/student/start-exam/<int:exam_id>", methods=["POST"])
@login_required("student")
def start_exam(exam_id):
    sid = session["user_id"]
    exam = query("SELECT * FROM exams WHERE exam_id=%s AND status='active'", (exam_id,), one=True)
    if not exam:
        flash("This exam is not available.", "warning")
        return redirect(url_for("student_exams"))
    if query("SELECT COUNT(*) AS c FROM questions WHERE exam_id=%s", (exam_id,), one=True)["c"] == 0:
        flash("This exam has no questions yet.", "warning")
        return redirect(url_for("student_exams"))

    # Resume an unfinished attempt (timer keeps running from the saved start time)
    open_attempt = query("SELECT * FROM exam_attempts WHERE student_id=%s AND exam_id=%s "
                         "AND status='in_progress'", (sid, exam_id), one=True)
    if open_attempt:
        deadline = open_attempt["start_time"] + timedelta(minutes=exam["duration"])
        if datetime.now() < deadline:
            return redirect(url_for("take_exam", attempt_id=open_attempt["attempt_id"]))
        finalize_attempt(open_attempt["attempt_id"])  # time is over -> grade it now

    done = query("SELECT COUNT(*) AS c FROM exam_attempts WHERE student_id=%s AND exam_id=%s "
                 "AND status='submitted'", (sid, exam_id), one=True)["c"]
    if done and not exam["allow_multiple_attempts"]:
        flash("You have already attempted this exam. Multiple attempts are not allowed.", "warning")
        return redirect(url_for("my_results"))

    attempt_id = execute("INSERT INTO exam_attempts (student_id, exam_id, start_time, status) "
                         "VALUES (%s,%s,%s,'in_progress')", (sid, exam_id, datetime.now()))
    return redirect(url_for("take_exam", attempt_id=attempt_id))


@app.route("/student/take-exam/<int:attempt_id>")
@login_required("student")
def take_exam(attempt_id):
    attempt = get_own_attempt(attempt_id)
    if attempt["status"] == "submitted":
        return redirect(url_for("student_result", attempt_id=attempt_id))

    remaining = int((attempt["deadline"] - datetime.now()).total_seconds())
    if remaining <= 0:
        finalize_attempt(attempt_id)
        flash("Time is over. Your exam was submitted automatically.", "info")
        return redirect(url_for("student_result", attempt_id=attempt_id))

    # NOTE: correct_option is deliberately NOT selected here
    questions = query("""SELECT question_id, question_text, option_a, option_b, option_c,
                                option_d, marks
                         FROM questions WHERE exam_id=%s ORDER BY question_id""",
                      (attempt["exam_id"],))
    saved = {row["question_id"]: row["selected_option"] for row in
             query("SELECT question_id, selected_option FROM answers WHERE attempt_id=%s",
                   (attempt_id,))}
    return render_template("student/take_exam.html", attempt=attempt, questions=questions,
                           saved=saved, remaining=remaining)


@app.route("/student/save-answer/<int:attempt_id>", methods=["POST"])
@login_required("student")
def save_answer(attempt_id):
    """AJAX auto-save so answers survive a page refresh."""
    attempt = get_own_attempt(attempt_id)
    if attempt["status"] != "in_progress" or datetime.now() > attempt["deadline"] + timedelta(seconds=GRACE_SECONDS):
        return jsonify(ok=False, message="Exam is closed"), 400
    data = request.get_json(silent=True) or {}
    question_id = to_int(data.get("question_id"))
    option = data.get("option")
    valid = query("SELECT 1 AS ok FROM questions WHERE question_id=%s AND exam_id=%s",
                  (question_id, attempt["exam_id"]), one=True)
    if not valid:
        return jsonify(ok=False, message="Invalid question"), 400
    if option is None:
        execute("DELETE FROM answers WHERE attempt_id=%s AND question_id=%s",
                (attempt_id, question_id))
    elif option in OPTIONS:
        save_answer_row(attempt_id, question_id, option)
    else:
        return jsonify(ok=False, message="Invalid option"), 400
    return jsonify(ok=True)


@app.route("/student/submit-exam/<int:attempt_id>", methods=["POST"])
@login_required("student")
def submit_exam(attempt_id):
    attempt = get_own_attempt(attempt_id)
    if attempt["status"] == "submitted":
        return redirect(url_for("student_result", attempt_id=attempt_id))

    # Apply the final answers from the form only if the time limit has not passed
    if datetime.now() <= attempt["deadline"] + timedelta(seconds=GRACE_SECONDS):
        valid_ids = {q["question_id"] for q in
                     query("SELECT question_id FROM questions WHERE exam_id=%s",
                           (attempt["exam_id"],))}
        for key, value in request.form.items():
            if key.startswith("q_") and key[2:].isdigit() and value in OPTIONS \
                    and int(key[2:]) in valid_ids:
                save_answer_row(attempt_id, int(key[2:]), value)

    finalize_attempt(attempt_id)
    flash("Exam submitted successfully.", "success")
    return redirect(url_for("student_result", attempt_id=attempt_id))


@app.route("/student/result/<int:attempt_id>")
@login_required("student")
def student_result(attempt_id):
    result = query("""SELECT r.*, s.full_name, e.title, e.passing_marks,
                             a.start_time, a.submission_time
                      FROM results r
                      JOIN students s ON s.student_id = r.student_id
                      JOIN exams e ON e.exam_id = r.exam_id
                      JOIN exam_attempts a ON a.attempt_id = r.attempt_id
                      WHERE r.attempt_id=%s AND r.student_id=%s""",
                   (attempt_id, session["user_id"]), one=True)
    if not result:
        # still running? send the student back to the exam, otherwise 404
        running = query("SELECT 1 AS ok FROM exam_attempts WHERE attempt_id=%s AND student_id=%s "
                        "AND status='in_progress'", (attempt_id, session["user_id"]), one=True)
        if running:
            return redirect(url_for("take_exam", attempt_id=attempt_id))
        abort(404)
    return render_template("student/result.html", r=result)


@app.route("/student/my-results")
@login_required("student")
def my_results():
    results = query("""SELECT r.*, e.title, a.submission_time
                       FROM results r
                       JOIN exams e ON e.exam_id = r.exam_id
                       JOIN exam_attempts a ON a.attempt_id = r.attempt_id
                       WHERE r.student_id=%s ORDER BY a.submission_time DESC""",
                    (session["user_id"],))
    return render_template("student/my_results.html", results=results)


# ----------------------------------------------------------------------
@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    if request.endpoint in ("take_exam", "student_result", "my_results"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1")
