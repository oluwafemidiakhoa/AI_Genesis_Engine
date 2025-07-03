# ─────────────────────────────
# Stage 1: Tailwind CSS Builder
# ─────────────────────────────
FROM node:18-alpine AS tailwind-builder

WORKDIR /app

# Install Tailwind
COPY package*.json ./
RUN npm install

# Copy Tailwind input and config
COPY ./app/static/css ./app/static/css
COPY tailwind.config.js ./

# Build the CSS
RUN npx tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css

# ─────────────────────────────
# Stage 2: Python Backend
# ─────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# Prevent .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Copy compiled CSS from Node stage
COPY --from=tailwind-builder /app/app/static/css/output.css ./app/static/css/output.css

# Optional: expose default dev port
EXPOSE 8000

# Use shell form to allow $PORT expansion; fallback to 8000 if undefined
CMD /bin/sh -c "gunicorn --bind 0.0.0.0:${PORT:-8000} wsgi:app"
