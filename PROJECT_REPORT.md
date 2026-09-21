PROJECT REPORT — Customer Support Ticketing CRM System
Prepared for submission to ozair.shaikh@datastraw.in, aryan.jaiswal@datastraw.in (CC: talent@datastraw.in)

1. PROJECT OVERVIEW
Name: Support OS — Customer Support Ticketing CRM
Type: Full-stack web application (FastAPI backend + Streamlit frontend)
Purpose: A role-based support ticket CRM with AI-assisted reply drafting, persistent SQLite storage, and a modern glassmorphism UI.

2. TECHNICAL ARCHITECTURE
- Backend: FastAPI (REST endpoints, static file serving, SQLite via SQLAlchemy)
- Database: SQLite (tickets, notes, users, replies) with persistent auth and ownership
- Frontend: Streamlit (interactive dashboard, multi-tab navigation, session-based state)
- AI Provider: OpenRouter (openai/gpt-4o-mini) with graceful error handling
- Security: PBKDF2 hashed passwords, role-based access (admin / customer), session authentication
- Styling: Custom CSS glassmorphism with soft sunset gradient, floating pastel shapes, frosted cards, modern typography

3. KEY FEATURES IMPLEMENTED
- Role-based login (admin / customer) with sign-up for customers
- Admin: full ticket queue, status dropdown (Open / In Progress / Closed), AI draft, internal notes, customer reply sending, email notifications
- Customer: raise tickets, view only own tickets, see support replies, track status, receive email confirmations
- Customer replies stored in database and visible to both roles
- Email notifications via SMTP (optional .env configuration)
- Multi-page design: Home, App / CRM, About
- Glassmorphism UI with animations and centered alignment

4. CHALLENGES ENCOUNTERED & SOLUTIONS
- Gemini API failures (404 / 503 / deprecated models): switched to OpenRouter as primary provider; kept graceful fallback
- Streamlit session state lost on reload: moved ticket storage to SQLite with owner_username filtering
- Railway deployment mismatch (FastAPI vs Streamlit): updated railway.toml to start Streamlit
- Design request for animations/alignment: added CSS float animations, centered cards, clean navigation
- SQLite NOT NULL errors on new inserts: added CURRENT_TIMESTAMP to insert statements

5. DEPLOYMENT STATUS
- GitHub: https://github.com/Tejk20/crm-ticket-system
- Railway: https://crm-ticket-system-production-cea2.up.railway.app/
- Latest commit: 46aeb85 (Railway Streamlit fix) / 69439f7 (role/auth/reply system)
- Status: Running locally at http://127.0.0.1:8503; Railway redeploy triggered after push

6. IMPROVEMENTS WITH ADDITIONAL TIME
- Migrate SQLite to PostgreSQL for production concurrency
- Add real-time notifications (polling / WebSocket)
- Implement full SMTP verification and delivery tracking
- Add analytics/reporting dashboard
- Add mobile-responsive refinements and accessibility improvements
- Record a demo video for submission

7. SUBMISSION DETAILS
To: ozair.shaikh@datastraw.in, aryan.jaiswal@datastraw.in
CC: talent@datastraw.in
LinkedIn profile: [Please attach your working LinkedIn profile link]
Demo video: Not yet recorded — can be created by recording the Streamlit session at http://127.0.0.1:8503
