from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
import stripe
from app.api.dependencies.auth import get_db, get_current_active_user
from app.models.user import User
from app.core.config import settings
from app.services.stripe import create_checkout_session

router = APIRouter()

@router.post("/subscription")
def create_subscription_checkout(
    current_user: User = Depends(get_current_active_user)
):
    try:
        session = create_checkout_session(
            user_id=current_user.id,
            success_url=f"http://localhost:5173/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url="http://localhost:5173/payment/cancel"
        )
        return {"url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header or not settings.STRIPE_WEBHOOK_SECRET:
         return {"status": "ignored"}

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.isPremium = True
            db.commit()
            
            # Le socket event sera poussé plus tard
            
    return {"status": "success"}
