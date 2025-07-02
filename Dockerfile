FROM python:3.9-slim

WORKDIR /code

# Copy requirements and install them
COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy all our application files
COPY . /code/

# Make our entrypoint script executable
RUN chmod +x /code/entrypoint.sh

# Expose the port
EXPOSE 8000

# Set the entrypoint script as the command to run when the container starts
ENTRYPOINT ["/code/entrypoint.sh"]
