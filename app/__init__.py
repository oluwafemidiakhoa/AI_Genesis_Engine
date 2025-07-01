# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config # Import the final, chosen config object
import os

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    
    db.init_app(app)

    # Within the app context, ensure the database and its tables are created.
    # This will write to the /data directory specified in the config.
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