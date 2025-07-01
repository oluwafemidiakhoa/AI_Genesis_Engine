# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# The guaranteed writable path in Hugging Face Spaces with persistent storage
# If this directory doesn't exist, the app will create it.
DATA_DIR = "/data"

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_key_that_should_be_changed')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Point the instance path directly to our writable directory
    INSTANCE_PATH = os.path.join(DATA_DIR, 'instance')

class DevelopmentConfig(Config):
    DEBUG = True
    # Point the SQLite database URI to a file within our writable directory
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(DATA_DIR, "app.db")}')
    
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', 'price_xxxxxxxxxxxxxx')

class ProductionConfig(Config):
    # In a real production environment, you would use a managed database like PostgreSQL
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL', f'sqlite:///{os.path.join(DATA_DIR, "prod.db")}')
    # ... other production settings ...

config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig
)