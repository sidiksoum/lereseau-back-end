import stripe
from app.core.config import settings

if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY

def create_checkout_session(user_id: str, success_url: str, cancel_url: str):
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'xof',
                'product_data': {
                    'name': 'Abonnement Premium LeRéseau',
                },
                'unit_amount': 9850,
            },
            'quantity': 1,
        }],
        mode='payment',
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=user_id
    )
    return session
