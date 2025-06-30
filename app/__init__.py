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

    # Import and register blueprints here
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app