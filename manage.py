# manage.py

import os
from app import create_app, db

# Create an app instance for the context
app = create_app(os.getenv('FLASK_CONFIG') or 'dev')

@app.cli.command('init_db')
def init_db_command():
    """Creates the database tables."""
    with app.app_context():
        db.create_all()
    print('Initialized the database.')

if __name__ == '__main__':
    # This allows running 'python manage.py init_db' from the command line
    app.cli()
