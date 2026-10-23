# Customer Feedback App

Users register, log in, and add or edit their own feedback. An admin gets a dashboard
with full CRUD (view, add, edit, delete) over all feedback.

**Stack:** FastAPI + SQLite (stdlib `sqlite3`) + plain HTML/CSS/JS. No build step.

## Run

```bash
python -m venv .venv
source .venv/bin/activate       
pip install -r requirements.txt
uvicorn main:app --reload
```

Open http://127.0.0.1:8000

## Accounts

- **Admin** (seeded on first start): `admin` / `admin123`
  Override with env vars `ADMIN_USERNAME` and `ADMIN_PASSWORD` before the first run.
- **Users:** sign up from the Register page.

## Pages

| Page | Purpose |
|------|---------|
| `/login.html` | Log in (redirects admins to the dashboard, users to feedback) |
| `/register.html` | Create a user account |
| `/feedback.html` | Add Feedback / Edit Feedback (one entry per user) |
| `/admin.html` | Admin Feedback Dashboard: View / Edit / Delete, plus Add |

## API

Interactive docs at `/docs`. Auth is a bearer token returned by `POST /api/login`.

- `POST /api/register`, `POST /api/login`, `POST /api/logout`, `GET /api/me`
- `GET /api/feedback/mine`, `POST /api/feedback`, `PUT /api/feedback/mine`
- Admin only: `GET/POST /api/admin/feedback`, `GET/PUT/DELETE /api/admin/feedback/{id}`

## Notes

- Passwords are hashed with PBKDF2-SHA256 and a per-user salt.
- Set `DB_PATH` to move the SQLite file. Change the seeded admin password before deploying.
