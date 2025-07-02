FROM python:3.9-slim

WORKDIR /code

# Copy requirements and install them
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of the application code
COPY . /code/

# Run the database initialization command during the build process
# This creates the database file in the persistent /data volume
RUN flask --app manage.py init_db

# Expose the port
EXPOSE 8000

# The command to run the application
# We now point gunicorn to the 'app' object created in run.py
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "run:app"]
