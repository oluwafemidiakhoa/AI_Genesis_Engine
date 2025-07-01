# Use a standard, stable Python base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /code

# Copy requirements and install them
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir -r /code/requirements.txt

# Copy the rest of the application code
COPY . /code/

# Expose the port Gunicorn will run on
EXPOSE 7860

# The command to run the application
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:7860", "run:app"]