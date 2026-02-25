from pathlib import Path
import sqlite3, uuid
from passlib.hash import pbkdf2_sha256

AUTH_DB_PATH = Path(__file__).resolve().parent.parent / "auth.db"
# backend/auth.py -> parent.parent = project root
SESSIONS = {}  # session_token -> user_id (hackathon only)

def init_auth_db():
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=10)
    print("AUTH_DB_PATH =", AUTH_DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        password_hash TEXT
    )
    """)
    conn.commit()
    conn.close()

def create_user(username: str, password: str) -> str:
    user_id = str(uuid.uuid4())
    pw_hash = pbkdf2_sha256.hash(password)

    conn = sqlite3.connect(AUTH_DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("INSERT INTO users(user_id, username, password_hash) VALUES(?,?,?)",
                (user_id, username, pw_hash))
    conn.commit()
    conn.close()
    return user_id

def verify_user(username: str, password: str) -> str | None:
    conn = sqlite3.connect(AUTH_DB_PATH, timeout=10)
    cur = conn.cursor()
    cur.execute("SELECT user_id, password_hash FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    user_id, pw_hash = row
    return user_id if pbkdf2_sha256.verify(password, pw_hash) else None

def new_session(user_id: str) -> str:
    # invalidate old tokens for this user
    for t, uid in list(SESSIONS.items()):
        if uid == user_id:
            del SESSIONS[t]
    token = str(uuid.uuid4())
    SESSIONS[token] = user_id
    return token

def user_from_session(token: str) -> str | None:
    return SESSIONS.get(token)