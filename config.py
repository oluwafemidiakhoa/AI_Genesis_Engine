# config.py
import os
from dotenv import load_dotenv

# load_dotenv() will load variables from a .env file for LOCAL development.
# In production on Render, these will be set by the dashboard/render.yaml.
load_dotenv()

class Config:
    """Base configuration class."""
    
    # CRITICAL: Flask requires a secret key for session management and security.
    # This MUST be set in your Render environment secrets.
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("FATAL ERROR: No SECRET_KEY set. Please set this in your environment secrets.")
        
    # This is a standard setting to disable a noisy Flask-SQLAlchemy feature.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # This will be automatically provided by Render via the render.yaml file.
    # We raise an error if it's missing to ensure the app doesn't run without a database.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        # For local development and testing, we fall back to a local SQLite database.
        SQLALCHEMY_DATABASE_URI = "sqlite:///dev.db"

    # All your other API keys are loaded from the environment here.
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')
    
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')


class DevelopmentConfig(Config):
    """Configuration for local development."""
    DEBUG = True

class ProductionConfig(Config):
    """Configuration for production."""
    DEBUG = False
    # In production, you might want to add other settings, like logging configurations.

# This dictionary allows us to select the configuration by name.
config = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig
}
