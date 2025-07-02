# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config # Import the final, chosen config object
import os # <--- THE MISSING IMPORT IS NOW HERE

db = SQLAlchemy()

def create_app(config_name='dev'):
    # Select the configuration object
    app_config = config.get(config_name, config['dev'])
    
    # Create the app, telling it where the instance folder is
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(app_config)

    # Use the instance path from the config object
    # This ensures it points to a writable directory like /data/instance
    instance_path = app.instance_path
    if not os.path.exists(instance_path):
        try:
            os.makedirs(instance_path)
        except OSError as e:
            # Handle potential race conditions in a multi-worker environment
            if not os.path.isdir(instance_path):
                raise e
    
    db.init_app(app)

    # Within the app context, ensure the database and its tables are created.
    with app.app_context():
        # Importing models here prevents circular import errors
        from . import models
        db.create_all()

    # Import and register the blueprints for our routes
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app
