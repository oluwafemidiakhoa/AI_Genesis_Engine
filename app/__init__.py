# app/__init__.py

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config # Import the final, chosen config object

# Initialize the database extension, but don't attach it to an app yet.
db = SQLAlchemy()

def create_app():
    """
    An application factory, as described in the Flask docs.
    This pattern allows for creating multiple app instances, which is great for testing.
    """
    
    # Create the core Flask app object.
    # instance_relative_config=True means it will look for config files
    # relative to an 'instance' folder.
    app = Flask(__name__, instance_relative_config=True)
    
    # Load the configuration from our config.py object.
    app.config.from_object(config)

    # Ensure the instance folder exists. Flask and extensions might use it.
    try:
        os.makedirs(app.instance_path)
    except OSError:
        # The directory already exists, which is fine.
        pass

    # Initialize extensions with the app
    db.init_app(app)

    # The app_context is crucial. It makes sure that the application is "live"
    # and knows about its configuration (like the database URI) before we try
    # to perform database operations.
    with app.app_context():
        # Import models here to prevent circular import issues.
        from . import models

        # This command connects to the database and creates all tables
        # defined in models.py, if they don't already exist.
        db.create_all()

        # Import and register the Blueprints (our route files).
        # This keeps our app organized.
        from .main import main as main_blueprint
        app.register_blueprint(main_blueprint)

        from .payments import payments as payments_blueprint
        app.register_blueprint(payments_blueprint, url_prefix='/payments')

        # You can register more blueprints here as your app grows.
        # from .auth import auth as auth_blueprint
        # app.register_blueprint(auth_blueprint, url_prefix='/auth')

    return app