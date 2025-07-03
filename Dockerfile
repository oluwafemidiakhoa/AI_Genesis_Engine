# ─────────────────────────────
# Stage 1: Tailwind CSS Builder
# ─────────────────────────────
FROM node:18-alpine AS tailwind-builder

# Set working directory
WORKDIR /app

# Install Node.js dependencies
COPY package*.json ./
RUN npm install

# Copy Tailwind input and configuration
COPY ./app/static/css ./app/static/css
COPY tailwind.config.js ./

# Build CSS using Tailwind CLI
RUN npx tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css

# ─────────────────────────────
# Stage 2: Python Backend
# ─────────────────────────────
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Copy built CSS from frontend stage
COPY --from=tailwind-builder /app/app/static/css/output.css ./app/static/css/output.css

# Expose a port for local development (optional)
EXPOSE 8000

# Render will provide $PORT at runtime
CMD ["/bin/sh", "-c", "gunicorn --bind 0.0.0.0:$PORT wsgi:app"]
