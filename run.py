# run.py

# Import the application factory function we created in our 'app' package.
from app import create_app

# Call the factory to create the application instance.
# It will automatically use the correct configuration (dev or prod)
# based on the FLASK_ENV environment variable.
app = create_app()

if __name__ == "__main__":
    # This block runs only when you execute `python run.py` directly.
    # It's perfect for local development.
    # In production, a WSGI server like Gunicorn will import the `app` object directly.
    # We get the HOST and PORT from the environment variables, which is standard practice.
    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5001))
    
    # app.config.get('DEBUG', False) will be True for DevelopmentConfig
    # and False for ProductionConfig.
    app.run(host=host, port=port, debug=app.config.get('DEBUG', False))