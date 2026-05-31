# TrustLed Aula

**The governed AI platform for universities.**

Aula gives an institution one sanctioned AI environment for staff and students,
so the university can oversee and log all AI use instead of people relying on
unapproved public tools. Every AI interaction runs through the server and is
recorded, which is what makes the platform *governed* rather than just another
AI tool.

## What it does

**Shared (lecturers and students)**
- Research Assistant — develops research and project ideas from a user's
  interests, with references in the institution's house style.
- Reference Formatter — formats raw source details in the house style.

**Lecturers**
- Lesson Planner — a semester-aligned plan with objectives, timing, and activities.
- Lecture Notes — structured teaching notes, saved and re-openable.

**Students**
- Research Support — guidance on project topics, structure, and drafting.
- Exam Preparation — revision summaries and practice questions.

**Admins (the governance layer)**
- Dashboard — AI usage by feature, role, and volume.
- Audit Log — every interaction, searchable and exportable to CSV.
- User Accounts — create and deactivate staff and student access.
- Settings — set the institution's referencing style, applied everywhere.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env
python init_db.py             # creates the database and three test accounts
flask --app wsgi run --debug  # or: python wsgi.py
```

Open http://127.0.0.1:5000 and sign in with one of the seeded accounts:

| Role     | Email                | Password     |
|----------|----------------------|--------------|
| Admin    | admin@aula.test      | admin123     |
| Lecturer | lecturer@aula.test   | lecturer123  |
| Student  | student@aula.test    | student123   |

> Change these immediately in any real deployment.

## AI provider

Aula calls the model on the server so usage can be logged. Set these in `.env`:

```
LLM_PROVIDER=anthropic            # or: openai
LLM_API_KEY=your-key-here
LLM_MODEL=claude-3-5-sonnet-20241022
```

**Demo mode:** leave `LLM_API_KEY` blank and the app runs end to end without
live AI, returning a clearly-labelled placeholder. Every request is still
logged, so the governance features can be demonstrated with no API spend.

## Deploy to Render (recommended)

Aula is a Flask server with a database, so it needs a host that runs Python web
services. **Netlify does not** (it is for static sites and short serverless
functions), so use Render, Railway, Fly.io, or similar. Render is the simplest:

1. Push this folder to a GitHub repository.
2. On Render, create a **New > Blueprint** and point it at the repo. The included
   `render.yaml` configures the build, start command, and a generated `SECRET_KEY`.
3. Add a Postgres database in Render (free tier) and Render will provide a
   `DATABASE_URL`; the app reads it automatically.
4. Set `LLM_API_KEY` in the Render dashboard (it is marked `sync: false` so it is
   never committed).
5. Deploy. The build runs `init_db.py` to seed the first accounts.

Alternatively, the included `Procfile` (`web: gunicorn wsgi:app`) works on
Railway and most other Python hosts.

## Project structure

```
app/
  __init__.py        application factory
  config.py          settings from environment variables
  extensions.py      db + login manager
  models.py          Institution, User, AuditLog, artefact tables
  decorators.py      role-based access control
  llm_service.py     single governed gateway to the AI model + logging
  auth/              login / logout
  main/              dashboard + shared features
  lecturer/          lesson planner, lecture notes
  student/           research support, exam prep
  admin/             users, audit log, usage, settings
  templates/         Jinja2 + Tailwind UI
init_db.py           seed script
wsgi.py              entry point
```

## Notes

- Plagiarism detection is intentionally not included.
- For production, move from SQLite to Postgres (set `DATABASE_URL`), rotate the
  seeded passwords, and restrict account creation to your administrator.
