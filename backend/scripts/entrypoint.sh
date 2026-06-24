#!/bin/sh
set -e

alembic upgrade head
python -m scripts.bootstrap
exec uvicorn marina_service.main:app --host 0.0.0.0 --port "${PORT:-8000}"
