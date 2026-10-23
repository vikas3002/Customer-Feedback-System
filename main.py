import hashlib
import os
import secrets
import sqlite3
from contextlib import contextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Customer Feedback")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "feedback.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str, salt: str = None):
    salt = salt or secrets.token_hex(8)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return salt, pw_hash


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT,
                salt TEXT,
                password_hash TEXT,
                role TEXT DEFAULT 'user'
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        if not conn.execute("SELECT 1 FROM users WHERE role = 'admin'").fetchone():
            salt, pw_hash = hash_password("admin123")
            conn.execute(
                "INSERT INTO users (username, email, salt, password_hash, role) VALUES (?, ?, ?, ?, 'admin')",
                ("admin", "admin@example.com", salt, pw_hash)
            )

init_db()


def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in.")
    token = authorization.split("Bearer ")[1].strip()
    with get_db() as conn:
        user = conn.execute(
            "SELECT u.id, u.username, u.email, u.role FROM sessions s "
            "JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,)
        ).fetchone()
    if not user:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    return dict(user)


def require_admin(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required.")
    return user


class RegisterForm(BaseModel):
    username: str
    email: str
    password: str
    confirm_password: str = ""


class LoginForm(BaseModel):
    username: str
    password: str


class FeedbackForm(BaseModel):
    text: str


def get_feedback(where="", args=()):
    with get_db() as conn:
        row = conn.execute(
            f"SELECT f.*, u.username FROM feedback f JOIN users u ON u.id = f.user_id {where}", args
        ).fetchone()
        return dict(row) if row else None


@app.post("/api/register")
def register(data: RegisterForm):
    if not data.username or not data.email or not data.password:
        raise HTTPException(400, "All fields are required.")
    if data.confirm_password and data.password != data.confirm_password:
        raise HTTPException(400, "Passwords do not match.")

    salt, pw_hash = hash_password(data.password)
    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, email, salt, password_hash) VALUES (?, ?, ?, ?)",
                (data.username, data.email, salt, pw_hash)
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That username is already taken.")
    return {"message": "Account created. You can log in now."}


@app.post("/api/login")
def login(data: LoginForm):
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (data.username,)).fetchone()
        if not user:
            raise HTTPException(401, "Incorrect username or password.")
        _, pw_hash = hash_password(data.password, user["salt"])
        if pw_hash != user["password_hash"]:
            raise HTTPException(401, "Incorrect username or password.")

        token = secrets.token_hex(24)
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
    return {"token": token, "username": user["username"], "role": user["role"]}


@app.post("/api/logout")
def logout(authorization: str = Header(None)):
    if authorization and "Bearer " in authorization:
        token = authorization.split("Bearer ")[1].strip()
        with get_db() as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"message": "Logged out."}


@app.get("/api/me")
def me(user=Depends(get_current_user)):
    return user


@app.get("/api/feedback/mine")
def my_feedback(user=Depends(get_current_user)):
    return {"feedback": get_feedback("WHERE f.user_id = ?", (user["id"],))}


@app.post("/api/feedback")
def add_feedback(data: FeedbackForm, user=Depends(get_current_user)):
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Feedback cannot be empty.")
    if get_feedback("WHERE f.user_id = ?", (user["id"],)):
        raise HTTPException(409, "You already submitted feedback. Use Edit Feedback to change it.")
    with get_db() as conn:
        conn.execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", (user["id"], text))
    return {"feedback": get_feedback("WHERE f.user_id = ?", (user["id"],))}


@app.put("/api/feedback/mine")
def edit_my_feedback(data: FeedbackForm, user=Depends(get_current_user)):
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Feedback cannot be empty.")
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE feedback SET text = ?, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (text, user["id"])
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "You have not submitted feedback yet. Use Add Feedback first.")
    return {"feedback": get_feedback("WHERE f.user_id = ?", (user["id"],))}


@app.get("/api/admin/feedback")
def admin_list(admin=Depends(require_admin)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT f.*, u.username FROM feedback f JOIN users u ON u.id = f.user_id ORDER BY f.id DESC"
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@app.post("/api/admin/feedback")
def admin_create(data: FeedbackForm, admin=Depends(require_admin)):
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Feedback cannot be empty.")
    with get_db() as conn:
        cur = conn.execute("INSERT INTO feedback (user_id, text) VALUES (?, ?)", (admin["id"], text))
    return get_feedback("WHERE f.id = ?", (cur.lastrowid,))


@app.put("/api/admin/feedback/{fid}")
def admin_update(fid: int, data: FeedbackForm, admin=Depends(require_admin)):
    text = data.text.strip()
    if not text:
        raise HTTPException(400, "Feedback cannot be empty.")
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE feedback SET text = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (text, fid)
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Feedback not found.")
    return get_feedback("WHERE f.id = ?", (fid,))


@app.delete("/api/admin/feedback/{fid}")
def admin_delete(fid: int, admin=Depends(require_admin)):
    with get_db() as conn:
        cur = conn.execute("DELETE FROM feedback WHERE id = ?", (fid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Feedback not found.")
    return {"message": "Feedback deleted."}


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/login.html")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
