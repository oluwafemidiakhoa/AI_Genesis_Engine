# run.py
from app import create_app
import os

# Use the FLASK_CONFIG env var, or default to 'dev'
config_name = os.getenv('FLASK_CONFIG', 'dev')
app = create_app(config_name)

if __name__ == '__main__':
    app.run()
