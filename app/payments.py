# app/payments.py

import stripe
from flask import Blueprint, request, jsonify, current_app
from .models import User, db

payments = Blueprint('payments', __name__)

DUMMY_USER_EMAIL = "customer@example.com"

@payments.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    data = request.get_json()
    business_idea = data.get('business_idea')

    if not business_idea:
        return jsonify(error="Business idea is required."), 400
    
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
            metadata={
                'business_idea': business_idea
            }
        )
        return jsonify({'url': checkout_session.url})
    except Exception as e:
        return jsonify(error=str(e)), 403

from .engine.agents import Strategist
from .models import Project

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
        business_idea = session.get('metadata', {}).get('business_idea')

        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            # Update user subscription status
            user.is_subscribed = True
            user.subscription_id = subscription_id

            if business_idea:
                # Create a new project
                new_project = Project(
                    user_id=user.id,
                    business_idea=business_idea,
                    status='generating_prd'
                )
                db.session.add(new_project)
                db.session.commit()

                # Trigger the Strategist agent
                try:
                    strategist = Strategist()
                    prd = strategist.generate_prd(business_idea)
                    new_project.prd = prd
                    new_project.status = 'completed'
                    print(f"PRD generated for project {new_project.id}")
                except Exception as e:
                    new_project.status = 'failed'
                    new_project.prd = f"Failed to generate PRD: {e}"
                    print(f"Error generating PRD for project {new_project.id}: {e}")

            db.session.commit()
            print(f"User {user.email} has successfully subscribed and project processed.")

    return 'Success', 200