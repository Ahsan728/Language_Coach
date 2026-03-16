# Backend Structure

The Flask backend is now organized around a small app factory and route registration modules:

- `app.py`: local/dev entrypoint that builds the app through `backend.create_app()`.
- `backend/__init__.py`: application factory that configures Flask, initializes the database, and registers routes.
- `backend/services.py`: reusable backend logic shared by web pages and API endpoints.
- `backend/routes/web.py`: HTML page routes, auth flow, and template globals.
- `backend/routes/api.py`: JSON/audio endpoints plus housekeeping helpers tied to API usage.

This keeps the current web behavior intact while separating reusable backend logic from the route layer. Future Android/API work can add new route modules or service functions without putting more endpoint logic back into `app.py`.

The app factory also supports instance-specific path overrides through app config. `BASE_DIR` now drives template/static/logo resolution, while `DATA_DIR` drives JSON content, SQLite, and cache paths unless a more specific override is provided.
