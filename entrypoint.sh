#!/bin/sh

# This script will run every time the container starts.

# Exit immediately if a command exits with a non-zero status.
set -e

# 1. Run the database initialization command.
#    The 'flask' command will have access to all the environment
#    variables at this point.
echo "Initializing database..."
flask --app manage.py init_db

# 2. Start the main application server (Gunicorn).
#    'exec' replaces the shell process with the Gunicorn process,
#    which is the correct way to run the main application.
echo "Starting Gunicorn..."
exec gunicorn --workers 2 --bind 0.0.0.0:8000 "run:app"
