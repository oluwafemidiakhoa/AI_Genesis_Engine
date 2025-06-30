# app/main.py

from flask import Blueprint, render_template

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # In a real app, you would check if the user is logged in
    return render_template('index.html')

@main.route('/success')
def success():
    return render_template('success.html')

@main.route('/cancel')
def cancel():
    return render_template('cancel.html')