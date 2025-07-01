# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config # Import the specific config object, not the dictionary
import os

db = SQLAlchemy()

def create_app(): # No need for config_name anymore
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config) # Load the configuration object
    
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    db.init_app(app)

    with app.app_context():
        from . import models
        db.create_all()

    # ... rest of the file (blueprints, etc.)
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app