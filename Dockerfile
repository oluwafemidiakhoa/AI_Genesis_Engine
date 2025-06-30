# Use a stable, slim version of Python as the base
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /code

# Copy the requirements file first to leverage Docker's layer caching
COPY ./requirements.txt /code/requirements.txt

# Install dependencies
# Using --no-cache-dir makes the image smaller
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy the rest of your application code into the container
# This includes the 'app' folder, config.py, etc.
COPY . /code/

# Expose the port that Gunicorn will run on
EXPOSE 7860

# The command to run your app using Gunicorn
# This is the standard for running Flask apps in production.
# It tells Gunicorn to find the 'app' object inside the 'run.py' file.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:7860", "run:app"]