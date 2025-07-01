# app/payments.py

import stripe
from flask import Blueprint, request, jsonify, current_app
from .models import User, db

payments = Blueprint('payments', __name__)

DUMMY_USER_EMAIL = "customer@example.com"

@payments.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    
    try:
        user = User.query.filter_by(email=DUMMY_USER_EMAIL).first()
        if not user:
            customer = stripe.Customer.create(email=DUMMY_USER_EMAIL)
            user = User(email=DUMMY_USER_EMAIL, stripe_customer_id=customer.id)
            db.session.add(user)
            db.session.commit()
        
        domain_url = request.host_url
        
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{'price': current_app.config['STRIPE_PRICE_ID'], 'quantity': 1}],
            mode='subscription',
            success_url=domain_url + 'success',
            cancel_url=domain_url + 'cancel',
        )
        # THE FIX: Return the URL as JSON
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        return jsonify(error=str(e)), 403

# ... The webhook function remains the same ...
@payments.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError: return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError: return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        customer_id = session.get('customer')
        subscription_id = session.get('subscription')
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.is_subscribed = True
            user.subscription_id = subscription_id
            db.session.commit()
            print(f"User {user.email} has successfully subscribed.")
    return 'Success', 200