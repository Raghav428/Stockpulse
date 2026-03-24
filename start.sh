#!/bin/bash
uv run alembic upgrade head
/app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000