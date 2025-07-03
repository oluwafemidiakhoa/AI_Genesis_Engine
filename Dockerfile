# ─────────────────────────────
# Stage 1: Tailwind CSS Builder
# ─────────────────────────────
FROM node:18-alpine AS tailwind-builder

WORKDIR /app

# Install Tailwind dependencies
COPY package*.json ./
RUN npm install

# Copy Tailwind input and config files
COPY ./app/static/css ./app/static/css
COPY tailwind.config.js ./

# Build the CSS
RUN npx tailwindcss -i ./app/static/css/input.css -o ./app/static/css/output.css

# ─────────────────────────────
# Stage 2: Python Backend
# ─────────────────────────────
FROM python:3.10-slim

WORKDIR /app

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY . .

# Bring in built CSS from tailwind-builder stage
COPY --from=tailwind-builder /app/app/static/css/output.css ./app/static/css/output.css

# Expose default port (optional for local testing)
EXPOSE 8000

# Run the app (Render will inject $PORT at runtime)
CMD gunicorn --bind 0.0.0.0:$PORT wsgi:app
