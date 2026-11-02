"""Application configuration. Values are read from the .env file (see .env.example)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")

    # MySQL connection settings
    MYSQL_HOST = os.environ.get("MYSQL_HOST", "localhost")
    MYSQL_USER = os.environ.get("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", "online_exam_system")

    # Session / CSRF security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=6)
    WTF_CSRF_TIME_LIMIT = None  # CSRF token valid for the whole session


def db_settings():
    """Connection arguments shared by app.py and the helper scripts."""
    return {
        "host": Config.MYSQL_HOST,
        "user": Config.MYSQL_USER,
        "password": Config.MYSQL_PASSWORD,
        "database": Config.MYSQL_DATABASE,
    }
