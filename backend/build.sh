#!/usr/bin/env bash
set -o errexit

cd "$(dirname "$0")/.."

node -v
(cd frontend && npm ci && npm run build)

cd backend
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate

if [ "$SEED_DEMO" = "1" ]; then
  python manage.py seed_demo --reset
  python manage.py seed_facts
fi