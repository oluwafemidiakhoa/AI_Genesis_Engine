# config.py

import os
from dotenv import load_dotenv

# Load environment variables from a .env file for local development
load_dotenv()

class Config:
    """Base configuration."""
    SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_key_that_should_be_changed')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    # For simplicity, we'll use SQLite for local dev.
    # A production app would use the POSTGRES_URL.
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///dev.db')
    POSTGRES_URL = os.getenv('POSTGRES_URL') # For production
    
    # Stripe Keys
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET') # Get this from your Stripe webhook settings
    
    # Define your Stripe Price ID for the subscription
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', 'price_xxxxxxxxxxxxxx') # Replace with your actual Price ID

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL')
    
    # Stripe Keys (should always be set in production)
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')

config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig
)