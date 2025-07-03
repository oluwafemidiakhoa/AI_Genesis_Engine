# Stage 1: Build frontend assets
FROM node:18-slim as frontend-builder

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the frontend source code
COPY . .

# Build the CSS. This runs the "build" script from your package.json
RUN npm run build

# Stage 2: Setup the Python application
FROM python:3.10-slim

WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Copy the built static assets from the previous stage
COPY --from=frontend-builder /app/app/static/css/output.css ./app/static/css/output.css

# The command to run the application (Render will use the PORT environment variable)
CMD gunicorn --bind 0.0.0.0:$PORT wsgi:app
