# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name
import os

db = SQLAlchemy()

def create_app(config_name='dev'):
    # Pass the instance_path directly during app creation
    app = Flask(__name__, instance_path=config_by_name[config_name].INSTANCE_PATH, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)

    # --- THE FINAL FIX ---
    # Create the database tables if they don't exist.
    # We do this within the app context to ensure everything is set up correctly.
    with app.app_context():
        from . import models  # Import models here to avoid circular imports
        db.create_all()
    # --- END OF FIX ---

    # Import and register blueprints here
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app