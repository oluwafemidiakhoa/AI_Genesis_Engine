# app/models.py

from . import db
from datetime import datetime

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Stripe-related fields
    stripe_customer_id = db.Column(db.String(120), unique=True)
    is_subscribed = db.Column(db.Boolean, default=False)
    subscription_id = db.Column(db.String(120), unique=True)

    def __repr__(self):
        return f'<User {self.email}>'