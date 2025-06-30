# config.py

import os
from dotenv import load_dotenv

load_dotenv()

# Define the path for our writable data directory
# This will be /data inside the Docker container
INSTANCE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
if os.environ.get('IN_DOCKER'): # A way to detect if we're in the Docker container
    INSTANCE_DIR = '/data'


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'a_very_secret_key_that_should_be_changed')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Tell Flask where its instance folder is. This must be a writable path.
    INSTANCE_PATH = INSTANCE_DIR

class DevelopmentConfig(Config):
    DEBUG = True
    # Point the SQLite database to our new writable data directory
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', f'sqlite:///{os.path.join(INSTANCE_DIR, "dev.db")}')
    
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID', 'price_xxxxxxxxxxxxxx')

# ... (ProductionConfig can be updated similarly) ...
class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv('POSTGRES_URL') # Production should use Postgres
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')


config_by_name = dict(
    dev=DevelopmentConfig,
    prod=ProductionConfig
)