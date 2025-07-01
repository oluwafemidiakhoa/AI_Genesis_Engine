# config.py

import os
from dotenv import load_dotenv

# Load environment variables from a .env file for local development
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. Please set it in your environment secrets.")
        
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    
    # Use the guaranteed writable /data directory for the SQLite database
    # This is the standard path for persistent storage on Hugging Face Spaces.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:////data/dev.db')
    
    # Stripe Keys
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    # For a real production app, you would use a managed database.
    # We still point to /data for a persistent SQLite file if no Postgres URL is provided.
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL', 'sqlite:////data/prod.db')
    
    # Stripe Keys should always be set in production
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')

# Select the configuration based on an environment variable
config_name = os.getenv('FLASK_CONFIG', 'dev')
config = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig
}.get(config_name, DevelopmentConfig)