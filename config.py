# config.py
import os
from dotenv import load_dotenv

# Load environment variables from a .env file if it exists.
# This is useful for local development.
load_dotenv()

class Config:
    """Base configuration settings."""
    # A strong secret key is crucial for session security.
    # It's better to fail if it's not set in production.
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. Please set it in your environment.")

    # This is a good default and reduces overhead.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Stripe keys that are common to all environments
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

    # Fail fast if essential Stripe keys are missing.
    # This prevents the app from running in a broken state.
    if not all([STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY, STRIPE_PRICE_ID]):
        raise ValueError("One or more required Stripe keys (PUBLISHABLE, SECRET, or PRICE_ID) are not set.")

class DevelopmentConfig(Config):
    """Configuration for development."""
    DEBUG = True
    
    # Use a guaranteed-writable directory for the local SQLite database.
    # This path is relative to the project root.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/dev.db')
    
    # Ensure the instance folder exists for the SQLite database.
    # The 'instance' folder is the conventional place for this in Flask.
    instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'instance')
    os.makedirs(instance_path, exist_ok=True)


class ProductionConfig(Config):
    """Configuration for production."""
    DEBUG = False
    
    # Production should always use a robust, managed database like PostgreSQL.
    # The application will fail to start if DATABASE_URL is not set.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    if not SQLALCHEMY_DATABASE_URI:
        raise ValueError("No DATABASE_URL set for production environment.")

# A dictionary to access configurations by name, e.g., 'dev' or 'prod'.
# We can determine which to use via an environment variable.
config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig
)

# You can set FLASK_ENV=prod in your Hugging Face secrets to use the production config.
key = os.getenv('FLASK_ENV', 'dev')
config = config_by_name[key]