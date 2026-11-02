"""
Secure way to create the initial Admin account.
Usage:  python create_admin.py
The password is typed in the terminal (hidden) and stored only as a hash.
"""
import getpass
import re
import sys

import mysql.connector
from werkzeug.security import generate_password_hash

from config import db_settings


def main():
    print("=== Create Admin Account ===")
    username = input("Username: ").strip()
    email = input("Email: ").strip().lower()
    password = getpass.getpass("Password (min 8 chars, letters + numbers): ")
    confirm = getpass.getpass("Confirm password: ")

    if len(username) < 3:
        sys.exit("Username must be at least 3 characters.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        sys.exit("Invalid email address.")
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        sys.exit("Password must be at least 8 characters with letters and numbers.")
    if password != confirm:
        sys.exit("Passwords do not match.")

    db = mysql.connector.connect(**db_settings())
    cur = db.cursor()
    try:
        cur.execute("INSERT INTO admins (username, email, password) VALUES (%s,%s,%s)",
                    (username, email, generate_password_hash(password)))
        db.commit()
        print(f"Admin '{username}' created successfully.")
    except mysql.connector.IntegrityError:
        print("An admin with that username or email already exists.")
    finally:
        cur.close()
        db.close()


if __name__ == "__main__":
    main()
