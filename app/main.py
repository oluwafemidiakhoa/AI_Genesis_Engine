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

from .models import User, Project

@main.route('/projects')
def list_projects():
    # For now, we'll fetch projects for the dummy user.
    # In a real app, you would get the user from the session.
    user = User.query.filter_by(email="customer@example.com").first()
    projects = []
    if user:
        projects = Project.query.filter_by(user_id=user.id).order_by(Project.created_at.desc()).all()
    return render_template('projects.html', projects=projects)

@main.route('/cancel')
def cancel():
    return render_template('cancel.html')