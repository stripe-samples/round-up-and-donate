#! /usr/bin/env python3.6

"""
server.py
Stripe Sample.
Python 3.6 or newer required.
"""

import stripe
import json
import os
import random

from flask import Flask, render_template, jsonify, request, send_from_directory
from dotenv import load_dotenv, find_dotenv

# Setup Stripe python client library
load_dotenv(find_dotenv())
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe.api_version = os.getenv('STRIPE_API_VERSION')

static_dir = str(os.path.abspath(os.path.join(
    __file__, "..", os.getenv("STATIC_DIR"))))
app = Flask(__name__, static_folder=static_dir,
            static_url_path="", template_folder=static_dir)


@app.route('/', methods=['GET'])
def get_checkout_page():
    # Display checkout page
    return render_template('index.html')


def calculate_order_amount(isDonating):
    # Replace this constant with a calculation of the order's amount
    # Calculate the order total on the server to prevent
    # people from directly manipulating the amount on the client
    return 1400 if isDonating else 1354


@app.route('/create-payment-intent', methods=['POST'])
def create_payment():
    data = json.loads(request.data)

    # Required if we want to transfer part of the payment as a donation
    # A transfer group is a unique ID that lets you associate transfers with the original payment
    transfer_group = "group_" + str(random.randint(0, 10000))

    # Create a PaymentIntent with the order amount and currency
    intent = stripe.PaymentIntent.create(
        amount=calculate_order_amount(False),
        currency=data['currency'],
        transfer_group=transfer_group
    )

    try:
        # Send publishable key and PaymentIntent details to client
        return jsonify({'publicKey': os.getenv('STRIPE_PUBLISHABLE_KEY'), 'paymentIntent': intent})
    except Exception as e:
        return jsonify(str(e)), 403


@app.route('/update-payment-intent', methods=['POST'])
def update_payment():
    data = json.loads(request.data)

    intent = stripe.PaymentIntent.retrieve(data['id'])
    metadata = intent.metadata
    if data['isDonating']:
        # Add metadata to track the amount being donated
        metadata.update(
            {'donationAmount': 46, 'organizationAccountId': os.getenv("ORGANIZATION_ACCOUNT_ID")})
    else:
        metadata.update(
            {'donationAmount': 0, 'organizationAccountId': ''})

    updated_intent = stripe.PaymentIntent.modify(data['id'],
                                                 metadata=metadata,
                                                 amount=calculate_order_amount(data['isDonating']))

    try:
        # Send new amount to client
        return jsonify({'amount': updated_intent.amount})
    except Exception as e:
        return jsonify(error=str(e)), 403


@app.route('/webhook', methods=['POST'])
def webhook_received():
    # You can use webhooks to receive information about asynchronous payment events.
    # For more about our webhook events check out https://stripe.com/docs/webhooks.
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    request_data = json.loads(request.data)

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return e
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request_data['data']
        event_type = request_data['type']
    data_object = data['object']

    if event_type == 'payment_intent.succeeded':
        if 'donationAmount' in data_object['metadata'] and data_object['metadata']['donationAmount']:
            # Customer made a donation
            # Use Stripe Connect to transfer funds to organization's Stripe account
            transfer = stripe.Transfer.create(
                amount=data_object['metadata']['donationAmount'],
                currency="usd",
                destination=data_object['metadata']['organizationAccountId'],
                transfer_group=data_object['transfer_group']
            )
            print('😀 Customer donated ' + str(transfer.amount) + ' to ' + str(transfer.destination) +
                  ' send them a thank you email at ' + str(data_object['receipt_email']))
        else:
            print('😶 Payment received -- customer did not donate.')
    elif event_type == 'payment_intent.payment_failed':
        print('❌ Payment failed.')
    return jsonify({'status': 'success'})


if __name__ == '__main__':
    app.run()
