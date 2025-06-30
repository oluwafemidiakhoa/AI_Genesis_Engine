# app/payments.py

import stripe
from flask import Blueprint, request, jsonify, redirect, url_for, current_app
from .models import User, db

payments = Blueprint('payments', __name__)

# This is a placeholder. In a real app, you'd have a user session.
# For this example, we'll create a new user on checkout.
DUMMY_USER_EMAIL = "customer@example.com"

@payments.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    try:
        # For this demo, find or create a dummy user
        user = User.query.filter_by(email=DUMMY_USER_EMAIL).first()
        if not user:
            # Create a customer in Stripe
            customer = stripe.Customer.create(email=DUMMY_USER_EMAIL)
            # Create user in our DB
            user = User(email=DUMMY_USER_EMAIL, stripe_customer_id=customer.id)
            db.session.add(user)
            db.session.commit()
        
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[
                {
                    'price': current_app.config['STRIPE_PRICE_ID'],
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=url_for('main.success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('main.cancel', _external=True),
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        return jsonify(error=str(e)), 403

@payments.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError as e:
        # Invalid payload
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return 'Invalid signature', 400

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        
        # Find the user in your database and update their subscription status
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.is_subscribed = True
            user.subscription_id = subscription_id
            db.session.commit()
            print(f"User {user.email} has successfully subscribed.")

    return 'Success', 200