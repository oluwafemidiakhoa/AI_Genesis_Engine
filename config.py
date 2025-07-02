# config.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set. Please set it in your environment secrets.")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') # This will now be set by Render
    if not SQLALCHEMY_DATABASE_URI:
        # Fallback for local development if DATABASE_URL is not set
        SQLALCHEMY_DATABASE_URI = 'sqlite:///dev.db'
        print("WARNING: DATABASE_URL not found. Falling back to local SQLite database.")

    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig
}
