# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config_by_name
import os

db = SQLAlchemy()

def create_app(config_name='dev'):
    config_obj = config_by_name[config_name]
    
    # Create the app, telling it where the instance folder is
    app = Flask(__name__, instance_path=config_obj.INSTANCE_PATH, instance_relative_config=True)
    app.config.from_object(config_obj)
    
    # Ensure the instance folder and the data directory exist
    # This is crucial for the database file to be created
    if not os.path.exists(config_obj.INSTANCE_PATH):
        os.makedirs(config_obj.INSTANCE_PATH)
    
    db.init_app(app)

    with app.app_context():
        from . import models
        db.create_all()

    # Import and register blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app