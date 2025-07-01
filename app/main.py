# app/main.py

from flask import Blueprint, render_template, request

main = Blueprint('main', __name__)

@main.route('/')
def index():
    # THE FIX: Pass the host URL to the template so JavaScript knows where to send the request.
    host_url = request.host_url
    return render_template('index.html', host_url=host_url)

@main.route('/success')
def success():
    return render_template('success.html')

@main.route('/cancel')
def cancel():
    return render_template('cancel.html')