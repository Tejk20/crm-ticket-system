SUBMISSION COVER LETTER — Customer Support Ticketing CRM System

To: ozair.shaikh@datastraw.in, aryan.jaiswal@datastraw.in
CC: talent@datastraw.in

Project: Support OS — Customer Support Ticketing CRM
GitHub: https://github.com/Tejk20/crm-ticket-system
Deployed: https://crm-ticket-system-production-cea2.up.railway.app/

TECHNICAL APPROACH & ARCHITECTURE
- FastAPI backend with SQLAlchemy + SQLite for persistent tickets, notes, users, and replies
- Streamlit frontend with role-based authentication (admin / customer)
- OpenRouter AI integration for draft reply generation (fallback to manual text if unavailable)
- Glassmorphism UI with soft sunset gradient, floating pastel shapes, frosted cards, and modern typography
- Persistent SQLite auth layer with hashed passwords (PBKDF2) and ticket ownership

KEY FEATURES
- Admin dashboard: full queue, status dropdown (Open / In Progress / Closed), AI draft, internal notes, customer reply sending
- Customer portal: sign-up/login, raise tickets, view only own tickets, see support replies, track status
- Email notifications when tickets are raised and when admin sends replies (SMTP optional via .env)
- Multi-page design: Home, App / CRM, About

CHALLENGES & SOLUTIONS
- Gemini API key issues (404 / 503 / deprecated model names): switched to OpenRouter as primary provider with graceful error handling
- Streamlit session state lost on reload: moved ticket storage to SQLite with owner_username filtering
- Railway deployment mismatch: updated railway.toml to start Streamlit instead of FastAPI
- Design request for animations and alignment: added CSS float animations, centered cards, and clean navigation

IMPROVEMENTS WITH MORE TIME
- Replace SQLite with PostgreSQL for production concurrency
- Add real-time notifications (WebSocket / polling)
- Implement full email delivery with SMTP verification
- Add reporting/analytics dashboard
- Add mobile-responsive refinements

DEMO VIDEO
Not yet recorded. Can be created quickly by recording the Streamlit session at http://127.0.0.1:8503.

LINKEDIN PROFILE
Please attach your LinkedIn profile link to this email.
