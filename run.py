# run.py

from app import create_app

app = create_app()

if __name__ == "__main__":
    # Note: In production, you would use a WSGI server like Gunicorn
    # Example: gunicorn --bind 0.0.0.0:5000 "run:app"
    app.run(debug=True, port=5001)