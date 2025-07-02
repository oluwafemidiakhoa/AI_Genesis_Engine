# app/__init__.py

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import config # Import the final, chosen config object

db = SQLAlchemy()

def create_app(config_name='dev'):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config[config_name])
    
    # Ensure the instance folder exists, as Flask needs it.
    # We will create the db file separately.
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)

    # Import and register blueprints
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from .payments import payments as payments_blueprint
    app.register_blueprint(payments_blueprint, url_prefix='/payments')

    return app
