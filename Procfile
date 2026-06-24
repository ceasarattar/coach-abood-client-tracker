# Single worker, NO threads — matches render.yaml. Parallel Sheets reads OOM
# Render's 512MB free tier (see HANDOFF_CLAUDE.md). Do not add --threads.
web: gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
