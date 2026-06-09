"""WSGI entry point for production servers, e.g. `gunicorn wsgi:app`.

Importing app runs db.bootstrap() (create tables + seed library + import any
legacy clients.yaml), so a fresh hosted database is usable on first request.
"""
from app import app

if __name__ == "__main__":
    app.run()
