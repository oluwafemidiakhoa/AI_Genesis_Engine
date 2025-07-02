# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# The guaranteed writable path in Render/HF Spaces with persistent storage
DATA_DIR = "/data"

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set. Please set it in your environment secrets.")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

class DevelopmentConfig(Config):
    DEBUG = True
    # Point the SQLite database to a file within our writable data directory
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{DATA_DIR}/dev.db')
    
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL', f'sqlite:///{DATA_DIR}/prod.db')
    # ... other settings

config = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig
}
