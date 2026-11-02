"""
Inserts sample data for testing:
  1 admin, 5 students, 3 exams, 10 questions per exam.
Usage:  python seed_data.py        (safe to run more than once)

Sample logins
  Admin   : admin@exam.com   / Admin@123
  Students: student1@example.com ... student5@example.com / Student@123
"""
import mysql.connector
from werkzeug.security import generate_password_hash

from config import db_settings

ADMIN = ("admin", "admin@exam.com", "Admin@123")

STUDENTS = [
    ("Aarav Sharma", "student1@example.com", "9876543210"),
    ("Priya Patil", "student2@example.com", "9876543211"),
    ("Rohan Deshmukh", "student3@example.com", "9876543212"),
    ("Sneha Kulkarni", "student4@example.com", "9876543213"),
    ("Vikram Joshi", "student5@example.com", "9876543214"),
]

# (question, A, B, C, D, correct)
PYTHON_QS = [
    ("Which keyword is used to define a function in Python?", "func", "def", "function", "define", "B"),
    ("What is the output of print(type([]))?", "<class 'list'>", "<class 'tuple'>", "<class 'dict'>", "<class 'set'>", "A"),
    ("Which of the following data types is immutable?", "list", "dict", "tuple", "set", "C"),
    ("What does len('Python') return?", "5", "6", "7", "Error", "B"),
    ("Which symbol is used for a single-line comment in Python?", "//", "#", "/* */", "--", "B"),
    ("What is the result of 2 ** 3 in Python?", "6", "9", "8", "5", "C"),
    ("Which list method adds an item at the end of the list?", "add()", "insert()", "push()", "append()", "D"),
    ("What is the correct file extension for Python files?", ".py", ".python", ".pt", ".pyt", "A"),
    ("What does range(3) generate?", "1, 2, 3", "0, 1, 2", "0, 1, 2, 3", "1, 2", "B"),
    ("Which block is used to handle exceptions in Python?", "try...catch", "try...except", "catch...finally", "handle...error", "B"),
]

DBMS_QS = [
    ("What does DBMS stand for?", "Database Management System", "Data Backup Management System", "Digital Base Management Software", "Data Binding and Mapping System", "A"),
    ("Which SQL command is used to retrieve data from a table?", "INSERT", "SELECT", "UPDATE", "DELETE", "B"),
    ("Which statement about a PRIMARY KEY is correct?", "It allows duplicate values", "It uniquely identifies each record", "It can always be NULL", "A table can have many primary keys", "B"),
    ("Which normal form removes partial dependency?", "1NF", "2NF", "3NF", "BCNF", "B"),
    ("Which SQL command removes a table completely from the database?", "DELETE", "REMOVE", "DROP", "CLEAR", "C"),
    ("A FOREIGN KEY is used to:", "Refer to the primary key of another table", "Encrypt table data", "Sort the records", "Create an index only", "A"),
    ("In ACID properties, what does 'A' stand for?", "Availability", "Atomicity", "Accuracy", "Authorization", "B"),
    ("Which clause is used to filter rows in an SQL query?", "ORDER BY", "GROUP BY", "WHERE", "LIMIT", "C"),
    ("Which JOIN returns only the rows that match in both tables?", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "CROSS JOIN", "C"),
    ("Which command makes a transaction permanent?", "ROLLBACK", "COMMIT", "SAVEPOINT", "REVOKE", "B"),
]

CF_QS = [
    ("Which part is known as the 'brain' of the computer?", "Monitor", "CPU", "RAM", "Keyboard", "B"),
    ("Which of the following is an input device?", "Printer", "Monitor", "Scanner", "Speaker", "C"),
    ("How many bits are there in one byte?", "4", "8", "16", "32", "B"),
    ("What does RAM stand for?", "Random Access Memory", "Read Access Memory", "Run Active Memory", "Rapid Application Memory", "A"),
    ("Which of the following is an operating system?", "MS Word", "Windows", "Google Chrome", "Photoshop", "B"),
    ("What is the base of the binary number system?", "2", "8", "10", "16", "A"),
    ("Which of the following is a volatile memory?", "ROM", "Hard disk", "RAM", "Pen drive", "C"),
    ("What is the full form of URL?", "Universal Resource Link", "Uniform Route Locator", "Uniform Resource Locator", "Unified Reference Location", "C"),
    ("Which device forwards data packets between computer networks?", "Monitor", "Router", "Scanner", "Speaker", "B"),
    ("Which keyboard shortcut is used to copy in Windows?", "Ctrl + V", "Ctrl + C", "Ctrl + X", "Ctrl + Z", "B"),
]

# (title, description, duration, marks per question, passing marks, multiple attempts, questions)
EXAMS = [
    ("Python Programming Basics", "Basic concepts of Python: syntax, data types, functions and exceptions.", 15, 1, 4, 0, PYTHON_QS),
    ("Database Management System", "Fundamentals of DBMS, SQL commands, keys, normalization and transactions.", 20, 2, 8, 0, DBMS_QS),
    ("Computer Fundamentals", "Basic computer knowledge: hardware, software, memory and networking.", 10, 1, 4, 1, CF_QS),
]


def main():
    db = mysql.connector.connect(**db_settings())
    cur = db.cursor()

    cur.execute("SELECT 1 FROM admins WHERE email=%s", (ADMIN[1],))
    if not cur.fetchone():
        cur.execute("INSERT INTO admins (username, email, password) VALUES (%s,%s,%s)",
                    (ADMIN[0], ADMIN[1], generate_password_hash(ADMIN[2])))
        print("Admin created.")

    for name, email, mobile in STUDENTS:
        cur.execute("SELECT 1 FROM students WHERE email=%s", (email,))
        if not cur.fetchone():
            cur.execute("INSERT INTO students (full_name, email, mobile, password) VALUES (%s,%s,%s,%s)",
                        (name, email, mobile, generate_password_hash("Student@123")))
            print(f"Student created: {email}")

    for title, desc, duration, marks, passing, multi, questions in EXAMS:
        cur.execute("SELECT 1 FROM exams WHERE title=%s", (title,))
        if cur.fetchone():
            continue
        cur.execute("""INSERT INTO exams (title, description, duration, total_marks, passing_marks,
                       status, allow_multiple_attempts) VALUES (%s,%s,%s,%s,%s,'active',%s)""",
                    (title, desc, duration, marks * len(questions), passing, multi))
        exam_id = cur.lastrowid
        for q in questions:
            cur.execute("""INSERT INTO questions (exam_id, question_text, option_a, option_b,
                           option_c, option_d, correct_option, marks)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""", (exam_id, *q, marks))
        print(f"Exam created: {title} ({len(questions)} questions)")

    db.commit()
    cur.close()
    db.close()
    print("Sample data ready.")


if __name__ == "__main__":
    main()
