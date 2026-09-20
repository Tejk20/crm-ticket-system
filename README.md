# Support Ticket CRM

A lightweight customer support ticketing CRM built with FastAPI, SQLite, SQLAlchemy, Tailwind CSS, and vanilla JavaScript.

## Run locally

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Start the development server:

   ```powershell
   uvicorn main:app --reload
   ```

Open <http://127.0.0.1:8000>. The SQLite database is created automatically as `support_tickets.db`.

## OpenRouter AI replies

Create a `.env` file in the project root and add your OpenRouter API key:

```text
OPENROUTER_API_KEY=your-key-here
```

The CRM uses OpenRouter to draft customer replies from the ticket subject, description, priority, category, and internal notes. The draft is placed in the modal for review before it is saved.

## API

Interactive API documentation is available at `/docs`. The API supports creating tickets, automatic priority/category triage, filtering and searching ticket lists, viewing ticket details with notes, and updating status or adding notes.

## Deploy to Railway

1. Push this repository to GitHub, making sure `.env` is not committed.
2. In Railway, choose **New Project** and **Deploy from GitHub repo**.
3. Select this repository and the branch you want to deploy, usually `main`.
4. In the Railway service variables, add `OPENROUTER_API_KEY` with your key.
5. Deploy. Railway reads `railway.toml`, installs `requirements.txt`, and starts FastAPI on Railway's assigned `$PORT`.

Railway automatically redeploys the service whenever new commits are pushed to the connected branch. Use the service's **Deployments** tab to inspect build logs and roll back if needed.

The default SQLite database is suitable for testing, but Railway's filesystem is ephemeral. For production data, attach a Railway volume mounted at the project root or migrate the `DATABASE_URL` in `database.py` to a managed PostgreSQL database.
